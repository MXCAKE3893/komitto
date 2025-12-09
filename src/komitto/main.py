import sys
import argparse
import pyperclip

from .config import load_config, init_config
from .llm import create_llm_client
from .git_utils import get_git_diff, get_git_log
from .editor import launch_editor
from .prompt import build_prompt

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

    # Git情報の取得
    recent_logs = get_git_log(limit=history_limit)
    diff_content = get_git_diff()
    user_context = " ".join(args.context)

    # プロンプトの構築
    final_text = build_prompt(system_prompt, recent_logs, user_context, diff_content)

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
        # LLM設定がない場合
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
