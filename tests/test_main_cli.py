import sys
import os
import pytest
from unittest.mock import patch, MagicMock

from komitto.main import get_key, generate_and_review, main

def test_get_key_windows():
    """Windows環境で msvcrt が使われ、キーが正常にデコードされて返されることをテスト"""
    mock_msvcrt = MagicMock()
    mock_msvcrt.getch.return_value = b'y'
    
    with patch("os.name", "nt"):
        with patch("komitto.main.msvcrt", mock_msvcrt, create=True):
            key = get_key()
            assert key == "y"
            mock_msvcrt.getch.assert_called_once()

def test_get_key_windows_decode_error():
    """Windows環境で getch がデコードエラーを起こした場合に、バイト列そのものが返ることをテスト"""
    mock_msvcrt = MagicMock()
    # デコードできない特殊キーバイト列
    mock_msvcrt.getch.return_value = b'\xff'
    
    with patch("os.name", "nt"):
        with patch("komitto.main.msvcrt", mock_msvcrt, create=True):
            key = get_key()
            assert key == b'\xff'

def test_get_key_unix():
    """Unix環境で termios/tty が使われ、1文字正しく読み込まれることをテスト"""
    mock_termios = MagicMock()
    mock_tty = MagicMock()
    mock_sys = MagicMock()
    mock_sys.stdin.fileno.return_value = 0
    mock_sys.stdin.read.return_value = 'n'
    
    with patch("os.name", "posix"):
        with patch("komitto.main.tty", mock_tty, create=True):
            with patch("komitto.main.termios", mock_termios, create=True):
                # sys.stdin の代わりにモックした sys をパッチ
                with patch("komitto.main.sys", mock_sys):
                    key = get_key()
                    assert key == "n"
                    mock_tty.setraw.assert_called_once_with(0)
                    mock_termios.tcsetattr.assert_called_once()

def test_generate_and_review_no_llm_config():
    """LLM設定がない場合に、警告メッセージを出力して即座に終了することをテスト"""
    config = {}
    args = MagicMock()
    
    with patch("komitto.main.console.print") as mock_print:
        result = generate_and_review(config, args, "sys_prompt", "final_prompt")
        assert result is None
        mock_print.assert_called_once()
        assert "api_error" in mock_print.call_args[0][0] or "API" in mock_print.call_args[0][0]

@patch("komitto.main.create_llm_client")
def test_generate_and_review_stream_error(mock_create_client):
    """LLM stream API の処理中に例外が発生した場合に、例外エラーを出力して None を返すことをテスト"""
    mock_client = MagicMock()
    mock_client.stream_commit_message.side_effect = Exception("API connection error")
    mock_create_client.return_value = mock_client
    
    config = {"llm": {"provider": "openai"}}
    args = MagicMock()
    
    with patch("komitto.main.console.print") as mock_print:
        result = generate_and_review(config, args, "sys_prompt", "final_prompt")
        assert result is None
        # エラーメッセージが表示されたこと
        assert any(isinstance(call[0][0], str) and "Error calling LLM API" in call[0][0] for call in mock_print.call_args_list if call[0])

@patch("komitto.main.create_llm_client")
@patch("komitto.main.get_key")
@patch("komitto.main.git_commit")
def test_generate_and_review_interactive_flow_commit(mock_git_commit, mock_get_key, mock_create_client):
    """インタラクティブレビューで 'y' を入力した際、コミットが実行され成功することをテスト"""
    # 1. LLM client の stream_commit_message のモック
    mock_client = MagicMock()
    mock_client.stream_commit_message.return_value = [("Generated commit message", None)]
    mock_create_client.return_value = mock_client
    
    # 2. キー入力のシミュレーション: 'y'
    mock_get_key.return_value = "y"
    
    # 3. コミット成否のシミュレーション: 成功
    mock_git_commit.return_value = True
    
    config = {"llm": {"provider": "openai"}}
    args = MagicMock()
    args.interactive = True
    args.compare = False
    
    with patch("builtins.print"):
        with patch("sys.stdout.flush"):
            with patch("komitto.main.pyperclip.copy") as mock_copy:
                result = generate_and_review(config, args, "sys_prompt", "final_prompt")
                
                assert result == "Generated commit message"
                mock_git_commit.assert_called_once_with("Generated commit message")
                mock_copy.assert_called_once_with("Generated commit message")

