#!/usr/bin/env python3
"""GUI entry point: python main.py"""

import logging
import sys

from mailer.paths import LOG_PATH, ensure_data_files


def main():
    ensure_data_files()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
    )
    from PySide6.QtWidgets import QApplication

    from gui.app import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
