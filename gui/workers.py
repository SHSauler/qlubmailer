"""Background workers so sending never blocks the GUI."""

from PySide6.QtCore import QThread, Signal


class SendWorker(QThread):
    progressed = Signal(int, int, str)  # done, total, label
    log_line = Signal(str)
    finished_ok = Signal(dict)  # result dict

    def __init__(self, template_text, recipients, subject, delay, config, parent=None):
        super().__init__(parent)
        self.template_text = template_text
        self.recipients = list(recipients)
        self.subject = subject
        self.delay = delay
        self.config = dict(config)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        from mailer.sender import send_emails

        def should_cancel():
            return self._cancel

        result = send_emails(
            self.template_text,
            self.recipients,
            self.subject,
            delay_seconds=self.delay,
            config=self.config,
            progress_callback=lambda d, t, r: self.progressed.emit(d, t, str(r.get("mail", ""))),
            log_callback=self.log_line.emit,
            should_cancel=should_cancel,
        )
        self.finished_ok.emit(result)


class TestConnectionWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = dict(config)

    def run(self):
        from mailer.sender import test_connection

        ok, msg = test_connection(self.config)
        self.done.emit(ok, msg)
