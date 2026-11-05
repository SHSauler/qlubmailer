"""Settings tab: edit .env (password shown in plain text per request)."""

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mailer.config import FIELD_DEFS, load_config, save_config

from .workers import TestConnectionWorker


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.edits = {}
        self.worker = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings are stored in .env (password visible, as requested). .env is never committed to history."))

        form = QFormLayout()
        config = load_config()
        for key, label, _default in FIELD_DEFS:
            edit = QLineEdit(config.get(key, ""))
            edit.setObjectName(key)
            self.edits[key] = edit
            form.addRow(label + f"  [{key}]", edit)
        layout.addLayout(form)

        row = QHBoxLayout()
        self.save_btn = QPushButton("Save settings")
        self.save_btn.clicked.connect(self.save)
        row.addWidget(self.save_btn)
        self.test_btn = QPushButton("Test SMTP connection")
        self.test_btn.clicked.connect(self.test_connection)
        row.addWidget(self.test_btn)
        self.status = QLabel("")
        row.addWidget(self.status, 1)
        layout.addLayout(row)
        layout.addStretch(1)

    def current_config(self):
        return {key: edit.text() for key, edit in self.edits.items()}

    def save(self):
        try:
            save_config(self.current_config())
            self.status.setText("Saved to .env")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save", f"Cannot save .env: {e}")
            return False

    def reload(self):
        config = load_config()
        for key, edit in self.edits.items():
            edit.setText(config.get(key, ""))

    def test_connection(self):
        if self.worker and self.worker.isRunning():
            return
        self.status.setText("Testing...")
        self.test_btn.setEnabled(False)
        self.worker = TestConnectionWorker(self.current_config(), self)
        self.worker.done.connect(self._on_test_done)
        self.worker.start()

    def _on_test_done(self, ok, msg):
        self.test_btn.setEnabled(True)
        self.status.setText(msg)
        QMessageBox.information(self, "SMTP test", msg)
