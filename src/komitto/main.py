import sys
import os
import argparse
import pyperclip
import time

try:
    import msvcrt
except ImportError:
    import tty
    import termios

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.markup import escape

from .config import load_config, init_config, resolve_config
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

from rich.live import Live
from rich.console import Group
from rich.text import Text

def generate_and_review(config, args, system_prompt, final_text, title_suffix=""):
    """
    Generates a commit message and handles the review loop.
    Extracts the main generation and interaction logic for reuse in single and compare modes.
    """
    llm_config = config.get("llm", {})
    if not llm_config or not llm_config.get("provider"):
        console.print(t("main.api_error"), style="yellow") # Or specific error about missing config
        return None

    try:
        client = create_llm_client(llm_config)
        
        while True:
            commit_message = ""
            usage_stats = None
            start_time = time.time()
            input_chars = len(final_text)
            
            with Live(
                Panel(
                    Markdown(""), 
                    title=f"⏳ Generating {title_suffix}...", 
                    border_style="#e5c07b",
                    title_align="left"
                ), 
                console=console, 
                refresh_per_second=10
            ) as live:
                for chunk, usage in client.stream_commit_message(final_text):
                    if chunk:
                        commit_message += chunk
                    
                    if usage:
                        usage_stats = usage
                    
                    elapsed = time.time() - start_time
                    speed_info = ""
                    if elapsed > 0:
                        if usage_stats and usage_stats.get('completion_tokens'):
                            speed = usage_stats['completion_tokens'] / elapsed
                            speed_info = f" / {speed:.1f} tok/s"
                        else:
                            speed = len(commit_message) / elapsed
                            speed_info = f" / {speed:.1f} char/s"

                    token_info = ""
                    if usage_stats:
                        p_tok = usage_stats.get('prompt_tokens', '?')
                        c_tok = usage_stats.get('completion_tokens', '?')
                        token_info = f"\nInput: {input_chars} chars ({p_tok} toks) / Output: {c_tok} toks{speed_info}"
                    elif commit_message:
                         est_out_tok = len(commit_message) // 4
                         token_info = f"\nInput: {input_chars} chars / Est. Output: {est_out_tok} toks{speed_info}"

                    live.update(Panel(
                        Group(
                            Markdown(commit_message),
                            Text.from_markup(token_info, style="dim")
                        ),
                        title=f"Generating {title_suffix}...", 
                        border_style="blue"
                    ))

            console.clear()
            final_panel_title = f"Generated Commit Message {title_suffix}"
            if usage_stats:
                elapsed = time.time() - start_time
                speed_str = ""
                if elapsed > 0 and usage_stats.get('completion_tokens'):
                     speed_str = f" ({usage_stats['completion_tokens'] / elapsed:.1f} tok/s)"
                
                p_tok = usage_stats.get('prompt_tokens', '?')
                c_tok = usage_stats.get('completion_tokens', '?')
                t_tok = usage_stats.get('total_tokens', '?')
                usage_str = f"[dim]Input: {input_chars} chars ({p_tok} toks) / Output: {c_tok} toks / Total: {t_tok} toks{speed_str}[/dim]"
                console.print(usage_str, justify="right")
            
            if not args.interactive and not args.compare:
                pyperclip.copy(commit_message)
                console.print(Panel(
                    Markdown(commit_message), 
                    title=f"✅ {final_panel_title}", 
                    border_style="#98c379",
                    title_align="left"
                ))
                console.print(f"[#98c379]📋 {t('main.copied_to_clipboard')}[/#98c379]")
                return commit_message

            # Interactive loop (or return for compare mode to handle display)
            if args.compare:
                return commit_message

            while True:
                console.clear() 
                if usage_stats:
                     console.print(f"[dim]Tokens: Prompt {usage_stats.get('prompt_tokens', '?')}, Completion {usage_stats.get('completion_tokens', '?')}, Total {usage_stats.get('total_tokens', '?')}[/dim]", justify="right")

                console.print(Panel(
                    Markdown(commit_message), 
                    title=f"✅ {final_panel_title}", 
                    border_style="#98c379",
                    title_align="left"
                ))
                
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
                    
                    console.print(f"[#e5c07b]📤 {t('main.action_commit_running')}[/#e5c07b]")
                    if git_commit(commit_message):
                        console.print(f"[#98c379]✅ {t('main.action_commit_success')}[/#98c379]")
                        return commit_message
                    else:
                        console.print(f"[#e06c75]❌ {t('main.action_commit_failed')}[/#e06c75]")
                        return None
                
                elif choice == 'e':
                    commit_message = launch_editor(commit_message)
                    continue 
                    
                elif choice == 'r':
                    break # Break inner loop to regenerate
                    
                elif choice == 'n' or choice == '\x03' or choice == 'q':
                    console.print(f"[#e5c07b]⚠️  {t('main.action_canceled')}[/#e5c07b]")
                    os._exit(0)
    except Exception as e:
        console.print(f"[#e06c75]❌ Error calling LLM API {title_suffix}: {e}[/#e06c75]")
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate semantic commit prompt for LLMs from git diff.")
    parser.add_argument('context', nargs='*', help='Optional context or comments about the changes')
    parser.add_argument('-i', '--interactive', action='store_true', help='Enable interactive mode to review/edit the message')
    parser.add_argument('-c', '--context-name', dest='context_name', help='Specify a context profile from config')
    parser.add_argument('-t', '--template', help='Specify a prompt template from config')
    parser.add_argument('-m', '--model', help='Specify a model config from config')
    parser.add_argument('--compare', nargs=2, metavar=('CTX1', 'CTX2'), help='Compare two contexts (by name)')
    args = parser.parse_args()

    if len(args.context) == 1 and args.context[0] == "init":
        init_config()
        return

    if len(args.context) == 1 and args.context[0] == "learn":
        base_config = load_config()
        config = resolve_config(base_config, model_name=args.model)
        from .learn import learn_style_from_history
        learn_style_from_history(config)
        return

    base_config = load_config()

    if args.compare:
        config1 = resolve_config(base_config, context_name=args.compare[0])
        config2 = resolve_config(base_config, context_name=args.compare[1])
        configs = [(args.compare[0], config1), (args.compare[1], config2)]
    else:
        config = resolve_config(base_config, context_name=args.context_name, template_name=args.template, model_name=args.model)
        configs = [("Default", config)]

    git_config = configs[0][1].get("git", {}) 
    exclude_patterns = git_config.get("exclude", [])
    
    llm_config = configs[0][1].get("llm", {})
    history_limit = llm_config.get("history_limit", 5)

    recent_logs = get_git_log(limit=history_limit)
    diff_content = get_git_diff(exclude_patterns=exclude_patterns)
    user_context = " ".join(args.context)

    if args.compare:
        compare_configs = []
        for name, cfg in configs:
            system_prompt = cfg["prompt"]["system"]
            final_text = build_prompt(system_prompt, recent_logs, user_context, diff_content)
            compare_configs.append((name, cfg, final_text))
        
        from .tui.app import KomittoApp
        app = KomittoApp(compare_configs=compare_configs)
        app.run()

    else:
        cfg = configs[0][1]
        system_prompt = cfg["prompt"]["system"]
        final_text = build_prompt(system_prompt, recent_logs, user_context, diff_content)
        
        if cfg.get("llm", {}).get("provider"):
            if args.interactive:
                from .tui.app import KomittoApp
                app = KomittoApp(config=cfg, prompt=final_text)
                app.run()
            else:
                generate_and_review(cfg, args, system_prompt, final_text)
        else:
            try:
                pyperclip.copy(final_text)
                console.print(t("main.prompt_copied"), style="green")
            except:
                console.print(final_text)

if __name__ == "__main__":
    main()
