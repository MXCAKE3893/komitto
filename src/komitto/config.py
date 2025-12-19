import sys
from pathlib import Path
import platformdirs
import copy

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .i18n import t

def load_config():
    """
    設定ファイルを読み込み、設定辞書を返す。
    読み込み順序（後勝ち）:
    1. デフォルト設定
    2. OS標準のユーザー設定ディレクトリ (e.g., AppData/Roaming/komitto/config.toml)
    3. カレントディレクトリ (./komitto.toml)
    """
    config = {
        "prompt": {
            "system": t("config.system_prompt")
        },
        "git": {
            "exclude": [
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "poetry.lock",
                "Cargo.lock",
                "go.sum",
                "*.lock"
            ]
        }
    }

    config_paths = []

    # 1. ユーザー設定 (OS標準)
    # Windows: C:\Users\<User>\AppData\Roaming\komitto\config.toml
    # macOS: /Users/<User>/Library/Application Support/komitto/config.toml
    # Linux: /home/<User>/.config/komitto/config.toml
    user_config_dir = platformdirs.user_config_dir("komitto", roaming=True)
    config_paths.append(Path(user_config_dir) / "config.toml")

    # 2. カレントディレクトリ
    config_paths.append(Path.cwd() / "komitto.toml")

    for path in config_paths:
        if path.exists():
            try:
                with open(path, "rb") as f:
                    toml_data = tomllib.load(f)
                    
                    # 辞書のマージ処理
                    for key, value in toml_data.items():
                        if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                            config[key].update(value)
                        else:
                            config[key] = value
                            
            except Exception as e:
                # 警告を表示するが処理は続行
                print(t("config.load_warning", path, e), file=sys.stderr)

    return config

def resolve_config(config, context_name=None, template_name=None, model_name=None):
    """
    指定されたコンテキスト、テンプレート、モデルに基づいて設定を解決・マージした新しい設定辞書を返す。
    """
    resolved_config = copy.deepcopy(config)
    
    target_template = template_name
    target_model = model_name

    if context_name:
        contexts = config.get("contexts", {})
        if context_name in contexts:
            ctx = contexts[context_name]
            if not target_template and "template" in ctx:
                target_template = ctx["template"]
            if not target_model and "model" in ctx:
                target_model = ctx["model"]

    if target_template:
        templates = config.get("templates", {})
        if target_template in templates:
            tmpl = templates[target_template]
            if "system" in tmpl:
                resolved_config.setdefault("prompt", {})["system"] = tmpl["system"]
            for k, v in tmpl.items():
                if k != "system":
                     resolved_config["prompt"][k] = v

    if target_model:
        models = config.get("models", {})
        if target_model in models:
            mdl = models[target_model]
            resolved_config["llm"] = resolved_config.get("llm", {}).copy()
            resolved_config["llm"].update(mdl)

    return resolved_config

def init_config():
    """設定ファイルの雛形をカレントディレクトリに生成する"""
    target_file = Path("komitto.toml")
    if target_file.exists():
        print(t("config.init_exists"))
        return

    content = f"""[prompt]
# System Prompt Settings
# You can overwrite the default prompt with the following settings.
# システムプロンプトの設定
# 以下の設定でデフォルトのプロンプトを上書きできます。

system = \"\"\"
{t("config.system_prompt").strip()}
\"\"\"

# [llm]
# # Uncomment and configure below to use AI auto-generation
# # AI自動生成を使用する場合は以下をコメントアウト解除して設定してください
# provider = "openai" # "openai", "gemini", "anthropic"
# model = "gpt-4o"
# # api_key = "sk-..." # Optional if environment variable is set / 省略時は環境変数を使用
# # base_url = "http://localhost:11434/v1" # For Ollama etc. / Ollamaなどの場合
# # history_limit = 5 # Number of past commits to include / プロンプトに含める過去のコミット数

[git]
# Files to exclude from the diff (glob patterns)
# 差分から除外するファイル（globパターン）
exclude = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
    "go.sum",
    "*.lock"
]

# --- Advanced Settings (Templates & Contexts) ---
# You can define reusable templates and contexts for different workflows.
# テンプレートやコンテキストを定義して、用途に応じて使い分けることができます。

# [templates.simple]
# system = "Summarize changes in one line."

# [models.gpt4]
# provider = "openai"
# model = "gpt-4o"

# [contexts.release]
# template = "simple"
# model = "gpt4"
# # usage: komitto -c release
"""
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(t("config.init_created", target_file))
    except Exception as e:
        print(t("config.init_failed", target_file, e), file=sys.stderr)
        sys.exit(1)

