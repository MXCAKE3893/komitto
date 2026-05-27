import os
import sys
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from komitto.config import (
    load_config,
    resolve_config,
    init_config,
    init_config_with_prompt,
    _build_toml_content
)

# 一時ディレクトリにカレントディレクトリを切り替えるフィクスチャ
@pytest.fixture
def temp_cwd(tmp_path):
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(orig_cwd)

def test_load_config_defaults(temp_cwd):
    """設定ファイルがない場合、デフォルトの設定が読み込まれることをテスト"""
    # platformdirs の user_config_dir が存在しないパスを返すようにモック
    with patch("platformdirs.user_config_dir", return_value=str(temp_cwd / "fake_user_config")):
        config = load_config()
        
        assert isinstance(config, dict)
        assert "prompt" in config
        assert "system" in config["prompt"]
        assert "git" in config
        assert isinstance(config["git"]["exclude"], list)

def test_load_config_merging(temp_cwd):
    """ユーザー設定とカレントディレクトリ設定が順番に上書きマージされることをテスト"""
    user_config_dir = temp_cwd / "user_config"
    user_config_dir.mkdir()
    
    # 1. ユーザー設定ファイル作成
    user_config_file = user_config_dir / "config.toml"
    user_config_file.write_text("""
[prompt]
system = "User System Prompt"
custom_key = "User Value"
""", encoding="utf-8")
    
    # 2. プロジェクト設定ファイル作成 (カレントディレクトリ)
    project_config_file = temp_cwd / "komitto.toml"
    project_config_file.write_text("""
[prompt]
custom_key = "Project Value"
another_key = "Project Extra"
[llm]
provider = "openai"
""", encoding="utf-8")

    with patch("platformdirs.user_config_dir", return_value=str(user_config_dir)):
        config = load_config()
        
        # ユーザー設定がマージされていること
        assert config["prompt"]["system"] == "User System Prompt"
        # プロジェクト設定で上書きされていること (User Value -> Project Value)
        assert config["prompt"]["custom_key"] == "Project Value"
        # プロジェクト独自のキーが追加されていること
        assert config["prompt"]["another_key"] == "Project Extra"
        # LLM設定が存在すること
        assert config["llm"]["provider"] == "openai"

def test_load_config_broken_toml(temp_cwd):
    """TOMLの構文が壊れている場合に、警告を表示しデフォルトにフォールバックすることをテスト"""
    project_config_file = temp_cwd / "komitto.toml"
    # 不正なTOML（クォートが閉じていないなど）
    project_config_file.write_text("""
[prompt]
system = "Unclosed quote
""", encoding="utf-8")

    with patch("platformdirs.user_config_dir", return_value=str(temp_cwd / "fake_user_config")):
        with patch("sys.stderr.write") as mock_stderr:
            config = load_config()
            
            # デフォルトが返っていること
            assert "prompt" in config
            # エラー出力が発生していること
            assert any("Warning: Failed to load config" in call[0][0] or "config.load_warning" in call[0][0] for call in mock_stderr.call_args_list if call[0])

def test_load_config_permission_error(temp_cwd):
    """設定ファイルのロード中に例外（権限エラーなど）が発生した場合にクラッシュしないことをテスト"""
    project_config_file = temp_cwd / "komitto.toml"
    project_config_file.touch()

    # open に PermissionError を発生させるパッチ
    original_open = open
    def mock_open(file, *args, **kwargs):
        if Path(file).name == "komitto.toml":
            raise PermissionError("Access denied")
        return original_open(file, *args, **kwargs)

    with patch("platformdirs.user_config_dir", return_value=str(temp_cwd / "fake_user_config")):
        with patch("builtins.open", side_effect=mock_open):
            with patch("sys.stderr.write") as mock_stderr:
                config = load_config()
                # クラッシュせずデフォルト設定が返る
                assert "prompt" in config
                # 警告が出力されること
                assert any("PermissionError" in call[0][0] or "Access denied" in call[0][0] for call in mock_stderr.call_args_list if call[0])

def test_resolve_config_complex():
    """resolve_config がコンテキスト、テンプレート、モデル設定を正しくマージ解決することをテスト"""
    base_config = {
        "prompt": {
            "system": "Default System"
        },
        "contexts": {
            "release": {
                "template": "simple",
                "model": "gpt4"
            },
            "incomplete": {
                "model": "non_existent_model"
            }
        },
        "templates": {
            "simple": {
                "system": "Simple Prompt System",
                "temperature": 0.2
            }
        },
        "models": {
            "gpt4": {
                "provider": "openai",
                "model": "gpt-4"
            }
        }
    }

    # 1. コンテキスト経由での解決 (template & model)
    res = resolve_config(base_config, context_name="release")
    assert res["prompt"]["system"] == "Simple Prompt System"
    assert res["prompt"]["temperature"] == 0.2
    assert res["llm"]["provider"] == "openai"
    assert res["llm"]["model"] == "gpt-4"

    # 2. 直接パラメータを指定した解決 (ベース値の上書き優先順位)
    res_direct = resolve_config(
        base_config,
        context_name="release",
        template_name="non_existent_template",  # 存在しないので無視
        model_name="direct_model"               # models にないが引数でモデルが指定された場合
    )
    # context のモデル (gpt4) より、直接指定された model_name (modelsにないためマージは発生しないが、直に引き継がれはしない。modelsにあるものしか適用されない)
    # 実装：model_nameがmodelsにあれば resolved_config["llm"] = mdl
    # modelsにない場合はマージ処理がスキップされるため、context_a の model 設定も適用されない（target_model = "direct_model" に上書きされるため）
    assert "llm" not in res_direct  # direct_model が models に定義されていないため llm セクションは生成されない

    # 3. 存在しないコンテキストが指定された場合は元のまま
    res_unknown = resolve_config(base_config, context_name="unknown")
    assert res_unknown["prompt"]["system"] == "Default System"
    assert "llm" not in res_unknown

