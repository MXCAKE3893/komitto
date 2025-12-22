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
    llm_config = config.get("llm", {})
    if not llm_config or not llm_config.get("provider"):
        console.print(t("main.api_error"), style="yellow")
        return

    # 履歴取得
    messages = get_commit_messages(limit)
    if not messages:
        console.print(t("learn.no_history"), style="yellow")
        return

    history_text = "\n---\n".join(messages)

    # ツール仕様（Facts）の定義
    tool_specs = """
## Technical Specifications (MUST be included in the system prompt)
The AI will receive input in a custom XML format, not standard 'git diff'. The system prompt MUST explain how to parse this:
- Root element: `<changeset>`
- Files: `<file path="...">`
- Code blocks: `<chunk scope="...">` (scope indicates class/function context)
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

    console.print(f"[bold cyan]{t('learn.analyzing', len(messages))}[/bold cyan]")

    try:
        client = create_llm_client(llm_config)
        suggestion = ""
        
        # Cursor effect for richer UI
        cursor = "█"
        
        with Live(Panel(Markdown(""), title=t("learn.analyzing_status"), border_style="green"), console=console, refresh_per_second=5, vertical_overflow="visible") as live:
            for chunk, _ in client.stream_commit_message(analysis_prompt):
                if chunk:
                    suggestion += chunk
                    # Show cursor at the end
                    live.update(Panel(Markdown(suggestion + cursor), title=t("learn.analyzing_status"), border_style="green"))
        
        console.clear()
        console.print(Panel(Markdown(suggestion), title=t("learn.suggested_prompt_title"), border_style="green"))
        
        try:
            pyperclip.copy(suggestion)
            console.print(t("main.prompt_copied"), style="green")
        except Exception:
            console.print(t("main.manual_copy_required"), style="yellow")

        console.print(f"\n[bold]{t('learn.apply_instruction_title')}[/bold]")
        console.print(t("learn.apply_instruction_step0"))
        console.print(t("learn.apply_instruction_step1"))
        console.print(t("learn.apply_instruction_step2"))
        console.print(f"\n[dim]{t('learn.apply_instruction_note')}[/dim]")

    except Exception as e:
        console.print(f"[red]{t('learn.error', e)}[/red]")