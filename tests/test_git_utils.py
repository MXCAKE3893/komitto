import sys
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from komitto.git_utils import (
    get_git_diff,
    get_git_log,
    get_commit_messages,
    git_commit
)

def test_get_git_diff_success():
    """正常系: ステージングされた変更があり、diff が取得できることをテスト"""
    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        if "rev-parse" in cmd:
            res.stdout = "true\n"
        elif "diff" in cmd:
            res.stdout = "diff --git a.txt b.txt\n"
        return res

    with patch("subprocess.run", side_effect=mock_run) as mock_subprocess:
        diff = get_git_diff()
        assert diff == "diff --git a.txt b.txt\n"
        # 呼ばれた回数や引数を確認
        assert mock_subprocess.call_count == 2
        assert mock_subprocess.call_args_list[1][0][0][1] == "diff"

def test_get_git_diff_outside_repo():
    """異常系: リポジトリ外で実行された場合、sys.exit(1) となることをテスト"""
    # 最初の rev-parse が CalledProcessError をスローするようにモック
    def mock_run(cmd, *args, **kwargs):
        if "rev-parse" in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        return MagicMock()

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(SystemExit) as exec_info:
            get_git_diff()
        assert exec_info.value.code == 1

def test_get_git_diff_no_changes():
    """異常系: リポジトリ内だがステージングされた変更がない場合、sys.exit(1) となることをテスト"""
    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        if "rev-parse" in cmd:
            res.stdout = "true\n"
        elif "diff" in cmd:
            res.stdout = ""  # 空の diff
        return res

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(SystemExit) as exec_info:
            get_git_diff()
        assert exec_info.value.code == 1

def test_get_git_diff_with_exclude():
    """正常系: 除外パターンが引数に正しくマッピングされることをテスト"""
    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        res.stdout = "diff content"
        return res

    with patch("subprocess.run", side_effect=mock_run) as mock_subprocess:
        diff = get_git_diff(exclude_patterns=["*.log", "tmp/"])
        assert diff == "diff content"
        
        # 呼ばれた引数を確認
        called_cmd = mock_subprocess.call_args_list[1][0][0]
        # "--", ":(exclude)*.log", ":(exclude)tmp/" が末尾に含まれているか
        assert "--" in called_cmd
        assert ":(exclude)*.log" in called_cmd
        assert ":(exclude)tmp/" in called_cmd

def test_get_git_log_success():
    """正常系: git log が正常に取得・整形されることをテスト"""
    mock_log_output = """Commit: abc1234
Date: 2026-05-28 04:00:00 +0900
Message:
feat: hello world
[Files]
M       src/main.py

Commit: def5678
Date: 2026-05-28 03:00:00 +0900
Message:
fix: crash
[Files]
M       src/utils.py
"""
    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        res.stdout = mock_log_output
        return res

    with patch("subprocess.run", side_effect=mock_run):
        log = get_git_log(limit=2)
        assert log is not None
        assert "Commit: abc1234" in log
        assert "Commit: def5678" in log
        # セパレータで連結されていること
        assert "----------------------------------------" in log

def test_get_git_log_error():
    """異常系: git log コマンド実行中にエラーが発生した場合、None が返ることをテスト"""
    with patch("subprocess.run", side_effect=subprocess.SubprocessError("git error")):
        assert get_git_log() is None

def test_get_commit_messages_success():
    """正常系: 分析用コミットメッセージがヌル文字区切りで正しく取得・パースされることをテスト"""
    # 2回目の git log 呼び出しで返るヌル文字区切りのデータ
    mock_messages_raw = "feat: first message\n\n\0\nfix: second message\n\0"
    
    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        # format:%B%n%x00 形式の出力を想定
        if "%x00" in cmd[-1]:
            res.stdout = mock_messages_raw
        else:
            res.stdout = "dummy"
        return res

    with patch("subprocess.run", side_effect=mock_run):
        messages = get_commit_messages(limit=5)
        # 空の行が除かれ、strip されてリスト化されていること
        assert messages == ["feat: first message", "fix: second message"]

def test_get_commit_messages_error():
    """異常系: コマンド失敗時に空のリストが返ることをテスト"""
    with patch("subprocess.run", side_effect=Exception("error")):
        assert get_commit_messages() == []

def test_git_commit_empty_message():
    """異常系: 空メッセージでのコミットは何も実行せず False を返すことをテスト"""
    with patch("subprocess.run") as mock_run:
        assert git_commit("") is False
        assert git_commit("   ") is False
        mock_run.assert_not_called()

def test_git_commit_success():
    """正常系: git commit コマンドが成功し True が返ることをテスト"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        res = git_commit("feat: test commit")
        assert res is True
        mock_run.assert_called_once_with(["git", "commit", "-m", "feat: test commit"], check=True)

def test_git_commit_failure():
    """異常系: git commit コマンドが例外（非ゼロ終了）を投げて False が返ることをテスト"""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git commit")):
        res = git_commit("feat: failed commit")
        assert res is False
