"""
TUI dashboard for Daedelus.

This file implements the main Textual application for the Daedelus dashboard,
following the plan outlined in .devdocs/11_GUI_IMPLEMENTATION.md.

Created by: orpheus497
"""

import logging

# Import with graceful degradation
try:
    from textual.app import App, ComposeResult
    from textual.containers import Container
    from textual.widgets import Footer, Header, TabbedContent, TabPane

    from daedelus.ui.ipc_client import DashboardIPCClient
    from daedelus.ui.screens.analytics import AnalyticsScreen
    from daedelus.ui.screens.history import HistoryScreen
    from daedelus.ui.screens.overview import OverviewScreen
    from daedelus.ui.screens.prompts import PromptsScreen
    from daedelus.ui.screens.settings import SettingsScreen

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    logging.warning("textual is not available - dashboard disabled")


if TEXTUAL_AVAILABLE:

    class DashboardApp(App):
        """Daedelus TUI Dashboard Application."""

        TITLE = "Daedelus Dashboard"
        SUB_TITLE = "v0.3.0"

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("ctrl+t", "toggle_tab", "Toggle Tab"),
        ]

        def __init__(self, *args, **kwargs):
            """Initialize the dashboard app."""
            super().__init__(*args, **kwargs)
            self.ipc_client = DashboardIPCClient()

        def compose(self) -> ComposeResult:
            """Create child widgets for the app."""
            yield Header()
            with TabbedContent(initial="overview"):
                with TabPane("Overview", id="overview"):
                    yield OverviewScreen(ipc_client=self.ipc_client)
                with TabPane("History", id="history"):
                    yield HistoryScreen(ipc_client=self.ipc_client)
                with TabPane("NLP Prompts", id="prompts"):
                    yield PromptsScreen(ipc_client=self.ipc_client)
                with TabPane("Analytics", id="analytics"):
                    yield AnalyticsScreen(ipc_client=self.ipc_client)
                with TabPane("Settings", id="settings"):
                    yield SettingsScreen(ipc_client=self.ipc_client)
            yield Footer()

        def on_mount(self) -> None:
            """Called when the app is mounted."""
            if self.ipc_client.is_connected():
                logging.info("DashboardApp mounted - connected to daemon")
                self.sub_title = "v0.3.0 [Connected]"
            else:
                logging.warning("DashboardApp mounted - daemon not reachable (using mock data)")
                self.sub_title = "v0.3.0 [Disconnected]"

        def action_toggle_tab(self) -> None:
            """Action to toggle between tabs."""
            tabs = self.query_one(TabbedContent)
            tabs.action_next_tab()

    def run_dashboard() -> None:
        """Run the dashboard interface."""
        if TEXTUAL_AVAILABLE:
            app = DashboardApp()
            app.run()
        else:
            print("Textual is not installed. Please run 'pip install textual'")

else:

    def run_dashboard() -> None:
        """Fallback function when Textual is not available."""
        print("Textual is not installed. Please run 'pip install textual'")


if __name__ == "__main__":
    # A simple way to test the dashboard directly
    run_dashboard()
