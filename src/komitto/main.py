import subprocess
import re
import sys
import argparse
import os
import tempfile
import textwrap
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

def get_git_log(limit=5):
    """直近のコミットメッセージと変更ファイルを取得する"""
    cmd = [
        "git", "log", 
        f"-n {limit}", 
        "--date=iso", 
        "--pretty=format:Commit: %h%nDate: %ad%nMessage:%n%B%n[Files]", 
        "--name-status"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0 and result.stdout:
            logs = result.stdout.strip()
            formatted_logs = []
            for block in logs.split("Commit: "):
                if not block.strip():
                    continue
                formatted_logs.append(f"Commit: {block.strip()}")
            
            return "\n\n----------------------------------------\n\n".join(formatted_logs)
    except Exception:
        pass
    return None

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
# # history_limit = 5 # プロンプトに含める過去のコミット数
"""
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created {target_file}")
    except Exception as e:
        print(f"Error: Failed to create {target_file}: {e}", file=sys.stderr)
        sys.exit(1)

def launch_editor(initial_message: str) -> str:
    """環境変数で指定されたエディタを起動してメッセージを編集させる"""
    # エディタの特定: 環境変数 -> git var GIT_EDITOR -> デフォルト
    editor = os.environ.get('GIT_EDITOR') or \
             os.environ.get('VISUAL') or \
             os.environ.get('EDITOR')

    if not editor:
        try:
            result = subprocess.run(['git', 'var', 'GIT_EDITOR'], capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0 and result.stdout:
                editor = result.stdout.strip()
        except Exception:
            pass

    if not editor:
        editor = 'notepad' if os.name == 'nt' else 'vi'

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix=".txt") as tmp_file:
        tmp_file_path = tmp_file.name
        tmp_file.write(initial_message.strip() + "\n\n")
        tmp_file.write(textwrap.dedent("""
            # --- komitto interactive mode ---
            # コミットメッセージを編集してください。
            # '#' で始まる行は最終的なメッセージから除外されます。
        """).strip())
    
    try:
        if os.name == 'nt':
            cmd = f'{editor} "{tmp_file_path}"'
            subprocess.run(cmd, check=True, shell=True)
        else:
            import shlex
            cmd_args = shlex.split(editor)
            cmd_args.append(tmp_file_path)
            subprocess.run(cmd_args, check=True)
        
        with open(tmp_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        cleaned_lines = [line for line in lines if not line.strip().startswith('#')]
        return "".join(cleaned_lines).strip()
        
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"⚠️ エディタ '{editor}' の起動に失敗しました ({e})。編集をキャンセルします。", file=sys.stderr)
        return initial_message
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

def main():
    parser = argparse.ArgumentParser(description="Generate semantic commit prompt for LLMs from git diff.")
    parser.add_argument('context', nargs='*', help='Optional context or comments about the changes')
    parser.add_argument('-i', '--interactive', action='store_true', help='Enable interactive mode to review/edit the message')
    args = parser.parse_args()

    # "init" コマンドの特別処理
    if len(args.context) == 1 and args.context[0] == "init":
        init_config()
        return

    # 設定の読み込み
    config = load_config()
    system_prompt = config["prompt"]["system"]
    
    # LLM設定の取得
    llm_config = config.get("llm", {})
    history_limit = llm_config.get("history_limit", 5)

    # 1. コンテキストの構築
    full_payload = [system_prompt, "\n---\n"]
    
    # 直近のコミット履歴を追加
    recent_logs = get_git_log(limit=history_limit)
    if recent_logs:
        full_payload.append("## 📜 直近のコミット履歴（参考情報）")
        full_payload.append(f"以下の履歴を踏まえて、文脈や形式を考慮してください:\n\n{recent_logs}")
        full_payload.append("\n---\n")
    
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
    if llm_config and llm_config.get("provider"):
        try:
            client = create_llm_client(llm_config)
            
            # 再生成用ループ (r:再生成 が選ばれた場合にここに戻る)
            while True:
                print("🤖 AIがコミットメッセージを生成中...")
                commit_message = client.generate_commit_message(final_text)
                
                # 対話モードが無効なら即終了（既存の挙動）
                if not args.interactive:
                    pyperclip.copy(commit_message)
                    print("\n" + "="*40)
                    print(commit_message)
                    print("="*40 + "\n")
                    print("✅ 生成されたメッセージをクリップボードにコピーしました！")
                    break

                # 承認ループ (編集後にここに戻る)
                while True:
                    print("\n" + "="*40)
                    print(commit_message)
                    print("="*40 + "\n")
                    
                    choice = input("Action [y:採用 / e:編集 / r:再生成 / n:キャンセル]: ").lower().strip()
                    
                    if choice == 'y':
                        pyperclip.copy(commit_message)
                        print("✅ 生成されたメッセージをクリップボードにコピーしました！")
                        return # 終了
                    
                    elif choice == 'e':
                        # エディタを起動して編集
                        commit_message = launch_editor(commit_message)
                        # 編集結果を表示するためにループ継続
                        continue 
                        
                    elif choice == 'r':
                        # 再生成ループへ戻る
                        break 
                        
                    elif choice == 'n':
                        print("❌ キャンセルしました。")
                        sys.exit(0)
            
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