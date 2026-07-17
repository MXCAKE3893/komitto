import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from komitto.config import (
    SCHEMA_URL,
    get_config_root,
    get_global_config_path,
    get_local_config_path,
    get_repository_id,
    get_repository_prompt_path,
    init_config,
    init_config_with_prompt,
    load_config,
    resolve_config,
)


@pytest.fixture
def temp_cwd(tmp_path):
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)


@pytest.fixture
def config_root(tmp_path):
    root = tmp_path / ".config" / "komitto"
    with patch("komitto.config.get_config_root", return_value=root):
        yield root


def test_config_paths_use_json(temp_cwd, config_root):
    assert get_global_config_path() == config_root / "config.json"
    assert get_local_config_path() == temp_cwd / "komitto.json"


def test_load_config_local_overrides_global(temp_cwd, config_root):
    global_config = config_root / "config.json"
    global_config.parent.mkdir(parents=True)
    global_config.write_text(json.dumps({"llm": {"model": "global"}, "context": {"files": ["GLOBAL.md"]}}), encoding="utf-8")
    (temp_cwd / "komitto.json").write_text(json.dumps({"llm": {"model": "local"}}), encoding="utf-8")

    config = load_config()

    assert config["llm"]["model"] == "local"
    assert config["context"]["files"] == ["GLOBAL.md"]


def test_repository_prompt_overrides_default(temp_cwd, config_root):
    with patch("komitto.config.get_repository_id", return_value="repo-id"):
        prompt_path = get_repository_prompt_path()
        prompt_path.parent.mkdir(parents=True)
        prompt_path.write_text("Repository prompt", encoding="utf-8")
        assert load_config()["prompt"]["system"] == "Repository prompt"


def test_repository_id_uses_normalized_origin():
    with patch("komitto.config._run_git", return_value="git@github.com:Owner/Repo.git"):
        first = get_repository_id()
    with patch("komitto.config._run_git", return_value="https://github.com/owner/repo.git"):
        second = get_repository_id()
    assert first == second
    assert len(first) == 64


def test_toml_is_migrated_without_api_key(temp_cwd, config_root):
    legacy = temp_cwd / "komitto.toml"
    legacy.write_text('[llm]\nprovider = "openai"\napi_key = "secret"\n[prompt]\nsystem = "Legacy prompt"\n', encoding="utf-8")

    with patch("komitto.config.get_repository_id", return_value="repo-id"):
        config = load_config()
        migrated = json.loads((temp_cwd / "komitto.json").read_text(encoding="utf-8"))
        prompt = get_repository_prompt_path().read_text(encoding="utf-8")

    assert config["llm"]["provider"] == "openai"
    assert "api_key" not in migrated["llm"]
    assert migrated["$schema"] == SCHEMA_URL
    assert prompt == "Legacy prompt\n"


def test_json_prompt_and_api_key_are_ignored(temp_cwd, config_root):
    (temp_cwd / "komitto.json").write_text(
        json.dumps({"prompt": {"system": "Do not load"}, "llm": {"api_key": "secret"}}),
        encoding="utf-8",
    )

    config = load_config()

    assert config["prompt"]["system"] != "Do not load"
    assert "api_key" not in config.get("llm", {})


def test_dotenv_does_not_override_existing_environment(temp_cwd, config_root, monkeypatch):
    config_root.mkdir(parents=True)
    (config_root / ".env").write_text("OPENAI_API_KEY=from-file\nGEMINI_API_KEY=gemini\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "from-environment")

    load_config()

    assert os.environ["OPENAI_API_KEY"] == "from-environment"
    assert os.environ["GEMINI_API_KEY"] == "gemini"


def test_init_creates_json_prompt_and_dotenv_example(temp_cwd, config_root):
    with patch("komitto.config.get_repository_id", return_value="repo-id"):
        init_config()
        config = json.loads((temp_cwd / "komitto.json").read_text(encoding="utf-8"))
        prompt_path = get_repository_prompt_path()

    assert config["$schema"] == SCHEMA_URL
    assert config["prompt"] == {"source": "repository"}
    assert prompt_path.exists()
    assert (config_root / ".env.example").exists()


def test_learn_prompt_updates_markdown_not_json(temp_cwd, config_root):
    with patch("komitto.config.get_repository_id", return_value="repo-id"):
        success, path, is_new = init_config_with_prompt("Learned prompt")
        config = json.loads((temp_cwd / "komitto.json").read_text(encoding="utf-8"))
        prompt = get_repository_prompt_path().read_text(encoding="utf-8")

    assert success and is_new
    assert path.endswith("system.md")
    assert config["prompt"] == {"source": "repository"}
    assert prompt == "Learned prompt\n"


def test_learn_uses_timestamped_backup(temp_cwd, config_root):
    with patch("komitto.config.get_repository_id", return_value="repo-id"):
        init_config()
        success, backup_path, is_new = init_config_with_prompt("Updated prompt")

    backup = Path(backup_path)
    assert success and not is_new
    assert backup.name.startswith("komitto.json.")
    assert backup.name.endswith(".backup")
    assert backup.exists()


def test_resolve_config_does_not_mutate_source():
    base = {"prompt": {"system": "Default"}, "templates": {"short": {"system": "Short"}}}
    resolved = resolve_config(base, template_name="short")
    assert resolved["prompt"]["system"] == "Short"
    assert base["prompt"]["system"] == "Default"
