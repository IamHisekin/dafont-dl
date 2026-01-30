from __future__ import annotations

import sys


def detect_system_theme() -> str:
    """
    Returns: "dark" or "light"
    - Qt styleHints when available
    - Windows registry fallback
    - default: light
    """
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            cs = app.styleHints().colorScheme()
            if cs == Qt.ColorScheme.Dark:
                return "dark"
            if cs == Qt.ColorScheme.Light:
                return "light"
    except Exception:
        pass

    if sys.platform.startswith("win"):
        try:
            import winreg  # type: ignore

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                # 0 = dark, 1 = light
                val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                return "light" if int(val) == 1 else "dark"
        except Exception:
            pass

    return "light"
