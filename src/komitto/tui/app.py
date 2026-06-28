from textual.app import App, ComposeResult
from textual.widgets import Footer, Static, Markdown, Label, Input, Button
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual import work
from textual.reactive import reactive
from textual.screen import ModalScreen
import asyncio
import pyperclip
from typing import Optional
from komitto.llm import create_llm_client
from komitto.git_utils import git_commit
from komitto.editor import launch_editor
from komitto.i18n import t
from komitto.cost import calculate_cost, format_cost
from komitto.prompt import clean_markdown_code_block


class IMEFriendlyInput(Input):
    """IME入力に対応したInputウィジェット。

    日本語等のIME変換時にIME候補ウィンドウが正しい位置に表示されるよう、
    フォーカス中はターミナルカーソル位置を定期的に同期する。
    """

    def on_focus(self) -> None:
        """フォーカス時にカーソル位置の定期同期を開始。"""
        self._ime_sync_timer = self.set_interval(
            0.05, self._sync_cursor_position
        )

    def on_blur(self) -> None:
        """フォーカス解除時に定期同期を停止。"""
        if hasattr(self, '_ime_sync_timer') and self._ime_sync_timer:
            self._ime_sync_timer.stop()
            self._ime_sync_timer = None

    def _sync_cursor_position(self) -> None:
        """ターミナルカーソル位置をInputのカーソル位置に同期。"""
        if self.has_focus:
            self.app.cursor_position = self.cursor_screen_offset


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
            yield IMEFriendlyInput(placeholder=t("tui.regen_placeholder"), id="regen-input")
    
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
    STATE_ERROR = "error"

    current_state = reactive(STATE_GENERATING)
    generated_text = reactive("")
    generated_text_a = reactive("")
    generated_text_b = reactive("")

    def __init__(self, config: Optional[dict] = None, prompt: str = "", compare_configs: Optional[list[tuple[str, dict]]] = None, **kwargs):
        super().__init__(**kwargs)
        self.prompt_text = prompt
        self.compare_configs = compare_configs
        
        if self.compare_configs:
            self.is_compare_mode = True
            self.config_a = self.compare_configs[0][1]
            self.name_a = self.compare_configs[0][0]
            self.config_b = self.compare_configs[1][1]
            self.name_b = self.compare_configs[1][0]
            self.messages_history = []
        else:
            self.is_compare_mode = False
            self.config = config
            self.messages_history = [{"role": "user", "content": self.prompt_text}]

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
                    yield Static("", id="reasoning-view", classes="reasoning-view")
                    yield Markdown("", id="markdown-view")
                    yield Label("", id="stats-label", classes="stats-label")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "Komitto"
        self._anim_frame = 0
        self._anim_timer = self.set_interval(0.1, self._animate_loading)
        if self.is_compare_mode:
            self.generate_compare()
        else:
            self.generate_message()

    def _animate_loading(self) -> None:
        if self.current_state != self.STATE_GENERATING:
            return

        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frame = frames[self._anim_frame % len(frames)]
        self._anim_frame += 1

        if not self.is_compare_mode:
            try:
                reasoning_view = self.query_one("#reasoning-view")
                is_reasoning = reasoning_view.display
            except:
                is_reasoning = False
            
            if is_reasoning:
                try:
                    self.query_one("#status-label").update(f"{frame} 💭 Thinking...")
                except: pass
            elif not self.generated_text:
                try:
                    self.query_one("#status-label").update(f"{frame} Generating commit message...")
                except: pass
            else:
                try:
                    self.query_one("#status-label").update("⏳ Generating commit message...")
                except: pass
        else:
            if not self.generated_text_a and not self.generated_text_b:
                try:
                    self.query_one("#left-panel Label").update(f"{frame} Option A: {self.name_a}")
                    self.query_one("#right-panel Label").update(f"{frame} Option B: {self.name_b}")
                except: pass
            else:
                try:
                    self.query_one("#left-panel Label").update(f"📝 Option A: {self.name_a}")
                    self.query_one("#right-panel Label").update(f"📝 Option B: {self.name_b}")
                except: pass

    def _show_reasoning_phase(self) -> None:
        """Switch UI to reasoning phase: show reasoning-view, hide markdown-view."""
        try:
            self.query_one("#reasoning-view").display = True
            self.query_one("#markdown-view").display = False
        except:
            pass

    def _show_content_phase(self) -> None:
        """Switch UI to content phase: hide reasoning-view, show markdown-view."""
        try:
            self.query_one("#reasoning-view").display = False
            self.query_one("#markdown-view").display = True
        except:
            pass

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

        elif state == self.STATE_ERROR:
            if not self.is_compare_mode:
                try:
                    status_label = self.query_one("#status-label")
                    status_label.update("❌ Generation failed")
                    status_label.remove_class("status-generating")
                    status_label.add_class("status-ready")
                except: pass

    @work(exclusive=True)
    async def generate_message(self) -> None:
        """Generate commit message in background (Single mode)."""
        import time
        self.current_state = self.STATE_GENERATING
        self.generated_text = ""

        llm_config = self.config.get("llm", {})
        if not llm_config or not llm_config.get("provider"):
            self.notify("No LLM provider configured.", severity="error")
            return

        client = create_llm_client(llm_config)
        try:
            full_text = ""
            reasoning_full_text = ""
            is_reasoning_phase = True
            usage_stats = None
            start_time = time.time()
            input_chars = sum(len(m["content"]) for m in self.messages_history)
            
            # Show reasoning-view, hide markdown-view initially
            self._show_reasoning_phase()
            
            async for chunk, reasoning_chunk, usage in client.stream_commit_message_async(self.messages_history):
                if reasoning_chunk:
                    reasoning_full_text += reasoning_chunk
                
                if chunk:
                    full_text += chunk
                    # First content chunk: transition from reasoning to main text
                    if is_reasoning_phase:
                        is_reasoning_phase = False
                        self._show_content_phase()
                
                # Update the appropriate view
                if is_reasoning_phase and reasoning_full_text:
                    try:
                        reasoning_view = self.query_one("#reasoning-view")
                        lines = reasoning_full_text.strip().split('\n')
                        display_lines = '\n'.join(lines[-3:])
                        reasoning_view.update(display_lines)
                    except:
                        pass
                elif full_text:
                    self.generated_text = full_text
                
                if usage:
                    usage_stats = usage
                
                elapsed = time.time() - start_time
                if elapsed > 0:
                    stats_text = ""
                    phase_label = "💭 " if is_reasoning_phase else "📊 "
                    if usage_stats:
                        p_tok = usage_stats.get('prompt_tokens', '?')
                        c_tok = usage_stats.get('completion_tokens', '?')
                        t_tok = usage_stats.get('total_tokens', '?')
                        speed = c_tok / elapsed if isinstance(c_tok, int) else 0
                        stats_text = f"{phase_label}Input: {input_chars} chars ({p_tok} tok) | Output: {c_tok} tok | Total: {t_tok} tok | Speed: {speed:.1f} tok/s"
                        
                        if isinstance(p_tok, int) and isinstance(c_tok, int):
                            cost_data = calculate_cost(llm_config, p_tok, c_tok)
                            if cost_data:
                                cost_str = format_cost(cost_data)
                                stats_text += f" | {cost_str}"
                    else:
                        total_chars = len(full_text) + len(reasoning_full_text)
                        speed = total_chars / elapsed if total_chars else 0
                        est_tok = total_chars // 4
                        stats_text = f"{phase_label}Input: {input_chars} chars | Est. Output: ~{est_tok} tok | Speed: {speed:.1f} char/s"
                    
                    try:
                        stats_label = self.query_one("#stats-label")
                        stats_label.update(stats_text)
                    except:
                        pass
            
            # Ensure we're in content phase for review
            if is_reasoning_phase:
                self._show_content_phase()
            
            self.current_state = self.STATE_REVIEW
            
            # Add assistant response to history
            if full_text:
                full_text = clean_markdown_code_block(full_text)
                self.generated_text = full_text
                self.messages_history.append({"role": "assistant", "content": full_text})
            
        except asyncio.CancelledError:
            self.notify("Generation canceled", severity="warning")
            raise
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            self.generated_text = ""
            self.current_state = self.STATE_ERROR
        finally:
            await client.aclose()

    @work(exclusive=True)
    async def generate_compare(self) -> None:
        """Generate two messages in parallel."""
        self.current_state = self.STATE_GENERATING
        self.generated_text_a = ""
        self.generated_text_b = ""

        prompt_a = self.compare_configs[0][2]
        prompt_b = self.compare_configs[1][2]

        await asyncio.gather(
            self._generate_compare_option(self.config_a, prompt_a, "generated_text_a"),
            self._generate_compare_option(self.config_b, prompt_b, "generated_text_b"),
            return_exceptions=True,
        )

        self.current_state = self.STATE_COMPARE

    async def _generate_compare_option(self, cfg, prompt, target_attr):
        try:
            llm_config = cfg.get("llm", {})
            client = create_llm_client(llm_config)
            full_text = ""
            try:
                async for chunk, reasoning_chunk, _ in client.stream_commit_message_async(prompt):
                    if chunk:
                        full_text += chunk
                        setattr(self, target_attr, full_text)
                
                full_text = clean_markdown_code_block(full_text)
                setattr(self, target_attr, full_text)
            finally:
                await client.aclose()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.notify(f"Error generating {target_attr}: {e}", severity="error")

    def action_select_a(self) -> None:
        if self.current_state == self.STATE_COMPARE:
            self.generated_text = self.generated_text_a
            self.config = self.config_a
            self.prompt_text = self.compare_configs[0][2]
            self.messages_history = [
                {"role": "user", "content": self.prompt_text},
                {"role": "assistant", "content": self.generated_text_a}
            ]
            self.current_state = self.STATE_REVIEW

    def action_select_b(self) -> None:
        if self.current_state == self.STATE_COMPARE:
            self.generated_text = self.generated_text_b
            self.config = self.config_b
            self.prompt_text = self.compare_configs[1][2]
            self.messages_history = [
                {"role": "user", "content": self.prompt_text},
                {"role": "assistant", "content": self.generated_text_b}
            ]
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
        
        def handle_modal_result(result: Optional[str]) -> None:
            if result is None:
                return
            if result:
                self.messages_history.append({"role": "user", "content": result})
            elif self.messages_history and self.messages_history[-1]["role"] == "assistant":
                self.messages_history.pop()
            self.generate_message()
        
        self.push_screen(RegenerateModal(), handle_modal_result)