def test_init_config_new(temp_cwd):
    """init_config が新規に komitto.toml を作成することをテスト"""
    target = Path("komitto.toml")
    assert not target.exists()
    
    with patch("sys.stdout.write") as mock_stdout:
        init_config()
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "[prompt]" in content
        assert "[git]" in content

def test_init_config_already_exists(temp_cwd):
    """すでに komitto.toml が存在する場合、上書きせずメッセージを出力することをテスト"""
    target = Path("komitto.toml")
    target.write_text("existing content", encoding="utf-8")
    
    with patch("sys.stdout.write") as mock_stdout:
        init_config()
        assert target.read_text(encoding="utf-8") == "existing content"
        # 既に存在している旨のメッセージが出力されること
        assert any("already exists" in call[0][0] or "config.init_exists" in call[0][0] for call in mock_stdout.call_args_list if call[0])

def test_init_config_write_error(temp_cwd):
    """init_config 中に書き込みエラーが発生した場合、sys.exit(1) で終了することをテスト"""
    # ファイル書き込みでエラーを起こすためにopenをモック
    with patch("builtins.open", side_effect=IOError("Write failed")):
        with pytest.raises(SystemExit) as exec_info:
            init_config()
        assert exec_info.value.code == 1

def test_init_config_with_prompt_new(temp_cwd):
    """init_config_with_prompt が新規作成の場合に正しくプロンプトを埋め込んでファイルを作成することをテスト"""
    target = Path("komitto.toml")
    assert not target.exists()
    
    success, filepath, is_new = init_config_with_prompt("My Suggestion Prompt")
    assert success is True
    assert is_new is True
    assert filepath == str(target)
    assert target.exists()
    
    content = target.read_text(encoding="utf-8")
    assert 'system = """\nMy Suggestion Prompt\n"""' in content.replace('\r\n', '\n')

def test_init_config_with_prompt_existing_backup(temp_cwd):
    """すでに設定ファイルが存在する場合、バックアップを作成してシステムプロンプトのみ書き換えることをテスト"""
    target = Path("komitto.toml")
    target.write_text("""
[prompt]
system = "Old Prompt"
custom_prompt_key = "keep_me"

[llm]
provider = "openai"

[git]
exclude = ["*.log"]
""", encoding="utf-8")

    success, backup_path, is_new = init_config_with_prompt("New Suggestion")
    assert success is True
    assert is_new is False
    # バックアップファイルが作成されていること
    assert Path(backup_path).exists()
    assert "komitto.toml.backup" in backup_path
    
    # 既存の中身が退避されていること
    backup_content = Path(backup_path).read_text(encoding="utf-8")
    assert "Old Prompt" in backup_content
    
    # komitto.toml の system プロンプトが書き換わっており、他の設定（custom_prompt_key, llm, git）が保持されていること
    new_content = target.read_text(encoding="utf-8")
    assert "New Suggestion" in new_content
    assert "Old Prompt" not in new_content
    assert "keep_me" in new_content
    assert "provider = 'openai'" in new_content or 'provider = "openai"' in new_content
    assert "*.log" in new_content

def test_init_config_with_prompt_write_error(temp_cwd):
    """書き込み不可な状態など、例外発生時にFalseとエラーメッセージを返すことをテスト"""
    target = Path("komitto.toml")
    # ディレクトリとして作成しておくことで書き込みエラーを引き起こす
    target.mkdir()
    
    success, err_msg, is_new = init_config_with_prompt("Suggestion")
    assert success is False
    assert len(err_msg) > 0

def test_build_toml_content_serialization():
    """_build_toml_content が辞書から正しい構造の TOML 文字列をシリアライズすることをテスト"""
    config = {
        "prompt": {
            "system": "Hello",
            "temperature": 0.7
        },
        "llm": {
            "provider": "gemini",
            "model": "gemini-3.5-flash"
        },
        "git": {
            "exclude": ["*.tmp", "dist/"]
        },
        "templates": {
            "t1": {"system": "T1 system"}
        }
    }
    
    toml_str = _build_toml_content(config, "New Hello")
    
    # systemプロンプトが更新されていること
    assert "New Hello" in toml_str
    # 辞書値が反映されていること
    assert "temperature = 0.7" in toml_str
    assert "provider = 'gemini'" in toml_str or 'provider = "gemini"' in toml_str
    assert "exclude = [" in toml_str
    assert '"*.tmp",' in toml_str or "'*.tmp'," in toml_str
    assert "[templates.t1]" in toml_str
    assert "system = 'T1 system'" in toml_str or 'system = "T1 system"' in toml_str
