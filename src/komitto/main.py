import sys
import os
import argparse
import pyperclip

try:
    import msvcrt
except ImportError:
    import tty
    import termios

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.markup import escape

from .config import load_config, init_config
from .llm import create_llm_client
from .git_utils import get_git_diff, get_git_log, git_commit
from .editor import launch_editor
from .prompt import build_prompt
from .i18n import t

console = Console()

def get_key():
    """Reads a single key from the console."""
    if os.name == 'nt':
        # msvcrt.getch() returns bytes, decode to string
        key = msvcrt.getch()
        try:
            return key.decode('utf-8')
        except UnicodeDecodeError:
            return key  # Return bytes if cannot decode (e.g. arrow keys)
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def main():
    parser = argparse.ArgumentParser(description="Generate semantic commit prompt for LLMs from git diff.")
    parser.add_argument('context', nargs='*', help='Optional context or comments about the changes')
    parser.add_argument('-i', '--interactive', action='store_true', help='Enable interactive mode to review/edit the message')
    args = parser.parse_args()

    if len(args.context) == 1 and args.context[0] == "init":
        init_config()
        return

    config = load_config()
    system_prompt = config["prompt"]["system"]
    
    llm_config = config.get("llm", {})
    history_limit = llm_config.get("history_limit", 5)

    git_config = config.get("git", {})
    exclude_patterns = git_config.get("exclude", [])

    recent_logs = get_git_log(limit=history_limit)
    diff_content = get_git_diff(exclude_patterns=exclude_patterns)
    user_context = " ".join(args.context)

    final_text = build_prompt(system_prompt, recent_logs, user_context, diff_content)

    if llm_config and llm_config.get("provider"):
        try:
            client = create_llm_client(llm_config)
            
            while True:
                with console.status(t("main.generating"), spinner="dots"):
                    commit_message = client.generate_commit_message(final_text)
                
                if not args.interactive:
                    pyperclip.copy(commit_message)
                    console.print(Panel(Markdown(commit_message), title="Generated Commit Message", border_style="blue"))
                    console.print(t("main.copied_to_clipboard"), style="green")
                    break

                while True:
                    console.clear() 
                    console.print(Panel(Markdown(commit_message), title="Generated Commit Message", border_style="blue"))
                    
                    prompt_msg = escape(t("main.action_prompt"))
                    console.print(prompt_msg, end=" ", style="bold")
                    sys.stdout.flush()
                    
                    choice = get_key().lower()
                    console.print(choice) 
                    
                    if choice == 'y':
                        try:
                            pyperclip.copy(commit_message)
                        except Exception:
                            pass
                        
                        console.print(t("main.action_commit_running"), style="yellow")
                        if git_commit(commit_message):
                            console.print(t("main.action_commit_success"), style="bold green")
                        else:
                            console.print(t("main.action_commit_failed"), style="bold red")
                        return
                    
                    elif choice == 'e':
                        commit_message = launch_editor(commit_message)
                        continue 
                        
                    elif choice == 'r':
                        break 
                        
                    elif choice == 'n' or choice == '\x03' or choice == 'q':
                        console.print(t("main.action_canceled"), style="yellow")
                        os._exit(0)
            
        except Exception as e:
            console.print(f"Error calling LLM API: {e}", style="bold red")
            console.print(t("main.api_error"), style="yellow")
            try:
                pyperclip.copy(final_text)
                console.print(t("main.prompt_copied"), style="green")
            except:
                pass
    else:
        try:
            pyperclip.copy(final_text)
            console.print(t("main.prompt_copied"), style="green")
            if user_context:
                console.print(t("main.context_added", user_context), style="blue")
        except pyperclip.PyperclipException:
            console.print(t("main.manual_copy_required"), style="yellow")
            console.print(final_text)
        except Exception as e:
            console.print(t("common.error", e), style="bold red")

if __name__ == "__main__":
    main()
