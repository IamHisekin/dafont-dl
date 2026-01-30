from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dafont_app.utils.paths import app_root

ThemeMode = Literal["system", "dark", "light"]

@dataclass
class AppSettings:
    theme: ThemeMode = "system"

def settings_path() -> Path:
    p = app_root() / "config"
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"

def load_settings() -> AppSettings:
    path = settings_path()
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        theme = data.get("theme", "system")
        if theme not in ("system", "dark", "light"):
            theme = "system"
        return AppSettings(theme=theme)
    except Exception:
        return AppSettings()

def save_settings(s: AppSettings) -> None:
    path = settings_path()
    data: dict[str, Any] = {"theme": s.theme}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
