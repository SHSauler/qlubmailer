"""Compose tab: template + subject editing, preview, test/full send."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mailer import history, recipients as recipients_mod
from mailer.paths import RECIPIENTS_PATH, SUBJECT_PATH, TEMPLATE_PATH
from mailer.sender import render_template, sanitize_header_value

from .workers import SendWorker


def _read(path, default=""):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def _read_subject(default="Einladung"):
    """Load subject.txt as a single-line header value.

    subject.txt may contain trailing newlines or accidental line breaks
    (e.g. ``"Einladung\\nNov Dez"``); a raw QLineEdit would display that
    as ``"Einladung Nov Dez"`` while sending would fail with
    ``folded header contains newline``. Normalize to single line.
    """
    return sanitize_header_value(_read(SUBJECT_PATH, default)) or default


class ComposeTab(QWidget):
    log_signal = None

    def __init__(self, get_config, data_dir, parent=None):
        super().__init__(parent)
        self.get_config = get_config
        self.data_dir = data_dir
        self.worker = None
        self.recipients = []

        layout = QVBoxLayout(self)

        # Subject row
        subj_row = QHBoxLayout()
        subj_row.addWidget(QLabel("Subject:"))
        self.subject_edit = QLineEdit(_read_subject("Einladung"))
        subj_row.addWidget(self.subject_edit, 1)
        self.save_btn = QPushButton("Save (commits version)")
        self.save_btn.clicked.connect(self.save_files)
        subj_row.addWidget(self.save_btn)
        layout.addLayout(subj_row)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Template (Jinja2: {{ firstName }} {{ lastName }} {{ mail }} {{ name }}):"))
        self.template_edit = QPlainTextEdit(_read(TEMPLATE_PATH, ""))
        self.template_edit.setPlaceholderText("Sehr geehrter Herr {{ lastName }}, ...")
        left_layout.addWidget(self.template_edit, 1)

        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("Preview for:"))
        self.preview_combo = QComboBox()
        self.preview_combo.currentIndexChanged.connect(self.update_preview)
        preview_row.addWidget(self.preview_combo, 1)
        self.refresh_preview_btn = QPushButton("Refresh")
        self.refresh_preview_btn.clicked.connect(self.reload_recipients_for_preview)
        preview_row.addWidget(self.refresh_preview_btn)
        left_layout.addLayout(preview_row)

        self.preview_view = QTextEdit()
        self.preview_view.setReadOnly(True)
        left_layout.addWidget(self.preview_view, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Send"))
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Delay (s):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 3600)
        self.delay_spin.setValue(60)
        delay_row.addWidget(self.delay_spin, 1)
        right_layout.addLayout(delay_row)

        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("Test send (first recipient)")
        self.test_btn.clicked.connect(self.test_send)
        btn_row.addWidget(self.test_btn)
        self.send_btn = QPushButton("Send all others")
        self.send_btn.setToolTip("Sends to all recipients except the first (tester)")
        self.send_btn.clicked.connect(self.send_all)
        btn_row.addWidget(self.send_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_send)
        btn_row.addWidget(self.cancel_btn)
        right_layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        right_layout.addWidget(self.progress)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        right_layout.addWidget(self.log_view, 1)
        splitter.addWidget(right)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)

        self.reload_recipients_for_preview()
        self.template_edit.textChanged.connect(self.update_preview)
        try:
            cfg = self.get_config()
            self.delay_spin.setValue(float(cfg.get("SEND_DELAY", 60)))
        except (TypeError, ValueError):
            pass

    # -- data -----------------------------------------------------------
    def reload_recipients_for_preview(self):
        try:
            self.recipients = recipients_mod.load_recipients(RECIPIENTS_PATH)
        except Exception:
            self.recipients = []
        self.preview_combo.clear()
        for r in self.recipients:
            self.preview_combo.addItem(
                f"{recipients_mod.display_name(r)} <{r.get('mail', '')}>", r
            )
        self.update_preview()

    def current_template(self):
        return self.template_edit.toPlainText()

    def update_preview(self):
        idx = self.preview_combo.currentIndex()
        if idx < 0 or idx >= len(self.recipients):
            self.preview_view.setPlainText("(no recipients — add some in the Recipients tab)")
            return
        try:
            text = render_template(self.current_template(), self.recipients[idx])
        except Exception as e:
            text = f"Template error: {e}"
        self.preview_view.setPlainText(
            f"To: {self.recipients[idx].get('mail', '')}\n"
            f"Subject: {self.subject_edit.text()}\n\n{text}"
        )

    def append_log(self, msg):
        self.log_view.append(msg)

    # -- save -----------------------------------------------------------
    def save_files(self):
        TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TEMPLATE_PATH.write_text(self.current_template(), encoding="utf-8")
        clean_subject = sanitize_header_value(self.subject_edit.text())
        if clean_subject != self.subject_edit.text():
            self.subject_edit.setText(clean_subject)
        SUBJECT_PATH.write_text(clean_subject, encoding="utf-8")
        committed, info = history.commit(self.data_dir, message="update template/subject")
        self.append_log(f"Saved template + subject. {info}" if committed else f"Saved. {info}")
        return True

    # -- sending --------------------------------------------------------
    def _start_worker(self, recipients):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "A send is already running.")
            return
        self.save_files()
        try:
            self.recipients = recipients_mod.load_recipients(RECIPIENTS_PATH)
        except Exception as e:
            QMessageBox.critical(self, "Recipients", f"Cannot load recipients: {e}")
            return
        if not recipients:
            QMessageBox.warning(self, "No recipients", "Recipient list is empty.")
            return
        reply = QMessageBox.question(
            self, "Confirm send",
            f"Send to {len(recipients)} recipient(s)?",
        )
        if reply != QMessageBox.Yes:
            return
        self.progress.setMaximum(len(recipients))
        self.progress.setValue(0)
        self.send_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.worker = SendWorker(
            self.current_template(), recipients, self.subject_edit.text(),
            float(self.delay_spin.value()), self.get_config(),
        )
        self.worker.progressed.connect(self._on_progress)
        self.worker.log_line.connect(self.append_log)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, done, total, label):
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _on_finished(self, result):
        self.send_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.information(
            self, "Send finished",
            f"Successful: {result.get('successful', 0)}\nFailed: {result.get('failed', 0)}"
            + ("\nCancelled." if result.get("cancelled") else ""),
        )

    def send_all(self):
        """Send to all recipients except the first (tester)."""
        try:
            recs = recipients_mod.load_recipients(RECIPIENTS_PATH)
        except Exception as e:
            QMessageBox.critical(self, "Recipients", f"Cannot load recipients: {e}")
            return
        if len(recs) <= 1:
            QMessageBox.warning(
                self, "No recipients",
                "No other recipients besides the tester (first entry).",
            )
            return
        self._start_worker(recs[1:])

    def test_send(self):
        try:
            recs = recipients_mod.load_recipients(RECIPIENTS_PATH)
        except Exception as e:
            QMessageBox.critical(self, "Recipients", f"Cannot load recipients: {e}")
            return
        if not recs:
            QMessageBox.warning(self, "No recipients", "Recipient list is empty.")
            return
        self._start_worker(recs[:1])

    def cancel_send(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.append_log("Cancelling after current mail...")
