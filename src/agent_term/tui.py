"""Textual TUI entry point for AgentTerm.

Requires the optional `textual` dependency:
  pip install agent-term[textual]

Shows Matrix rooms, selected thread events, local event log, agent status,
Policy Fabric approval queue, and a governed command input line.
Side-effecting commands require explicit approval before dispatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agent_term.store import DEFAULT_DB_PATH, EventStore
from agent_term.tui_model import PANE_ORDER, TuiSnapshotBuilder, title_for_pane

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.reactive import reactive
    from textual.widgets import Footer, Header, Label, ListItem, ListView, Log, Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False
    if TYPE_CHECKING:
        from textual.app import App, ComposeResult


_APPROVAL_REQUIRED_PREFIXES = (
    "/memory ",
    "/workroom ",
    "/meshrush ",
    "/sherlock ",
    "/agent ",
)


def _requires_approval(line: str) -> bool:
    return any(line.startswith(p) for p in _APPROVAL_REQUIRED_PREFIXES)


if _TEXTUAL_AVAILABLE:
    from textual.widgets import Input

    class AgentTermApp(App):  # type: ignore[misc]
        """Matrix-first terminal ChatOps console."""

        TITLE = "AgentTerm"
        SUB_TITLE = "SourceOS operator console"
        CSS = """
        Screen {
            layout: horizontal;
        }
        #sidebar {
            width: 24;
            border: solid $primary;
            overflow-y: auto;
        }
        #main {
            layout: vertical;
        }
        #event-log {
            border: solid $accent;
            height: 1fr;
        }
        #approval-bar {
            height: 3;
            border: solid $warning;
            display: none;
        }
        #approval-bar.visible {
            display: block;
        }
        #cmd-input {
            height: 3;
            border: solid $surface;
        }
        .pane-header {
            background: $primary;
            color: $text;
            padding: 0 1;
        }
        .approval-warning {
            color: $warning;
            padding: 0 1;
        }
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("ctrl+c", "quit", "Quit"),
        ]

        pending_command: reactive[str] = reactive("")

        def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
            super().__init__()
            self._db_path = db_path
            self._store = EventStore(db_path)
            self._builder = TuiSnapshotBuilder()
            self._snapshot = self._builder.build(self._store.iter_recent(limit=200))

        def compose(self) -> ComposeResult:
            yield Header()
            with Horizontal():
                with Vertical(id="sidebar"):
                    yield Static("Panes", classes="pane-header")
                    items = [ListItem(Label(title_for_pane(p))) for p in PANE_ORDER]
                    yield ListView(*items, id="pane-list")
                with Vertical(id="main"):
                    yield Log(id="event-log", highlight=True, markup=True)
                    yield Static("", id="approval-bar", classes="approval-warning")
                    yield Input(
                        placeholder="/ command or message…",
                        id="cmd-input",
                    )
            yield Footer()

        def on_mount(self) -> None:
            self._refresh_log()

        def _refresh_log(self) -> None:
            log = self.query_one("#event-log", Log)
            log.clear()
            text = self._snapshot.render_text()
            for line in text.splitlines():
                log.write_line(line)

        def on_input_submitted(self, event: Input.Submitted) -> None:
            line = event.value.strip()
            if not line:
                return
            approval_bar = self.query_one("#approval-bar", Static)
            if _requires_approval(line):
                approval_bar.add_class("visible")
                approval_bar.update(
                    f"[bold yellow]Approval required before dispatch:[/bold yellow] {line!r}  "
                    "— Confirm with /approve or /deny"
                )
                self.pending_command = line
                event.input.clear()
                return
            if line in ("/approve", "/y") and self.pending_command:
                self._dispatch_approved(self.pending_command)
                self.pending_command = ""
                approval_bar.remove_class("visible")
                approval_bar.update("")
            elif line in ("/deny", "/n"):
                self.pending_command = ""
                approval_bar.remove_class("visible")
                approval_bar.update("")
            else:
                self._dispatch_line(line)
            event.input.clear()

        def _dispatch_line(self, line: str) -> None:
            log = self.query_one("#event-log", Log)
            log.write_line(f"[dim]> {line}[/dim]")

        def _dispatch_approved(self, line: str) -> None:
            log = self.query_one("#event-log", Log)
            log.write_line(f"[green]✓ approved:[/green] {line}")

        def on_list_view_selected(self, event: ListView.Selected) -> None:
            idx = event.list_view.index
            if idx is None or idx >= len(PANE_ORDER):
                return
            pane_name = PANE_ORDER[idx]
            log = self.query_one("#event-log", Log)
            pane = self._snapshot.pane(pane_name)
            log.clear()
            log.write_line(f"[bold]{title_for_pane(pane_name)}[/bold]")
            for item in pane.items:
                status_marker = {
                    "approved": "[green]✓[/green]",
                    "denied": "[red]✗[/red]",
                    "pending": "[yellow]⏳[/yellow]",
                    "revoked": "[red]⊘[/red]",
                    "expired": "[dim]⌛[/dim]",
                }.get(item.status, "")
                log.write_line(f"  {status_marker} {item.text}")

        def on_unmount(self) -> None:
            self._store.close()


def run_tui(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Launch the AgentTerm Textual TUI."""
    if not _TEXTUAL_AVAILABLE:
        raise ImportError(
            "Textual is required for the TUI. Install it with:\n"
            "  pip install agent-term[textual]\n"
            "or:\n"
            "  pip install textual"
        )
    app = AgentTermApp(db_path=db_path)
    app.run()
