"""Recipients tab: table editor for the fixed schema."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mailer import history, recipients as recipients_mod
from mailer.paths import RECIPIENTS_PATH


class RecipientsTab(QWidget):
    def __init__(self, data_dir, parent=None):
        super().__init__(parent)
        self.data_dir = data_dir
        layout = QVBoxLayout(self)

        self.info = QLabel("Fixed columns: firstName | lastName | mail. Red rows = validation errors.")
        layout.addWidget(self.info)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(recipients_mod.FIELDS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        for label, slot in [
            ("Add row", self.add_row),
            ("Delete selected", self.delete_selected),
            ("Reload", self.load),
            ("Save (commits version)", self.save),
            ("Import CSV", self.import_csv),
            ("Export CSV", self.export_csv),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        layout.addLayout(row)
        self.status = QLabel("")
        layout.addWidget(self.status)
        self._loading = False
        self.load()

    def _on_item_changed(self, *args):
        if self._loading:
            return
        self.validate_view()

    def rows(self):
        out = []
        for r in range(self.table.rowCount()):
            out.append(
                {
                    field: (self.table.item(r, c).text() if self.table.item(r, c) else "").strip()
                    for c, field in enumerate(recipients_mod.FIELDS)
                }
            )
        return out

    def load(self):
        self._loading = True
        try:
            try:
                recs = recipients_mod.load_recipients(RECIPIENTS_PATH)
            except FileNotFoundError:
                recs = []
            self.table.setRowCount(0)
            for rec in recs:
                self.table.insertRow(self.table.rowCount())
                for c, field in enumerate(recipients_mod.FIELDS):
                    self.table.setItem(
                        self.table.rowCount() - 1, c, QTableWidgetItem(rec.get(field, ""))
                    )
            self.status.setText(f"Loaded {len(recs)} recipient(s).")
        except Exception as e:
            QMessageBox.critical(self, "Load", f"Cannot load recipients: {e}")
        finally:
            self._loading = False
        self.validate_view()

    def validate_view(self):
        for r in range(self.table.rowCount()):
            rec = {
                field: (self.table.item(r, c).text() if self.table.item(r, c) else "")
                for c, field in enumerate(recipients_mod.FIELDS)
            }
            errors = recipients_mod.validate_recipient(rec)
            color = QColor(255, 220, 220) if errors else QColor(255, 255, 255)
            for c in range(3):
                item = self.table.item(r, c)
                if item is None:
                    item = QTableWidgetItem("")
                    self.table.setItem(r, c, item)
                item.setBackground(color)
                item.setToolTip("; ".join(errors))

    def add_row(self):
        self.table.insertRow(self.table.rowCount())
        for c in range(3):
            self.table.setItem(self.table.rowCount() - 1, c, QTableWidgetItem(""))
        self.validate_view()

    def delete_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self.validate_view()

    def save(self):
        recs = self.rows()
        bad = [(i, recipients_mod.validate_recipient(r)) for i, r in enumerate(recs)]
        bad = [(i, e) for i, e in bad if e]
        if bad:
            msg = "\n".join(f"row {i + 1}: {'; '.join(e)}" for i, e in bad[:10])
            reply = QMessageBox.question(
                self, "Invalid rows", f"Some rows are invalid:\n{msg}\n\nSave anyway?"
            )
            if reply != QMessageBox.Yes:
                return False
        try:
            RECIPIENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            recipients_mod.save_recipients(RECIPIENTS_PATH, recs)
        except Exception as e:
            QMessageBox.critical(self, "Save", f"Cannot save: {e}")
            return False
        committed, info = history.commit(self.data_dir, message="update recipients")
        self.status.setText(f"Saved {len(recs)} recipient(s). {info}")
        return True

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            recs = recipients_mod.load_csv(path)
        except Exception as e:
            QMessageBox.critical(self, "Import", f"Cannot import: {e}")
            return
        self._loading = True
        for rec in recs:
            self.table.insertRow(self.table.rowCount())
            for c, field in enumerate(recipients_mod.FIELDS):
                self.table.setItem(
                    self.table.rowCount() - 1, c, QTableWidgetItem(rec.get(field, ""))
                )
        self._loading = False
        self.validate_view()
        self.status.setText(f"Imported {len(recs)} row(s). Press Save to keep them.")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "recipients.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            recipients_mod.save_csv(path, self.rows())
            self.status.setText(f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export", f"Cannot export: {e}")
