import sys
import pyperclip
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .llm import create_llm_client
from .git_utils import get_commit_messages
from .i18n import t

from rich.live import Live
from rich.text import Text

console = Console()

def learn_style_from_history(config, limit=20):
    """
    コミット履歴を分析し、スタイルガイド（システムプロンプト案）を生成する
    """
    from pathlib import Path
    if not Path("komitto.toml").exists():
        console.print(t("learn.no_config_file"), style="yellow")
        return
    
    llm_config = config.get("llm", {})
    if not llm_config or not llm_config.get("provider"):
        console.print(t("main.api_error"), style="yellow")
        return

    messages = get_commit_messages(limit)
    if not messages:
        console.print(t("learn.no_history"), style="yellow")
        return

    history_text = "\n---\n".join(messages)

    tool_specs = """
## Technical Specifications (MUST be included in the system prompt)
The AI will receive input in a custom XML format, not standard 'git diff'. The system prompt MUST explain how to parse this:
- Root element: `<changeset>`
- Files: `<file path=\"...\">
- Code blocks: `<chunk scope=\"...\">` (scope indicates class/function context)
- Change types: `<type>` (modification, addition, deletion)
- Content: `<original>` (old code) vs `<modified>` (new code). The intent lies in the difference.
- Constraint: Only code inside `<modified>` represents the final state.
"""

    analysis_prompt = f"""
Act as an expert prompt engineer.
Your goal is to write a "System Prompt" for an AI commit message generator that matches the coding style and conventions of a specific repository.

{tool_specs}

## Source Material: Commit History
Analyze the following history to determine the Language, Format (e.g. Conventional Commits, Emoji), and Tone.
{history_text}

## Task
Write a comprehensive System Prompt that:
1. Incorporates the **Technical Specifications** above so the AI understands the XML input.
2. Instructs the AI to generate messages that strictly follow the style, language, and format observed in the **Commit History**.
3. (Important) If the history uses specific prefixes (feat, fix) or emojis, explicitly define them in the prompt.

## Output
Return ONLY the generated System Prompt. Do not include explanations.
The prompt itself should be written in the primary language of the commit history (e.g., if history is Japanese, write the prompt instructions in Japanese).
"""

    console.print(f"[bold #61afef]📚 {t('learn.analyzing', len(messages))}[/bold #61afef]")

    try:
        client = create_llm_client(llm_config)
        suggestion = ""
        
        cursor = "█"
        
        with Live(
            Panel(
                Markdown("", style="#abb2bf"), 
                title="⏳ " + t("learn.analyzing_status"), 
                border_style="#e5c07b",
                title_align="left"
            ), 
            console=console, 
            refresh_per_second=5, 
            vertical_overflow="visible"
        ) as live:
            for chunk, _ in client.stream_commit_message(analysis_prompt):
                if chunk:
                    suggestion += chunk
                    live.update(Panel(
                        Markdown(suggestion + cursor, style="#abb2bf"), 
                        title="⏳ " + t("learn.analyzing_status"), 
                        border_style="#e5c07b",
                        title_align="left"
                    ))
        
        console.clear()
        console.print(Panel(
            Markdown(suggestion, style="#abb2bf"), 
            title="✅ " + t("learn.suggested_prompt_title"), 
            border_style="#98c379",
            title_align="left"
        ))
        
        try:
            pyperclip.copy(suggestion)
            console.print(f"[#98c379]📋 {t('main.prompt_copied')}[/#98c379]")
        except Exception:
            console.print(f"[#e5c07b]⚠️  {t('main.manual_copy_required')}[/#e5c07b]")

        console.print(f"\n[bold yellow]{t('learn.auto_init_prompt')}[/bold yellow]")
        console.print("[dim](y を入力して Enter を押すと適用、その他のキーで手動設定)[/dim]")
        console.print("[bold cyan]▶ [/bold cyan]", end="")
        
        response = input().strip().lower()
        
        if response == 'y':
            console.print(f"[#98c379]{t('learn.auto_init_yes')}[/#98c379]")
            
            from .config import init_config_with_prompt
            success, message, is_new = init_config_with_prompt(suggestion)
            
            if success:
                if is_new:
                    console.print(f"[#98c379]{t('learn.auto_init_created', message)}[/#98c379]")
                else:
                    console.print(f"[#98c379]{t('learn.auto_init_backup_created', message)}[/#98c379]")
                    console.print(f"[#98c379]{t('learn.auto_init_updated', 'komitto.toml')}[/#98c379]")
            else:
                console.print(f"[#e06c75]{t('learn.auto_init_failed', message)}[/#e06c75]")
        else:
            console.print(f"[#e5c07b]{t('learn.auto_init_no')}[/#e5c07b]")
            console.print(f"\n[bold #61afef]📝 {t('learn.apply_instruction_title')}[/bold #61afef]")
            console.print(f"[#abb2bf]  1. {t('learn.apply_instruction_step0')}[/#abb2bf]")
            console.print(f"[#abb2bf]  2. {t('learn.apply_instruction_step1')}[/#abb2bf]")
            console.print(f"[#abb2bf]  3. {t('learn.apply_instruction_step2')}[/#abb2bf]")
            console.print(f"\n[dim #5c6370]ℹ️  {t('learn.apply_instruction_note')}[/dim #5c6370]")

    except Exception as e:
        console.print(f"[#e06c75]❌ {t('learn.error', e)}[/#e06c75]")
