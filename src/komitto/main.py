import sys
import argparse
import pyperclip

from .config import load_config, init_config
from .llm import create_llm_client
from .git_utils import get_git_diff, get_git_log, git_commit
from .editor import launch_editor
from .prompt import build_prompt
from .i18n import t

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

    # Git除外設定の取得
    git_config = config.get("git", {})
    exclude_patterns = git_config.get("exclude", [])

    # Git情報の取得
    recent_logs = get_git_log(limit=history_limit)
    diff_content = get_git_diff(exclude_patterns=exclude_patterns)
    user_context = " ".join(args.context)

    # プロンプトの構築
    final_text = build_prompt(system_prompt, recent_logs, user_context, diff_content)

    # LLM設定がある場合はAPIを呼び出す
    if llm_config and llm_config.get("provider"):
        try:
            client = create_llm_client(llm_config)
            
            # 再生成用ループ (r:再生成 が選ばれた場合にここに戻る)
            while True:
                print(t("main.generating"))
                commit_message = client.generate_commit_message(final_text)
                
                # 対話モードが無効なら即終了（既存の挙動）
                if not args.interactive:
                    pyperclip.copy(commit_message)
                    print("\n" + "="*40)
                    print(commit_message)
                    print("="*40 + "\n")
                    print(t("main.copied_to_clipboard"))
                    break

                # 承認ループ (編集後にここに戻る)
                while True:
                    print("\n" + "="*40)
                    print(commit_message)
                    print("="*40 + "\n")
                    
                    choice = input(t("main.action_prompt")).lower().strip()
                    
                    if choice == 'y':
                        # クリップボードにも一応コピーしておく
                        try:
                            pyperclip.copy(commit_message)
                        except Exception:
                            pass
                        
                        print(t("main.action_commit_running"))
                        if git_commit(commit_message):
                            print(t("main.action_commit_success"))
                        else:
                            print(t("main.action_commit_failed"))
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
                        print(t("main.action_canceled"))
                        sys.exit(0)
            
        except Exception as e:
            print(f"Error calling LLM API: {e}", file=sys.stderr)
            print(t("main.api_error"))
            pyperclip.copy(final_text)
            print(t("main.prompt_copied"))
    else:
        # LLM設定がない場合
        try:
            pyperclip.copy(final_text)
            print(t("main.prompt_copied"))
            if user_context:
                print(t("main.context_added", user_context))
        except pyperclip.PyperclipException:
            print(t("main.manual_copy_required"))
            print(final_text)
        except Exception as e:
            print(t("common.error", e), file=sys.stderr)

if __name__ == "__main__":
    main()
