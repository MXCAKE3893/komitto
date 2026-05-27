import pytest
import asyncio
import sys
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

from komitto.tui.app import KomittoApp

@pytest.fixture
def anyio_backend():
    return "asyncio"

# suspend() をダミーのコンテキストマネージャにするヘルパー
@contextmanager
def dummy_suspend():
    yield

@pytest.fixture(autouse=True)
def mock_llm_client():
    mock_client = MagicMock()
    # stream_commit_message は (chunk, usage) のイテレータを返すジェネレータ関数をモック
    def mock_stream(*args, **kwargs):
        yield "Mocked commit message", None
    mock_client.stream_commit_message.side_effect = mock_stream
    
    with patch("komitto.tui.app.create_llm_client", return_value=mock_client) as mock_factory:
        yield mock_client

@pytest.mark.anyio
async def test_komitto_app_initialization_single_mode():
    config = {"llm": {"provider": "openai"}}
    app = KomittoApp(config=config, prompt="test prompt")
    assert app.is_compare_mode is False
    assert app.prompt_text == "test prompt"

@pytest.mark.anyio
async def test_komitto_app_run_single(mock_llm_client):
    """シングルモードで起動し、自動的に生成されてレビュー画面に移行することをテスト"""
    config = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4"
        }
    }
    app = KomittoApp(config=config, prompt="test prompt")
    app.suspend = dummy_suspend  # suspend のモック化
    
    async with app.run_test() as pilot:
        # バックグラウンドの `@work` タスクが完了するのを待つ
        await app.workers.wait_for_complete()
        await pilot.pause()
        
        assert app.current_state == "review"
        assert app.generated_text == "Mocked commit message"

@pytest.mark.anyio
async def test_komitto_app_copy_action(mock_llm_client):
    """レビュー状態でコピーアクション (c キー) がクリップボードコピーを呼び出すことをテスト"""
    config = {"llm": {"provider": "openai"}}
    app = KomittoApp(config=config, prompt="test prompt")
    app.suspend = dummy_suspend  # suspend のモック化
    
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        
        with patch("komitto.tui.app.pyperclip.copy") as mock_copy:
            await pilot.press("c")
            mock_copy.assert_called_once_with("Mocked commit message")

@pytest.mark.anyio
async def test_komitto_app_edit_action(mock_llm_client):
    """編集アクション (e キー) でエディタが起動し、テキストが更新されることをテスト"""
    config = {"llm": {"provider": "openai"}}
    app = KomittoApp(config=config, prompt="test prompt")
    app.suspend = dummy_suspend  # suspend のモック化
    
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        
        with patch("komitto.tui.app.launch_editor", return_value="User edited message") as mock_launch:
            await pilot.press("e")
            await pilot.pause()
            mock_launch.assert_called_once_with("Mocked commit message")
            assert app.generated_text == "User edited message"

@pytest.mark.anyio
async def test_komitto_app_commit_action_success(mock_llm_client):
    """コミットアクション (y キー) が成功し、アプリが終了することをテスト"""
    config = {"llm": {"provider": "openai"}}
    app = KomittoApp(config=config, prompt="test prompt")
    app.suspend = dummy_suspend  # suspend のモック化
    
    # builtins.print をパッチして、UnicodeEncodeError を完全に防ぐ
    with patch("builtins.print") as mock_print:
        async with app.run_test() as pilot:
            await app.workers.wait_for_complete()
            await pilot.pause()
            
            app.exit = MagicMock()
            
            with patch("komitto.tui.app.git_commit", return_value=True) as mock_commit:
                with patch("time.sleep"):  # sleepをスキップして高速化
                    await pilot.press("y")
                    mock_commit.assert_called_once_with("Mocked commit message")
                    app.exit.assert_called_once()

@pytest.mark.anyio
async def test_komitto_app_run_compare():
    """比較モードで起動し、Option A と Option B の選択によって状態が遷移することをテスト"""
    compare_configs = [
        ("OptA", {"llm": {"provider": "openai"}}, "prompt_a"),
        ("OptB", {"llm": {"provider": "gemini"}}, "prompt_b")
    ]
    app = KomittoApp(compare_configs=compare_configs)
    app.suspend = dummy_suspend  # suspend のモック化
    
    mock_client_a = MagicMock()
    def mock_stream_a(*args, **kwargs):
        yield "Msg A from OpenAI", None
    mock_client_a.stream_commit_message.side_effect = mock_stream_a

    mock_client_b = MagicMock()
    def mock_stream_b(*args, **kwargs):
        yield "Msg B from Gemini", None
    mock_client_b.stream_commit_message.side_effect = mock_stream_b
    
    # create_llm_client に渡されるのは llm_config 辞書
    def side_effect(llm_cfg):
        if llm_cfg.get("provider") == "openai":
            return mock_client_a
        return mock_client_b

    with patch("komitto.tui.app.create_llm_client", side_effect=side_effect):
        async with app.run_test() as pilot:
            # バックグラウンドの `@work` スレッド処理が完了するのを待つ
            await app.workers.wait_for_complete()
            await pilot.pause()
            
            assert app.current_state == "compare"
            assert app.generated_text_a == "Msg A from OpenAI"
            assert app.generated_text_b == "Msg B from Gemini"
            
            await pilot.press("a")
            # 状態遷移とUI更新を待つ
            await pilot.pause()
            
            assert app.current_state == "review"
            assert app.generated_text == "Msg A from OpenAI"
            assert app.config == {"llm": {"provider": "openai"}}
