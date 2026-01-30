from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from dafont_app.ui.main_window import MainWindow
from dafont_app.utils.paths import ensure_app_dirs
from dafont_app.utils.app_logging import setup_logging, install_excepthooks, install_qt_message_handler
from dafont_app.utils.settings import load_settings
from dafont_app.ui.theme import apply_theme


def main() -> None:
    ensure_app_dirs()
    setup_logging()
    install_excepthooks()
    install_qt_message_handler()

    app = QApplication(sys.argv)
    app.setApplicationName("DaFont Downloader")
    app.setOrganizationName("IgorBryan")

    s = load_settings()
    apply_theme(app, s.theme)

    win = MainWindow()
    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
