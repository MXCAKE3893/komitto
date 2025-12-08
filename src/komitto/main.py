import subprocess
import re
import sys
import argparse
from pathlib import Path
import pyperclip
from xml.sax.saxutils import escape

from .config import load_config, DEFAULT_SYSTEM_PROMPT
from .llm import create_llm_client

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
"""
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created {target_file}")
    except Exception as e:
        print(f"Error: Failed to create {target_file}: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate semantic commit prompt for LLMs from git diff.")
    parser.add_argument('context', nargs='*', help='Optional context or comments about the changes')
    args = parser.parse_args()

    # "init" コマンドの特別処理
    if len(args.context) == 1 and args.context[0] == "init":
        init_config()
        return

    # 設定の読み込み
    config = load_config()
    system_prompt = config["prompt"]["system"]

    # 1. コンテキストの構築
    full_payload = [system_prompt, "\n---\n"]
    
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

    # LLM設定がある場合はAPIを呼び出す
    llm_config = config.get("llm")
    if llm_config and llm_config.get("provider"):
        try:
            print("🤖 AIがコミットメッセージを生成中...")
            client = create_llm_client(llm_config)
            commit_message = client.generate_commit_message(final_text)
            
            # 結果をクリップボードにコピー
            pyperclip.copy(commit_message)
            print("\n" + "="*40)
            print(commit_message)
            print("="*40 + "\n")
            print("✅ 生成されたメッセージをクリップボードにコピーしました！")
        except Exception as e:
            print(f"Error calling LLM API: {e}", file=sys.stderr)
            print("⚠️ API呼び出しに失敗しました。プロンプトをコピーします。")
            pyperclip.copy(final_text)
            print("✅ プロンプトをクリップボードにコピーしました！")
    else:
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