from __future__ import annotations

import os
from pathlib import Path


def app_root() -> Path:
    # Allow overriding for portable mode
    override = os.environ.get("DAFONT_GUI_HOME")
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    return (home / ".dafont_gui").resolve()


def ensure_app_dirs() -> None:
    (app_root() / "logs").mkdir(parents=True, exist_ok=True)
    (app_root() / "data").mkdir(parents=True, exist_ok=True)
    (app_root() / "cache").mkdir(parents=True, exist_ok=True)
    (app_root() / "downloads").mkdir(parents=True, exist_ok=True)


def fontes_db_path() -> Path:
    return app_root() / "data" / "fontes.db"


def cache_db_path() -> Path:
    return app_root() / "cache" / "cache.db"


def downloads_dir() -> Path:
    return app_root() / "downloads"


def db_path() -> Path:
    """
    Caminho do fontes.db sincronizado.
    """
    data = app_root() / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data / "fontes.db"
