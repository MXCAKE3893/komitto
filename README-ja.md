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
- **LLM API連携**: `komitto.json` の設定に基づき、OpenAI, Gemini, Anthropic, Ollama などのプロバイダーのAPIを直接呼び出し可能。
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

`komitto.json` に `llm` の設定（プロバイダーやモデルなど）を追加すると、`komitto` は直接LLMと通信します。推論プロセス（`<think>`等）とメッセージの生成をリアルタイムでストリーミング表示し、完了後にインタラクティブな確認プロンプトを表示します。

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
4. このリポジトリ用の Markdown システムプロンプトを作成または更新

### CLIオプション

| オプション                  | 説明                                             |
|----------------------------|--------------------------------------------------|
| `-i`, `--interactive`      | インタラクティブTUIモードを有効化                |
| `-c`, `--context-name 名前` | 設定からコンテキストプロファイルを指定           |
| `-t`, `--template 名前`     | 設定からプロンプトテンプレートを指定             |
| `-m`, `--model 名前`        | 設定からモデルを指定                             |
| `--compare CTX1 CTX2`       | 2つのコンテキスト設定からの出力を比較            |

## 設定ファイルによるカスタマイズ

以下を実行すると、プロジェクト設定とリポジトリ別プロンプトファイルを作成します:

```bash
komitto init
```

設定は次の順序で読み込まれます（後の値が前の値を上書きします）:

1. 組み込みの既定値
2. グローバル JSON: `~/.config/komitto/config.json`
3. ローカル JSON: `./komitto.json`
4. リポジトリ別プロンプト: `~/.config/komitto/repos/<repository-sha256>/system.md`

プロンプトのパスは正規化した Git の `origin` URL（origin がない場合は Git top-level ディレクトリ）から算出されるため、リポジトリごとに別の `system.md` が使用されます。`komitto learn` はこの Markdown ファイルを更新し、必要に応じて `./komitto.json` を作成または更新します。

### `komitto.json` のサンプル

```json
{
  "$schema": "https://raw.githubusercontent.com/MXCAKE3893/komitto/main/schema/komitto-config.schema.json",
  "prompt": { "source": "repository" },
  "context": { "files": ["README.md"] },
  "llm": {
    "provider": "openai",
    "model": "gpt-5.4-mini",
    "base_url": "http://localhost:11434/v1"
  },
  "git": { "exclude": ["package-lock.json", "*.lock"] },
  "templates": { "simple": { "system": "変更内容を1行で要約してください。" } },
  "models": { "gpt54mini": { "provider": "openai", "model": "gpt-5.4-mini" } },
  "contexts": { "release": { "template": "simple", "model": "gpt54mini" } }
}
```

`$schema` により、対応エディタで補完と検証が有効になります。公開スキーマは [`schema/komitto-config.schema.json`](schema/komitto-config.schema.json) にあり、`main` の URL はインストール済み形式の最新定義を参照します。

### 機密情報とプロンプト本文

API キーやプロンプト本文を JSON に保存しないでください。`komitto` は、すでにプロセス環境に設定された値を上書きせずに `~/.config/komitto/.env` を読み込みます。`komitto init` は利用可能な変数名を示す `~/.config/komitto/.env.example` を作成します:

```dotenv
OPENAI_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
```

`llm.api_key_env` を指定すると、任意の環境変数名を使用できます（例: `"api_key_env": "OLLAMA_API_KEY"`）。未指定の場合は、OpenAI は `OPENAI_API_KEY`、Gemini は `GEMINI_API_KEY` または `GOOGLE_API_KEY`、Anthropic は `ANTHROPIC_API_KEY` を使用します。旧来の `config.toml` と `komitto.toml` は初回読み込み時に自動移行され、`api_key` は移行先から除外されます。

### Ollama/LM Studio の使用

OpenAI 互換プロバイダーと URL を JSON で指定します:

```json
{
  "llm": {
    "provider": "openai",
    "model": "qwen3",
    "base_url": "http://localhost:11434/v1",
    "api_key_env": "OLLAMA_API_KEY"
  }
}
```

## 仕組み（内部フロー）

1. `git diff --staged` でステージされた変更を取得します。
2. 差分は、XMLライクな形式の構造化表現（`ファイルパス | 操作 | 関連する関数/クラスのシグネチャ`）に変換されます。
3. 設定ファイルで定義された**システムプロンプト**が、ユーザー提供のコンテキストやdiffの表現とマージされ、最終的なLLM入力が生成されます。
4. CLIフラグに応じて、ツールはトークンをライブストリーミング（リッチUI）するか、完全な文字列を即座に返します。
5. 結果のテキストはクリップボードにコピーされます。インタラクティブモードでは、ユーザーは承認、編集、再生成、またはキャンセルが可能です。

## ライセンス

MIT © 2025-2026
