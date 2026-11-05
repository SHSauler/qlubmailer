"""Main window: one window with four tabs."""

from PySide6.QtWidgets import QMainWindow, QTabWidget

from mailer import history
from mailer.config import load_config
from mailer.paths import DATA_DIR

from .compose_tab import ComposeTab
from .history_tab import HistoryTab
from .recipients_tab import RecipientsTab
from .settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QlubSender — club mail sender")
        self.resize(1100, 750)
        ok, msg = history.ensure_repo(DATA_DIR)
        self._config = load_config()

        self.tabs = QTabWidget()
        self.compose = ComposeTab(self.get_config, DATA_DIR, self)
        self.recipients_tab = RecipientsTab(DATA_DIR, self)
        self.history_tab = HistoryTab(DATA_DIR, self)
        self.settings_tab = SettingsTab(self)

        self.tabs.addTab(self.compose, "Compose & Send")
        self.tabs.addTab(self.recipients_tab, "Recipients")
        self.tabs.addTab(self.history_tab, "History")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage(msg if ok else f"History unavailable: {msg}", 8000)

    def get_config(self):
        # Settings tab is the source of truth if visible; else .env file.
        try:
            cfg = self.settings_tab.current_config()
            # If settings tab still has defaults and .env differs, prefer file.
            fresh = load_config()
            merged = dict(fresh)
            # Prefer on-screen edits (user may not have saved yet).
            for k, v in cfg.items():
                if v != fresh.get(k):
                    merged[k] = v
                elif k in fresh:
                    merged[k] = fresh[k]
            return merged
        except Exception:
            return load_config()

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) is self.history_tab:
            self.history_tab.refresh()
        elif self.tabs.widget(index) is self.compose:
            self.compose.reload_recipients_for_preview()
        elif self.tabs.widget(index) is self.settings_tab:
            self.settings_tab.reload()
