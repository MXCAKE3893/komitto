import subprocess
import re
import sys
import argparse
import pyperclip
from xml.sax.saxutils import escape

# ==========================================
# LLM System Prompt Definition
# ==========================================
SYSTEM_PROMPT = r"""
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

def get_git_diff():
    """ステージングされた変更を取得する"""
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Error: Not a git repository.", file=sys.stderr)
        sys.exit(1)

    cmd = ["git", "diff", "--staged", "--no-prefix", "-U0"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    if not result.stdout:
        print("Warning: No staged changes found. (Use 'git add' first)", file=sys.stderr)
        sys.exit(1)
        
    return result.stdout

def parse_diff_to_xml(diff_content):
    """Git DiffをXML形式に変換する"""
    diff_lines = diff_content.split('\n')
    output = []
    
    output.append("以下より<changeset>")
    output.append("<changeset>")
    
    current_file = None
    current_scope = ""
    in_chunk = False
    added_lines = []
    removed_lines = []
    
    def flush_chunk():
        nonlocal in_chunk, added_lines, removed_lines
        if not in_chunk:
            return
            
        if added_lines and removed_lines:
            c_type = "modification"
        elif added_lines:
            c_type = "addition"
        else:
            c_type = "deletion"

        output.append(f'    <chunk scope="{escape(current_scope)}">')
        output.append(f'      <type>{c_type}</type>')
        
        if removed_lines:
            content = "\n".join(removed_lines)
            output.append(f'      <original>\n{escape(content)}\n      </original>')
        
        if added_lines:
            content = "\n".join(added_lines)
            output.append(f'      <modified>\n{escape(content)}\n      </modified>')
            
        output.append('    </chunk>')
        
        added_lines.clear()
        removed_lines.clear()
        in_chunk = False

    for line in diff_lines:
        if line.startswith("diff --git"):
            flush_chunk()
            if current_file:
                output.append("  </file>")
            
            match = re.search(r"diff --git (.*?) (.*)", line)
            file_path = match.group(2) if match else "unknown"
            current_file = file_path
            output.append(f'  <file path="{file_path}">')
            continue

        if line.startswith("@@"):
            flush_chunk()
            scope_match = re.search(r"@@.*?@@\s*(.*)", line)
            current_scope = scope_match.group(1).strip() if scope_match else "global"
            in_chunk = True
            continue
            
        if in_chunk:
            if line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])

    flush_chunk()
    if current_file:
        output.append("  </file>")
    output.append("</changeset>")
    
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description="Generate semantic commit prompt for LLMs from git diff.")
    parser.add_argument('context', nargs='*', help='Optional context or comments about the changes')
    args = parser.parse_args()

    # 1. コンテキストの構築
    full_payload = [SYSTEM_PROMPT, "\n---\n"]
    
    user_context = " ".join(args.context)
    if user_context:
        full_payload.append("## 💡 ユーザーからの追加コンテキスト（補足情報）")
        full_payload.append(f"ユーザーメモ: {user_context}")
        full_payload.append("\n---\n")

    # 2. XML Diffの生成
    diff_content = get_git_diff()
    xml_output = parse_diff_to_xml(diff_content)
    full_payload.append(xml_output)

    # 3. 結果の結合
    final_text = "\n".join(full_payload)

    # 4. クリップボードへのコピー
    try:
        pyperclip.copy(final_text)
        print("✅ プロンプトをクリップボードにコピーしました！")
        if user_context:
            print(f"📝 付与されたコンテキスト: {user_context}")
    except pyperclip.PyperclipException:
        print("⚠️ クリップボードへのコピーに失敗しました。以下の出力を手動でコピーしてください:\n")
        print(final_text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()