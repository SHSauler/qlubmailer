"""History tab: git log / diff / restore for data/ files."""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtCore import Qt

from mailer import history


class HistoryTab(QWidget):
    def __init__(self, data_dir, parent=None):
        super().__init__(parent)
        self.data_dir = data_dir
        self.entries = []
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("File:"))
        self.file_combo = QComboBox()
        self.file_combo.addItems(history.TRACKED_FILES)
        self.file_combo.currentTextChanged.connect(lambda _t: self.refresh())
        top.addWidget(self.file_combo, 1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        self.restore_btn = QPushButton("Restore selected version")
        self.restore_btn.clicked.connect(self.restore)
        top.addWidget(self.restore_btn)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_diff)
        splitter.addWidget(self.list)
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFontFamily("monospace")
        splitter.addWidget(self.diff_view)
        splitter.setSizes([350, 650])
        layout.addWidget(splitter, 1)
        self.status = QLabel("")
        layout.addWidget(self.status)
        self.refresh()

    def refresh(self):
        filename = self.file_combo.currentText()
        self.entries = history.file_log(self.data_dir, filename) or history.log(self.data_dir)
        self.list.clear()
        for e in self.entries:
            self.list.addItem(f"{e['short']} {e['date'][:16]} {e['message']}")
        self.status.setText(f"{len(self.entries)} commit(s) for {filename}." if self.entries else "No history yet (save once to create a commit).")
        if self.entries:
            self.list.setCurrentRow(0)

    def show_diff(self, row):
        if row < 0 or row >= len(self.entries):
            self.diff_view.clear()
            return
        filename = self.file_combo.currentText()
        rev = self.entries[row]["hash"]
        # Diff selected commit against its parent = what changed in that commit.
        content = history.diff(self.data_dir, filename, rev + "^", rev)
        if not content.strip():
            content = history.show(self.data_dir, filename, rev)
        self.diff_view.setPlainText(content or "(no diff)")

    def restore(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self.entries):
            QMessageBox.warning(self, "Restore", "Select a version first.")
            return
        filename = self.file_combo.currentText()
        rev = self.entries[row]["hash"]
        reply = QMessageBox.question(
            self, "Restore",
            f"Restore {filename} to version {self.entries[row]['short']}?\nCurrent content will be overwritten (and committed).",
        )
        if reply != QMessageBox.Yes:
            return
        ok, info = history.restore(self.data_dir, filename, rev)
        QMessageBox.information(self, "Restore", info)
        self.refresh()
