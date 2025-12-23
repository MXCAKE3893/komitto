from textual.app import App, ComposeResult
from textual.widgets import Footer, Static, Markdown, Label
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual import work
from textual.reactive import reactive
import pyperclip

from komitto.llm import create_llm_client
from komitto.git_utils import git_commit
from komitto.editor import launch_editor


class CustomHeader(Static):
    """A custom header widget for Komitto TUI."""
    
    def __init__(self, title: str = "Komitto", **kwargs):
        super().__init__(**kwargs)
        self.title = title
    
    def render(self) -> str:
        return f"🔧 {self.title}"

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

    # アプリケーションの状態
    STATE_GENERATING = "generating"
    STATE_REVIEW = "review"
    STATE_COMPARE = "compare" # 比較選択待ち

    current_state = reactive(STATE_GENERATING)
    generated_text = reactive("") # シングルモード用、または選択後のテキスト
    
    # 比較モード用のリアクティブ変数
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
            # プロンプトは共通と仮定（または呼び出し側で個別にビルドが必要だが、一旦共通の diff prompt を使う）
            # ※ 本来は config ごとに system prompt が違うので、prompt も list で受け取るべきだが、
            # main.py の構造上、prompt (final_text) は config に依存してビルドされている。
            # 簡略化のため、このクラス内で prompt の再ビルドは行わず、渡された prompt を使う。
            # ただし、厳密には compare モードの場合、main.py 側でそれぞれの system prompt を使って
            # final_text を作っているはず。
            # -> コンストラクタ引数を (prompt_a, config_a), (prompt_b, config_b) のリストにするのが正しい。
            # 修正: compare_configs は [(name, config, prompt), ...] のリストとする。
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
            pass  # Footer will display key bindings
            
        elif state == self.STATE_REVIEW:
            # 比較モードから遷移してきた場合、レイアウトを切り替える必要があるが
            # Textual で動的にウィジェットを入れ替えるのは少し複雑。
            # ここでは、選択されたテキストを generated_text にセットし、
            # シンプルに「選択完了、あとはコミットするだけ」の状態にするか、
            # あるいは比較画面のまま片方をハイライトするなどの表現が考えられる。
            # 今回はシンプルに、選択されたテキストを表示するシングルビューに切り替える（再マウント）。
            # ...というのは難しいので、初期 compose で条件分岐している。
            # 一旦アプリを終了して、選択されたテキストで再度コミットフローに入る...のもUXが悪い。
            # 
            # 解決策: Containerの中身を消して、シングルビューをマウントし直す。
            
            if self.is_compare_mode:
                # 比較モードからの遷移時、UIをシングルモードに書き換える
                self.is_compare_mode = False # フラグを倒す
                container = self.query_one("#main-container")
                container.remove_children()
                container.mount(
                    Vertical(
                        Label("✅ Review selected message", id="status-label", classes="status-ready"),
                        Markdown(self.generated_text, id="markdown-view"),
                        id="content-area"
                    )
                )
            
            # シングルモードの場合の更新
            try:
                status_label = self.query_one("#status-label")
                status_label.update("✅ Review generated message")
                status_label.remove_class("status-generating")
                status_label.add_class("status-ready")
            except: pass

    @work(exclusive=True, thread=True)
    def generate_message(self) -> None:
        """Generate commit message in background (Single mode)."""
        self.app.call_from_thread(setattr, self, "current_state", self.STATE_GENERATING)
        self.app.call_from_thread(setattr, self, "generated_text", "")

        llm_config = self.config.get("llm", {})
        if not llm_config or not llm_config.get("provider"):
            self.app.call_from_thread(self.notify, "No LLM provider configured.", severity="error")
            return

        try:
            client = create_llm_client(llm_config)
            full_text = ""
            for chunk, usage in client.stream_commit_message(self.prompt_text):
                if chunk:
                    full_text += chunk
                    self.app.call_from_thread(setattr, self, "generated_text", full_text)
            
            self.app.call_from_thread(setattr, self, "current_state", self.STATE_REVIEW)
            
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")
            self.app.call_from_thread(setattr, self, "current_state", self.STATE_REVIEW)

    @work(exclusive=True, thread=True)
    def generate_compare(self) -> None:
        """Generate two messages in parallel."""
        self.app.call_from_thread(setattr, self, "current_state", self.STATE_GENERATING)
        self.app.call_from_thread(setattr, self, "generated_text_a", "")
        self.app.call_from_thread(setattr, self, "generated_text_b", "")

        # compare_configs structure: [(name, config, prompt), (name, config, prompt)]
        prompt_a = self.compare_configs[0][2]
        prompt_b = self.compare_configs[1][2]

        # 並列実行用のヘルパー
        def run_gen(cfg, prompt, target_attr):
            try:
                llm_config = cfg.get("llm", {})
                client = create_llm_client(llm_config)
                full_text = ""
                for chunk, _ in client.stream_commit_message(prompt):
                    if chunk:
                        full_text += chunk
                        self.app.call_from_thread(setattr, self, target_attr, full_text)
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Error generating {target_attr}: {e}", severity="error")

        import threading
        t1 = threading.Thread(target=run_gen, args=(self.config_a, prompt_a, "generated_text_a"))
        t2 = threading.Thread(target=run_gen, args=(self.config_b, prompt_b, "generated_text_b"))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.app.call_from_thread(setattr, self, "current_state", self.STATE_COMPARE)

    def action_select_a(self) -> None:
        if self.current_state == self.STATE_COMPARE:
            self.generated_text = self.generated_text_a
            self.config = self.config_a # 選択した設定を現在の設定にする（再生成時などに使用）
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
        
        self.notify("📤 Committing...", severity="information")
        self.do_commit(self.generated_text)

    def action_edit(self) -> None:
        if self.current_state != self.STATE_REVIEW:
            return
        
        # suspend() must be called from the main thread
        with self.suspend():
            new_text = launch_editor(self.generated_text)
        
        if new_text != self.generated_text:
            self.generated_text = new_text
            self.notify("✏️ Message updated from editor", severity="information")

    def action_copy(self) -> None:
        if self.current_state != self.STATE_REVIEW:
            return
        pyperclip.copy(self.generated_text)
        self.notify("📋 Copied to clipboard!", severity="information")

    def action_regenerate(self) -> None:
        if self.current_state != self.STATE_REVIEW:
            return
        self.generate_message()

    @work(thread=True)
    def do_commit(self, message: str) -> None:
        try:
            success = git_commit(message)
            if success:
                self.app.call_from_thread(self.notify, "✅ Commit successful!", severity="information")
                import time
                time.sleep(1)
                self.app.call_from_thread(self.exit)
            else:
                self.app.call_from_thread(self.notify, "❌ Commit failed.", severity="error")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"⚠️ Commit error: {e}", severity="error")