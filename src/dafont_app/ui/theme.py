from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

ThemeMode = str  # "system" | "dark" | "light"


def _palette_dark() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#0f141c"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e8eef7"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#0b111a"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#101a28"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#0f141c"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8eef7"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e8eef7"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#121a26"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e8eef7"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#2b66f6"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link, QColor("#7aa7ff"))
    return pal


def _palette_light() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#f6f8fb"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#111827"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#f0f4f8"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#111827"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#111827"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#111827"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#2b66f6"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link, QColor("#245dff"))
    return pal


_BASE_QSS = r"""
QWidget { font-size: 10.5pt; }

QFrame#Card {
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.06);
}

QLineEdit, QComboBox, QPushButton, QToolButton {
  border-radius: 12px;
  padding: 8px 10px;
}

QTableView {
  border-radius: 14px;
}

QHeaderView::section {
  padding: 6px 8px;
  border: none;
}
"""

_QSS_LIGHT_EXTRA = r"""
QCheckBox::indicator {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(17, 24, 39, 0.55);   /* borda escura no claro */
  background: rgba(255, 255, 255, 1.0);
}
QCheckBox::indicator:hover {
  border: 1px solid rgba(17, 24, 39, 0.85);
}
QCheckBox::indicator:checked {
  background: palette(Highlight);
  border: 1px solid palette(Highlight);
}
QCheckBox::indicator:checked:hover {
  border: 1px solid palette(Highlight);
}
"""

_QSS_DARK_EXTRA = r"""
QCheckBox::indicator {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(232, 238, 247, 0.35); /* borda clara no escuro */
  background: rgba(18, 26, 38, 1.0);
}
QCheckBox::indicator:hover {
  border: 1px solid rgba(232, 238, 247, 0.60);
}
QCheckBox::indicator:checked {
  background: palette(Highlight);
  border: 1px solid palette(Highlight);
}
"""


def apply_theme(app: QApplication, mode: ThemeMode) -> None:
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)

    if (mode or "system").lower() == "system":
        from dafont_app.utils.system_theme import detect_system_theme

        mode = detect_system_theme()

    if mode == "dark":
        app.setPalette(_palette_dark())
        extra = _QSS_DARK_EXTRA
    else:
        app.setPalette(_palette_light())
        extra = _QSS_LIGHT_EXTRA

    app.setStyleSheet(_BASE_QSS)
