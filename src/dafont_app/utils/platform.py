from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

def open_folder(path: Path) -> None:
    p = str(path)
    if sys.platform.startswith("win"):
        os.startfile(p)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])
