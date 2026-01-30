from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def resolved_color_scheme(mode: str) -> str:
    """
    Retorna 'dark' ou 'light'.
    mode pode ser: 'dark', 'light', 'system'
    """
    mode = (mode or "system").lower()
    if mode in ("dark", "light"):
        return mode

    app = QGuiApplication.instance()
    try:
        # Qt 6: QStyleHints.colorScheme()
        cs = app.styleHints().colorScheme() if app else None
        if cs == Qt.ColorScheme.Dark:
            return "dark"
        if cs == Qt.ColorScheme.Light:
            return "light"
    except Exception:
        pass

    # fallback: tenta inferir pela cor da janela padrão
    try:
        pal = app.palette() if app else None
        if pal:
            c = pal.window().color()
            # lightness 0..255
            return "dark" if c.lightness() < 128 else "light"
    except Exception:
        pass

    return "light"
