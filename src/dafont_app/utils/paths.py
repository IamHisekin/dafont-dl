from __future__ import annotations

import os
from pathlib import Path


def app_root() -> Path:
    # Cross-platform, no external deps.
    base = Path(os.environ.get("DAFONT_GUI_HOME", ""))
    if base:
        return base.expanduser().resolve()
    return (Path.home() / ".dafont_gui").resolve()


def db_path() -> Path:
    return app_root() / "dafont.sqlite3"


def downloads_dir() -> Path:
    return app_root() / "Downloads"


def ensure_app_dirs() -> None:
    app_root().mkdir(parents=True, exist_ok=True)
    downloads_dir().mkdir(parents=True, exist_ok=True)
