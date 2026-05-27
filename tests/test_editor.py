import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from komitto.editor import launch_editor

# 環境変数をクリーンにしておくためのヘルパー
@pytest.fixture(autouse=True)
def clean_env():
    env_vars = ['GIT_EDITOR', 'VISUAL', 'EDITOR']
    saved = {var: os.environ.get(var) for var in env_vars}
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]
    yield
    for var, val in saved.items():
        if val is not None:
            os.environ[var] = val
        else:
            if var in os.environ:
                del os.environ[var]

def test_launch_editor_env_priority_git_editor():
    """GIT_EDITOR 環境変数が最優先で利用されることをテスト"""
    os.environ['GIT_EDITOR'] = 'my-git-editor'
    os.environ['VISUAL'] = 'my-visual'
    os.environ['EDITOR'] = 'my-editor'

    with patch('subprocess.run') as mock_run:
        # モックの実行。一時ファイルの読み出しはモック。
        with patch('builtins.open') as mock_open:
            mock_file = MagicMock()
            mock_file.readlines.return_value = ["Edited Message\n", "# Comment\n"]
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = launch_editor("Initial")
            assert result == "Edited Message"
            
            # subprocess.run が 'my-git-editor' を伴って呼ばれたことを確認
            args, kwargs = mock_run.call_args
            assert 'my-git-editor' in args[0]

def test_launch_editor_env_priority_visual():
    """GIT_EDITOR がなく VISUAL がある場合、それが利用されることをテスト"""
    os.environ['VISUAL'] = 'my-visual'
    os.environ['EDITOR'] = 'my-editor'

    with patch('subprocess.run') as mock_run:
        with patch('builtins.open') as mock_open:
            mock_file = MagicMock()
            mock_file.readlines.return_value = ["Edited Message"]
            mock_open.return_value.__enter__.return_value = mock_file
            
            launch_editor("Initial")
            args, kwargs = mock_run.call_args
            assert 'my-visual' in args[0]

def test_launch_editor_env_priority_editor():
    """GIT_EDITOR, VISUAL がなく EDITOR がある場合、それが利用されることをテスト"""
    os.environ['EDITOR'] = 'my-editor'

    with patch('subprocess.run') as mock_run:
        with patch('builtins.open') as mock_open:
            mock_file = MagicMock()
            mock_file.readlines.return_value = ["Edited Message"]
            mock_open.return_value.__enter__.return_value = mock_file
            
            launch_editor("Initial")
            args, kwargs = mock_run.call_args
            assert 'my-editor' in args[0]

def test_launch_editor_git_var_fallback():
    """環境変数が一切ない場合、git var GIT_EDITOR を試すことをテスト"""
    # mock git var GIT_EDITOR
    def mock_run_impl(cmd, *args, **kwargs):
        if cmd == ['git', 'var', 'GIT_EDITOR']:
            res = MagicMock()
            res.returncode = 0
            res.stdout = "git-configured-editor\n"
            return res
        # エディタの実行
        res = MagicMock()
        res.returncode = 0
        return res

    with patch('subprocess.run', side_effect=mock_run_impl) as mock_run:
        with patch('builtins.open') as mock_open:
            mock_file = MagicMock()
            mock_file.readlines.return_value = ["Edited Message"]
            mock_open.return_value.__enter__.return_value = mock_file
            
            launch_editor("Initial")
            # git var GIT_EDITOR が呼ばれ、その後に取得したエディタが呼ばれているはず
            calls = mock_run.call_args_list
            assert calls[0][0][0] == ['git', 'var', 'GIT_EDITOR']
            assert 'git-configured-editor' in calls[1][0][0]

@pytest.mark.parametrize("os_name,expected_fallback", [
    ('nt', 'notepad'),
    ('posix', 'vi')
])
def test_launch_editor_default_fallback(os_name, expected_fallback):
    """環境変数も git 設定もない場合、OSのデフォルトエディタが選択されることをテスト"""
    # git var GIT_EDITOR は例外を投げて失敗させる
    def mock_run_impl(cmd, *args, **kwargs):
        if 'git' in cmd:
            raise subprocess.SubprocessError("git error")
        res = MagicMock()
        res.returncode = 0
        return res

    with patch('os.name', os_name):
        with patch('subprocess.run', side_effect=mock_run_impl) as mock_run:
            with patch('builtins.open') as mock_open:
                mock_file = MagicMock()
                mock_file.readlines.return_value = ["Edited"]
                mock_open.return_value.__enter__.return_value = mock_file
                
                launch_editor("Initial")
                calls = mock_run.call_args_list
                # エディタの実行にデフォルトエディタが使われていることをアサート
                editor_cmd = calls[-1][0][0]
                assert expected_fallback in editor_cmd

def test_launch_editor_comment_strip():
    """#で始まるコメント行が編集後メッセージから正しく除外されることをテスト"""
    os.environ['EDITOR'] = 'dummy-editor'
    
    # 実際のNamedTemporaryFileをフックし、書き込まれた内容はそのままに、読み出される内容を偽装
    with patch('subprocess.run') as mock_run:
        with patch('builtins.open') as mock_open:
            mock_file = MagicMock()
            mock_file.readlines.return_value = [
                "feat: add login page\n",
                "\n",
                "# Please enter the commit message for your changes.\n",
                "# Lines starting with '#' will be ignored.\n",
                "detailed info\n"
            ]
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = launch_editor("Initial message")
            
            # コメント行が除外され、余白がストリップされていること
            assert result == "feat: add login page\n\ndetailed info"

def test_launch_editor_exception_recovery_and_cleanup():
    """エディタ起動中に例外が発生した場合、元のメッセージが返り、一時ファイルが確実に削除されることをテスト"""
    os.environ['EDITOR'] = 'non_existent_editor_command_xyz'
    
    # ファイル存在確認をパッチして確実に True にさせ、unlink が呼ばれるかテスト
    with patch('os.path.exists', return_value=True) as mock_exists:
        with patch('os.unlink') as mock_unlink:
            # subprocess.run は起動失敗例外を投げる
            with patch('subprocess.run', side_effect=FileNotFoundError("No such command")):
                
                result = launch_editor("Original Message")
                
                # 例外が発生しても元のメッセージが返ること
                assert result == "Original Message"
                # 一時ファイルが unlink で削除されていること
                mock_unlink.assert_called_once()
