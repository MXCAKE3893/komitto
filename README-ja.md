# komitto (commit)

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/komitto?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=BRIGHTGREEN&left_text=downloads)](https://pepy.tech/projects/komitto)

[English](https://github.com/mxcake3893/komitto/blob/main/README.md) | [日本語](https://github.com/mxcake3893/komitto/blob/main/README-ja.md)

`git diff` を解析し、LLM API（OpenAI, Gemini, Anthropic, Ollama など）と連携してセマンティックなコミットメッセージを生成するCLIツールです。コミット履歴からプロジェクト固有のスタイルを学習して自動適用する機能（`komitto learn`）も持ちます。

<p align="center">
  <img src="https://raw.githubusercontent.com/mxcake3893/komitto/main/assets/komitto-demo.gif" alt="ターミナルで実行中のkomitto">
</p>

## 主な機能

- ステージされた変更（`git diff --staged`）を解析し、オプションで複数のコンテキストを比較可能。
- 変更内容を、LLMが理解しやすい構造化されたXML/JSON形式に変換。
- **LLM API連携**: `komitto.toml` の設定に基づき、OpenAI, Gemini, Anthropic, Ollama などのプロバイダーのAPIを直接呼び出し可能。
- **思考プロセスの可視化**: LLMの思考プロセス（`<think>`タグなど）をリアルタイムにストリーミング表示。
- **コンテキスト理解**: プロジェクトの文脈やスタイルを維持するため、直近のコミットログを自動的にプロンプトに含めます。
- **外部ファイル参照**: プロンプトのコンテキストに外部ファイルの内容を簡単に参照・埋め込むことが可能。
- **スタイル学習** (`komitto learn`): コミット履歴を分析し、プロジェクトのコミットスタイルに合わせたカスタムシステムプロンプトを生成。
- コミットメッセージ生成用に特別に設計されたシステムプロンプトと組み合わせ可能。テンプレートは、コンテキストごと、テンプレートごと、またはモデルごとに上書きできます。
- 生成された最終的なプロンプト（または生のLLM出力）をクリップボードにコピー。
- コマンドライン引数経由で、変更に関する追加コンテキストを付与する機能を提供。
- **インタラクティブモード** (`-i`/`--interactive`): リッチなTUIインターフェースで、生成されたメッセージの確認、編集、再生成、コミットが可能。
- **TUIインターフェース**: [Textual](https://textual.textualize.io/)を使用して構築された、リアルタイムストリーミング、ローディングスピナー、アニメーション対応のモダンなターミナル体験。
- **エディタ連携**: お好みのエディタ（VISUAL/EDITOR/GIT_EDITOR）を使用してコミットメッセージを編集可能。

## インストール

komittoの動作にはPython 3.9以上が必要です。

```bash
pip install komitto
```

開発用のインストールを行う場合は、以下を使用してください:

```bash
pip install -e .
```

## 言語サポート

komittoはOSのロケールに基づいて言語を自動検出します。サポートされている言語:

* 英語 (`en`) – デフォルト
* 日本語 (`ja`)

`KOMITTO_LANG=ja` を設定することで、強制的に日本語にすることができます。

## 使い方

### AI自動生成モード（推奨）

`komitto.toml` に `[llm]` の設定（プロバイダーやモデルなど）を追加すると、`komitto` は直接LLMと通信します。推論プロセス（`<think>`等）とメッセージの生成をリアルタイムでストリーミング表示し、完了後にインタラクティブな確認プロンプトを表示します。

```bash
komitto
# -> ⏳ Generating...
# -> (思考プロセスとメッセージがストリーミング表示される)
# -> Commit message generated.
# -> [y] 承認してコミット [e] 編集 [r] 再生成 [n] キャンセル:
```

対話プロンプト中の操作:
* `y` – 承認してコミットする (`git commit -m <msg>`)
* `e` – 外部エディタでメッセージを編集する
* `r` – 再生成する
* `n` または `Ctrl-C` – キャンセル

### 手動プロンプト生成モード

`[llm]` セクションが未設定の場合、komitto はステージされた変更からプロンプトテキストのみを生成し、クリップボードにコピーします。これをChatGPT等のWeb UIに貼り付けて使用できます。

```bash
komitto
# -> Prompt copied!
```

### 比較モード

2つの異なる設定を並べて比較します:

```bash
komitto --compare ctxA ctxB
```

2つの列が表示されます。`a` または `b` を押してどちらかを選択し、通常通りコミットまたは編集を行います。

### 追加コンテキストの付与

プロンプトにマージされる自由形式のコンテキストを追加できます:

```bash
komitto "Urgent bug fix for payment processing"
```

### エディタ連携

インタラクティブモード中は、いつでも設定されたエディタを呼び出すことができます。選択順序は以下の通りです:

1. `$GIT_EDITOR`
2. `$VISUAL`
3. `$EDITOR`
4. Gitの組み込みデフォルト（Windowsでは `notepad`、それ以外では `vi`）。

### スタイル学習

既存のコミット履歴を分析し、プロジェクトに最適化されたシステムプロンプトを自動生成します:

```bash
komitto learn
```

このコマンドは以下を行います:
1. リポジトリから直近のコミットメッセージを読み込み
2. 使用されている言語、フォーマット、規約を分析
3. スタイルに合わせたカスタムシステムプロンプトを生成
4. オプションで `komitto.toml` を自動的に更新

### CLIオプション

| オプション                  | 説明                                             |
|----------------------------|--------------------------------------------------|
| `-i`, `--interactive`      | インタラクティブTUIモードを有効化                |
| `-c`, `--context-name 名前` | 設定からコンテキストプロファイルを指定           |
| `-t`, `--template 名前`     | 設定からプロンプトテンプレートを指定             |
| `-m`, `--model 名前`        | 設定からモデルを指定                             |
| `--compare CTX1 CTX2`       | 2つのコンテキスト設定からの出力を比較            |

## 設定ファイルによるカスタマイズ

以下を実行して、プロジェクト固有の設定を作成します:

```bash
komitto init
```

設定ファイルは以下の順序で検索されます（後の方が優先されます）:

1. ユーザー設定ディレクトリ (`%APPDATA%\komitto\config.toml` など)
2. プロジェクトディレクトリ `./komitto.toml`

### `komitto.toml` のサンプル

```toml
[prompt]
system = """
あなたはConventional Commitsに従ったセマンティックなコミットメッセージを作成する役立つアシスタントです。
以下のdiffを分析し、件名行（50文字以内）とオプションの本文のみを出力してください。
"""

[context]
# プロンプトに必ず含める参考情報ファイル
# files = ["README.md"]

[llm]
provider = "openai" # "openai", "gemini", "anthropic"
model = "gpt-5.4-mini"
# api_key = "sk-..." # 環境変数を使用する場合は省略可能
# base_url = "http://localhost:11434/v1" # Ollamaなどの場合
# history_limit = 5

[git]
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
# [templates.simple]
# system = "変更内容を1行で要約してください。"

# [models.gpt54mini]
# provider = "openai"
# model = "gpt-5.4-mini"

# [contexts.release]
# template = "simple"
# model = "gpt54mini"
```

### Ollama/LM Studio の使用

```toml
[llm]
provider = "openai"        # 互換レイヤーのためにopenaiを使用します
model = "qwen3"
base_url = "http://localhost:11434/v1"
```

## 仕組み（内部フロー）

1. `git diff --staged` でステージされた変更を取得します。
2. 差分は、XMLライクな形式の構造化表現（`ファイルパス | 操作 | 関連する関数/クラスのシグネチャ`）に変換されます。
3. 設定ファイルで定義された**システムプロンプト**が、ユーザー提供のコンテキストやdiffの表現とマージされ、最終的なLLM入力が生成されます。
4. CLIフラグに応じて、ツールはトークンをライブストリーミング（リッチUI）するか、完全な文字列を即座に返します。
5. 結果のテキストはクリップボードにコピーされます。インタラクティブモードでは、ユーザーは承認、編集、再生成、またはキャンセルが可能です。

## ライセンス

MIT © 2025-2026