@patch("komitto.main.create_llm_client")
@patch("komitto.main.get_key")
@patch("komitto.main.launch_editor")
@patch("komitto.main.git_commit")
def test_generate_and_review_interactive_flow_edit_then_commit(mock_git_commit, mock_launch_editor, mock_get_key, mock_create_client):
    """インタラクティブレビューで 'e' を押して編集し、その後に 'y' でコミットすることをテスト"""
    mock_client = MagicMock()
    mock_client.stream_commit_message.return_value = [("Draft message", None)]
    mock_create_client.return_value = mock_client
    
    # キー入力シミュレーション: 1回目は 'e' (編集), 2回目は 'y' (採用)
    mock_get_key.side_effect = ["e", "y"]
    
    # エディタ編集結果
    mock_launch_editor.return_value = "Edited message"
    mock_git_commit.return_value = True
    
    config = {"llm": {"provider": "openai"}}
    args = MagicMock()
    args.interactive = True
    args.compare = False
    
    with patch("builtins.print"):
        with patch("sys.stdout.flush"):
            result = generate_and_review(config, args, "sys_prompt", "final_prompt")
            
            assert result == "Edited message"
            mock_launch_editor.assert_called_once_with("Draft message")
            mock_git_commit.assert_called_once_with("Edited message")

@patch("komitto.main.create_llm_client")
@patch("komitto.main.get_key")
@patch("os._exit")
def test_generate_and_review_interactive_flow_cancel(mock_exit, mock_get_key, mock_create_client):
    """インタラクティブレビューで 'n' を押した際、os._exit(0) が呼び出されることをテスト"""
    mock_client = MagicMock()
    mock_client.stream_commit_message.return_value = [("Draft message", None)]
    mock_create_client.return_value = mock_client
    
    mock_get_key.return_value = "n"
    mock_exit.side_effect = SystemExit
    
    config = {"llm": {"provider": "openai"}}
    args = MagicMock()
    args.interactive = True
    args.compare = False
    
    with patch("builtins.print"):
        with patch("sys.stdout.flush"):
            with pytest.raises(SystemExit):
                generate_and_review(config, args, "sys_prompt", "final_prompt")
            mock_exit.assert_called_once_with(0)

# ==============================================================================
# main() 結合/引数分岐テスト
# ==============================================================================

@patch("komitto.main.init_config")
def test_main_subcommand_init(mock_init_config):
    """'komitto init' 引数が指定された場合に init_config が呼び出されることをテスト"""
    with patch("sys.argv", ["komitto", "init"]):
        main()
        mock_init_config.assert_called_once()

@patch("komitto.main.load_config")
@patch("komitto.main.resolve_config")
@patch("komitto.learn.learn_style_from_history")
def test_main_subcommand_learn(mock_learn, mock_resolve, mock_load):
    """'komitto learn' 引数が指定された場合に learn_style_from_history が呼びされることをテスト"""
    mock_load.return_value = {}
    mock_resolve.return_value = {"resolved_config": True}
    
    with patch("sys.argv", ["komitto", "learn"]):
        main()
        mock_learn.assert_called_once_with({"resolved_config": True})

@patch("komitto.main.load_config")
@patch("komitto.main.resolve_config")
@patch("komitto.main.get_git_diff", return_value="my diff")
@patch("komitto.main.get_git_log", return_value="my logs")
@patch("komitto.main.build_prompt", return_value="final prompt text")
@patch("komitto.main.pyperclip.copy")
def test_main_standard_no_llm_flow(mock_copy, mock_build, mock_log, mock_diff, mock_resolve, mock_load):
    """標準実行（LLM設定なし）の際、プロンプトが自動生成されてクリップボードにコピーされることをテスト"""
    # llm 設定を空（プロバイダなし）にして、クリップボードコピーへフォールバックさせる
    mock_load.return_value = {}
    mock_resolve.return_value = {
        "git": {"exclude": []},
        "prompt": {"system": "my system prompt"}
    }
    
    with patch("sys.argv", ["komitto"]):
        main()
        
        mock_diff.assert_called_once_with(exclude_patterns=[])
        mock_log.assert_called_once_with(limit=5)
        mock_build.assert_called_once_with("my system prompt", "my logs", "", "my diff", None)
        mock_copy.assert_called_once_with("final prompt text")

@patch("komitto.main.load_config")
@patch("komitto.main.resolve_config")
@patch("komitto.main.get_git_diff", return_value="my diff")
@patch("komitto.main.get_git_log", return_value="my logs")
@patch("komitto.main.build_prompt", return_value="final prompt text")
@patch("komitto.main.generate_and_review")
def test_main_standard_llm_flow(mock_generate_review, mock_build, mock_log, mock_diff, mock_resolve, mock_load):
    """標準実行（LLM設定あり）の際、自動で generate_and_review が呼び出されることをテスト"""
    mock_load.return_value = {}
    mock_resolve.return_value = {
        "git": {"exclude": ["*.lock"]},
        "llm": {"provider": "openai", "history_limit": 10},
        "prompt": {"system": "my system prompt"}
    }
    
    with patch("sys.argv", ["komitto"]):
        main()
        
        mock_diff.assert_called_once_with(exclude_patterns=["*.lock"])
        mock_log.assert_called_once_with(limit=10)
        mock_generate_review.assert_called_once()
        # 解決された config が generate_and_review に渡されていること
        passed_config = mock_generate_review.call_args[0][0]
        assert passed_config["llm"]["provider"] == "openai"
