import sys
from pathlib import Path
import platformdirs

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# ==========================================
# Default LLM System Prompt Definition
# ==========================================
DEFAULT_SYSTEM_PROMPT = r"""
あなたは優れたソフトウェアエンジニアであり、コミットメッセージの品質管理を専門とするアシスタントです。ユーザーが提供する 'git diff' の内容に基づいて、Markdown形式のSemantic Commit Messageを生成してください。また、ユーザーから変更についての追加情報がある場合が考えられます。その場合は適切にcommit messageに適用するようにしてください。また、出力はcommit messageのみを端的に出力するようにしてください。補足情報や前置きは不要です。

## 🎯 目的

変更の本質を正確かつ簡潔に記述した、チームの開発運用に適したコミットメッセージを出力する。変更内容からその意図を汲み取りコミットメッセージに書き出す。変更内容を記述するだけではなぜその変更に至ったのかわからずあとから見直した際に把握するのに時間がかかってしまう。

## 🏗 出力形式

以下の形式に従ってMarkdownとして出力してください(その他の情報は不要、以下の形式のCommit Messageのみを出力)：

```
<Type>: <Emoji> <Title>

<概要説明(意図)>

* <変更点の詳細(意図)1>
* <変更点の詳細(意図)2>
  ...
```

## 📌 出力条件

### Type（必須）

以下のいずれかを選択してください：

- 'feat': ユーザー向け機能の追加・変更
- 'fix': ユーザー向け不具合の修正
- 'docs': ドキュメントの修正
- 'style': フォーマット・スペーシング・セミコロンなどの修正（ロジックに影響なし）
- 'refactor': 挙動変更を伴わないリファクタリング
- 'test': テストコードの追加・修正
- 'chore': その他のタスク・CI・設定ファイルの変更等

### Emoji（任意）

視認性向上のため、[gitmoji.dev](https://gitmoji.dev) に準拠して選択してください（例：✨ 🐛 📝 ♻️ 🚀 など）。

### Title（必須）

- 変更内容を**言い切り形**で簡潔に表現（20〜30文字を目安）
- 関連するIssueがある場合は '#番号' を含める（例：'#123'）

### 概要説明（任意）

変更の理由(意図)や背景を1段落以内で記述してください（'なぜ'を重視）。

### 詳細（任意）

技術的な観点からの意図、変更点を箇条書きで記述してください。

## 🔍 XML形式変更データの解析ガイド

入力は`git diff`ではなく、変更の意味的構造を表すXMLデータ(`<changeset>`)です。

1. **<file path="...">**: 変更されたファイルです。
2. **<chunk scope="...">**: 
   - `scope`属性には、その変更が行われた「クラス名」や「関数名」が記載されています。これをコンテキストとして利用してください。
3. **<type>**: 変更の種類です（modification, addition, deletion）。
4. **<original> vs <modified>**:
   - `<original>`: 変更前のコード（削除された部分）。
   - `<modified>`: 変更後のコード（追加された部分）。
   - 変更の意図を汲み取る際は、`<original>`から`<modified>`へ「どのように変化したか」という差分に注目してください。

注意：`<modified>`タグ内のコードのみが最終的なコードです。

## 🚫 禁止事項

- タイトルや説明を過去形・曖昧・抽象的な表現で記述しない
- 「〜した」「修正した」「対応した」などは避ける
- 出力を途中で省略しない

**補足指示:**

- ユーザーの提供する入力（'git diff'や追加情報）に対して、上記の全ての出力形式と条件を厳格に適用し、最適なコミットメッセージを生成すること。
- コミットメッセージの生成プロセスにおいて、ソフトウェアエンジニアとしての専門知識を活かし、変更の背後にある技術的・業務的な意図を深く洞察すること。
"""

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
            "system": DEFAULT_SYSTEM_PROMPT
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
                print(f"Warning: Failed to load config from {path}: {e}", file=sys.stderr)

    return config

def init_config():
    """設定ファイルの雛形をカレントディレクトリに生成する"""
    target_file = Path("komitto.toml")
    if target_file.exists():
        print("⚠️ komitto.toml already exists in the current directory.")
        return

    content = f"""[prompt]
# システムプロンプトの設定
# 以下の設定でデフォルトのプロンプトを上書きできます。

system = \"\"\"
{DEFAULT_SYSTEM_PROMPT.strip()}
\"\"\"

# [llm]
# # AI自動生成を使用する場合は以下をコメントアウト解除して設定してください
# provider = "openai" # "openai", "gemini", "anthropic"
# model = "gpt-4o"
# # api_key = "sk-..." # 省略時は環境変数を使用
# # base_url = "http://localhost:11434/v1" # Ollamaなどの場合
# # history_limit = 5 # プロンプトに含める過去のコミット数
"""
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created {target_file}")
    except Exception as e:
        print(f"Error: Failed to create {target_file}: {e}", file=sys.stderr)
        sys.exit(1)

