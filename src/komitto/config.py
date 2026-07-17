import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Optional
from urllib.parse import urlparse

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .i18n import t

SCHEMA_URL = "https://raw.githubusercontent.com/MXCAKE3893/komitto/main/schema/komitto-config.schema.json"
CONFIG_ROOT_NAME = ".config"
CONFIG_APP_NAME = "komitto"


def get_config_root() -> Path:
    return Path.home() / CONFIG_ROOT_NAME / CONFIG_APP_NAME


def get_global_config_path() -> Path:
    return get_config_root() / "config.json"


def get_local_config_path() -> Path:
    return Path.cwd() / "komitto.json"


def _run_git(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, encoding="utf-8", check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _normalize_repository_identifier(value: str) -> str:
    value = value.strip().replace("\\", "/")
    if value.startswith("git@") and ":" in value:
        host_and_path = value[4:].replace(":", "/", 1)
    else:
        parsed = urlparse(value)
        host_and_path = f"{parsed.hostname or ''}{parsed.path}" if parsed.scheme else value
    return re.sub(r"\.git/?$", "", host_and_path).strip("/").lower()


def get_repository_id() -> str:
    remote = _run_git("remote", "get-url", "origin")
    identity = _normalize_repository_identifier(remote) if remote else None
    if not identity:
        identity = _run_git("rev-parse", "--show-toplevel") or str(Path.cwd().resolve())
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def get_repository_prompt_path() -> Path:
    return get_config_root() / "repos" / get_repository_id() / "system.md"


def _default_config() -> dict:
    return {
        "prompt": {"source": "repository", "system": t("config.system_prompt")},
        "context": {"files": []},
        "git": {
            "exclude": [
                "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
                "Cargo.lock", "go.sum", "*.lock",
            ]
        },
    }


def _merge_config(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key == "$schema" or key == "api_key":
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_config(base[key], value)
        else:
            base[key] = value


def _read_json_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def _strip_api_keys(value):
    if isinstance(value, dict):
        return {key: _strip_api_keys(item) for key, item in value.items() if key != "api_key"}
    if isinstance(value, list):
        return [_strip_api_keys(item) for item in value]
    return value


def _sanitize_user_config(config: dict) -> dict:
    sanitized = _strip_api_keys(config)
    prompt = sanitized.get("prompt")
    if isinstance(prompt, dict):
        prompt.pop("system", None)
    return sanitized


def _write_json(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _migrate_toml(toml_path: Path, json_path: Path, is_local: bool) -> None:
    if json_path.exists() or not toml_path.exists():
        return
    try:
        with toml_path.open("rb") as file:
            legacy_config = tomllib.load(file)
        prompt = legacy_config.get("prompt", {})
        system_prompt = prompt.pop("system", None) if isinstance(prompt, dict) else None
        if system_prompt:
            prompt["source"] = "repository"
            _write_prompt(system_prompt)
        migrated = _sanitize_user_config(legacy_config)
        migrated["$schema"] = SCHEMA_URL
        _write_json(json_path, migrated)
        if _contains_api_key(legacy_config):
            print(
                f"Warning: omitted api_key while migrating {toml_path}; set it in {get_config_root() / '.env'}.",
                file=sys.stderr,
            )
    except Exception as error:
        print(t("config.load_warning", toml_path, error), file=sys.stderr)


def _contains_api_key(value) -> bool:
    if isinstance(value, dict):
        return "api_key" in value or any(_contains_api_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_api_key(item) for item in value)
    return False


def load_dotenv() -> None:
    dotenv_path = get_config_root() / ".env"
    if not dotenv_path.exists():
        return
    try:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)
    except OSError as error:
        print(t("config.load_warning", dotenv_path, error), file=sys.stderr)


def _write_prompt(content: str) -> Path:
    target = get_repository_prompt_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")
    return target


def _load_repository_prompt(config: dict) -> None:
    source = config.get("prompt", {}).get("source", "repository")
    if source != "repository":
        return
    path = get_repository_prompt_path()
    if not path.exists():
        return
    try:
        config.setdefault("prompt", {})["system"] = path.read_text(encoding="utf-8")
    except OSError as error:
        print(t("config.load_warning", path, error), file=sys.stderr)


def load_config() -> dict:
    """Load global and local JSON configuration; local values override global values."""
    load_dotenv()
    global_json = get_global_config_path()
    local_json = get_local_config_path()
    _migrate_toml(get_config_root() / "config.toml", global_json, is_local=False)
    _migrate_toml(Path.cwd() / "komitto.toml", local_json, is_local=True)

    config = _default_config()
    for path in (global_json, local_json):
        if not path.exists():
            continue
        try:
            _merge_config(config, _sanitize_user_config(_read_json_config(path)))
        except Exception as error:
            print(t("config.load_warning", path, error), file=sys.stderr)
    _load_repository_prompt(config)
    return config


def _initial_local_config() -> dict:
    return {
        "$schema": SCHEMA_URL,
        "prompt": {"source": "repository"},
        "context": {"files": []},
        "git": {"exclude": _default_config()["git"]["exclude"]},
    }


def _write_dotenv_example() -> None:
    example = get_config_root() / ".env.example"
    if not example.exists():
        example.parent.mkdir(parents=True, exist_ok=True)
        example.write_text(
            "# Copy this file to .env and set only the provider keys you use.\n"
            "OPENAI_API_KEY=\nGEMINI_API_KEY=\nANTHROPIC_API_KEY=\n",
            encoding="utf-8",
        )


def init_config() -> None:
    """Create local JSON configuration and the repository-specific prompt file."""
    target = get_local_config_path()
    if target.exists():
        print(t("config.init_exists"))
        return
    try:
        _write_json(target, _initial_local_config())
        prompt_path = get_repository_prompt_path()
        if not prompt_path.exists():
            _write_prompt(t("config.system_prompt"))
        _write_dotenv_example()
        print(t("config.init_created", target))
    except Exception as error:
        print(t("config.init_failed", target, error), file=sys.stderr)
        sys.exit(1)


def init_config_with_prompt(suggestion: str):
    """Create or update the repository-specific Markdown prompt and local JSON config."""
    target = get_local_config_path()
    is_new = not target.exists()
    try:
        if target.exists():
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup = target.with_name(f"{target.name}.{timestamp}.backup")
            shutil.copy2(target, backup)
            config = _read_json_config(target)
        else:
            backup = None
            config = _initial_local_config()
        config["$schema"] = SCHEMA_URL
        config["prompt"] = {"source": "repository"}
        _write_json(target, _sanitize_user_config(config))
        prompt_path = _write_prompt(suggestion)
        _write_dotenv_example()
        return True, str(prompt_path if is_new else backup), is_new
    except Exception as error:
        return False, str(error), is_new


def resolve_config(config, context_name=None, template_name=None, model_name=None):
    resolved_config = copy.deepcopy(config)
    target_template = template_name
    target_model = model_name

    if context_name:
        context = config.get("contexts", {}).get(context_name)
        if context:
            target_template = target_template or context.get("template")
            target_model = target_model or context.get("model")

    if target_template:
        template = config.get("templates", {}).get(target_template)
        if template:
            _merge_config(resolved_config.setdefault("prompt", {}), template)

    if target_model:
        model = config.get("models", {}).get(target_model)
        if model:
            _merge_config(resolved_config.setdefault("llm", {}), model)
    return resolved_config
