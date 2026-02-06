from textual.app import App, ComposeResult
from textual.widgets import Footer, Static, Markdown, Label, Input, Button
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual import work
from textual.reactive import reactive
from textual.screen import ModalScreen
import pyperclip

from komitto.llm import create_llm_client
from komitto.git_utils import git_commit
from komitto.editor import launch_editor
from komitto.i18n import t


class CustomHeader(Static):
    """A custom header widget for Komitto TUI."""
    
    def __init__(self, title: str = "Komitto", **kwargs):
        super().__init__(**kwargs)
        self.title = title
    
    def render(self) -> str:
        return f"🔧 {self.title}"


class RegenerateModal(ModalScreen):
    """追加指示を入力するモーダルダイアログ"""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def compose(self) -> ComposeResult:
        with Vertical(id="regen-modal"):
            yield Label(t("tui.regen_title"), id="regen-title")
            yield Input(placeholder=t("tui.regen_placeholder"), id="regen-input")
    
    def on_mount(self) -> None:
        self.query_one("#regen-input", Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class KomittoApp(App):
    """A TUI for generating and reviewing commit messages."""

    CSS_PATH = "styles.tcss"
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("y", "commit", "Commit"),
        Binding("e", "edit", "Edit"),
        Binding("c", "copy", "Copy"),
        Binding("r", "regenerate", "Regenerate"),
        Binding("a", "select_a", "Select A", show=False),
        Binding("b", "select_b", "Select B", show=False),
    ]

    STATE_GENERATING = "generating"
    STATE_REVIEW = "review"
    STATE_COMPARE = "compare"

    current_state = reactive(STATE_GENERATING)
    generated_text = reactive("")
    generated_text_a = reactive("")
    generated_text_b = reactive("")

    def __init__(self, config: dict | None = None, prompt: str = "", compare_configs: list[tuple[str, dict]] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.prompt_text = prompt
        self.compare_configs = compare_configs
        
        if self.compare_configs:
            self.is_compare_mode = True
            self.config_a = self.compare_configs[0][1]
            self.name_a = self.compare_configs[0][0]
            self.config_b = self.compare_configs[1][1]
            self.name_b = self.compare_configs[1][0]
        else:
            self.is_compare_mode = False
            self.config = config

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield CustomHeader("Komitto - AI Commit Message Generator", id="custom-header")
        
        with Container(id="main-container"):
            if self.is_compare_mode:
                with Horizontal(id="compare-area"):
                    with Vertical(id="left-panel", classes="panel"):
                        yield Label(f"📝 Option A: {self.name_a}", classes="panel-header")
                        yield Markdown("", id="markdown-view-a")
                    with Vertical(id="right-panel", classes="panel"):
                        yield Label(f"📝 Option B: {self.name_b}", classes="panel-header")
                        yield Markdown("", id="markdown-view-b")
            else:
                with Vertical(id="content-area"):
                    yield Label("⏳ Generating commit message...", id="status-label", classes="status-generating")
                    yield Markdown("", id="markdown-view")
                    yield Label("", id="stats-label", classes="stats-label")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "Komitto"
        if self.is_compare_mode:
            self.generate_compare()
        else:
            self.generate_message()

    def watch_generated_text(self, text: str) -> None:
        if not self.is_compare_mode or self.current_state == self.STATE_REVIEW:
            try:
                self.query_one("#markdown-view").update(text)
            except: pass

    def watch_generated_text_a(self, text: str) -> None:
        if self.is_compare_mode:
            try:
                self.query_one("#markdown-view-a").update(text)
            except: pass

    def watch_generated_text_b(self, text: str) -> None:
        if self.is_compare_mode:
            try:
                self.query_one("#markdown-view-b").update(text)
            except: pass

    def watch_current_state(self, state: str) -> None:
        """Update UI based on state."""
        if state == self.STATE_GENERATING:
            if not self.is_compare_mode:
                self.query_one("#status-label").update("⏳ Generating commit message...")
                self.query_one("#status-label").remove_class("status-ready")
                self.query_one("#status-label").add_class("status-generating")
            
        elif state == self.STATE_COMPARE:
            pass
            
        elif state == self.STATE_REVIEW:
            if self.is_compare_mode:
                self.is_compare_mode = False
                container = self.query_one("#main-container")
                container.remove_children()
                container.mount(
                    Vertical(
                        Label("✅ Review selected message", id="status-label", classes="status-ready"),
                        Markdown(self.generated_text, id="markdown-view"),
                        id="content-area"
                    )
                )
            
            try:
                status_label = self.query_one("#status-label")
                status_label.update("✅ Review generated message")
                status_label.remove_class("status-generating")
                status_label.add_class("status-ready")
            except: pass

    @work(exclusive=True, thread=True)
    def generate_message(self) -> None:
        """Generate commit message in background (Single mode)."""
        import time
        self.call_from_thread(setattr, self, "current_state", self.STATE_GENERATING)
        self.call_from_thread(setattr, self, "generated_text", "")

        llm_config = self.config.get("llm", {})
        if not llm_config or not llm_config.get("provider"):
            self.call_from_thread(self.notify, "No LLM provider configured.", severity="error")
            return

        try:
            client = create_llm_client(llm_config)
            full_text = ""
            usage_stats = None
            start_time = time.time()
            input_chars = len(self.prompt_text)
            
            for chunk, usage in client.stream_commit_message(self.prompt_text):
                if chunk:
                    full_text += chunk
                    self.call_from_thread(setattr, self, "generated_text", full_text)
                
                if usage:
                    usage_stats = usage
                
                elapsed = time.time() - start_time
                if elapsed > 0:
                    stats_text = ""
                    if usage_stats:
                        p_tok = usage_stats.get('prompt_tokens', '?')
                        c_tok = usage_stats.get('completion_tokens', '?')
                        t_tok = usage_stats.get('total_tokens', '?')
                        speed = c_tok / elapsed if isinstance(c_tok, int) else 0
                        stats_text = f"📊 Input: {input_chars} chars ({p_tok} tok) | Output: {c_tok} tok | Total: {t_tok} tok | Speed: {speed:.1f} tok/s"
                    else:
                        est_tok = len(full_text) // 4
                        speed = len(full_text) / elapsed
                        stats_text = f"📊 Input: {input_chars} chars | Est. Output: ~{est_tok} tok | Speed: {speed:.1f} char/s"
                    
                    try:
                        stats_label = self.query_one("#stats-label")
                        self.call_from_thread(stats_label.update, stats_text)
                    except:
                        pass
            
            self.call_from_thread(setattr, self, "current_state", self.STATE_REVIEW)
            
        except Exception as e:
            self.call_from_thread(self.notify, f"Error: {e}", severity="error")
            self.call_from_thread(setattr, self, "current_state", self.STATE_REVIEW)

    @work(exclusive=True, thread=True)
    def generate_compare(self) -> None:
        """Generate two messages in parallel."""
        self.call_from_thread(setattr, self, "current_state", self.STATE_GENERATING)
        self.call_from_thread(setattr, self, "generated_text_a", "")
        self.call_from_thread(setattr, self, "generated_text_b", "")

        prompt_a = self.compare_configs[0][2]
        prompt_b = self.compare_configs[1][2]

        def run_gen(cfg, prompt, target_attr):
            try:
                llm_config = cfg.get("llm", {})
                client = create_llm_client(llm_config)
                full_text = ""
                for chunk, _ in client.stream_commit_message(prompt):
                    if chunk:
                        full_text += chunk
                        self.call_from_thread(setattr, self, target_attr, full_text)
            except Exception as e:
                self.call_from_thread(self.notify, f"Error generating {target_attr}: {e}", severity="error")

        import threading
        t1 = threading.Thread(target=run_gen, args=(self.config_a, prompt_a, "generated_text_a"))
        t2 = threading.Thread(target=run_gen, args=(self.config_b, prompt_b, "generated_text_b"))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.call_from_thread(setattr, self, "current_state", self.STATE_COMPARE)

    def action_select_a(self) -> None:
        if self.current_state == self.STATE_COMPARE:
            self.generated_text = self.generated_text_a
            self.config = self.config_a
            self.prompt_text = self.compare_configs[0][2]
            self.current_state = self.STATE_REVIEW

    def action_select_b(self) -> None:
        if self.current_state == self.STATE_COMPARE:
            self.generated_text = self.generated_text_b
            self.config = self.config_b
            self.prompt_text = self.compare_configs[1][2]
            self.current_state = self.STATE_REVIEW

    def action_commit(self) -> None:
        if self.current_state != self.STATE_REVIEW:
            return
        
        with self.suspend():
            print(f"\n{t('main.action_commit_running')}")
            success = git_commit(self.generated_text)
            
        if success:
            self.notify(t('main.action_commit_success'), severity="information")
            import time
            time.sleep(1)
            self.exit()
        else:
            self.notify(t('main.action_commit_failed'), severity="error")

    def action_edit(self) -> None:
        if self.current_state != self.STATE_REVIEW:
            return
        
        with self.suspend():
            new_text = launch_editor(self.generated_text)
        
        if new_text != self.generated_text:
            self.generated_text = new_text
            self.notify("✏️ Message updated from editor", severity="information")

    def action_copy(self) -> None:
        if self.current_state != self.STATE_REVIEW:
            return
        pyperclip.copy(self.generated_text)
        self.notify(t('main.copied_to_clipboard'), severity="information")

    def action_regenerate(self) -> None:
        if self.current_state != self.STATE_REVIEW:
            return
        
        def handle_modal_result(result: str | None) -> None:
            if result is None:
                return
            if result:
                self.prompt_text = f"{self.prompt_text}\n\n---\n{t('tui.regen_extra_header')}\n{result}"
            self.generate_message()
        
        self.push_screen(RegenerateModal(), handle_modal_result)