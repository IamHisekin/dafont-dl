from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import requests


def download_zip_to_dir(url: str, slug: str, target_dir: Path, progress: Optional[Callable[[str], None]] = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"{slug}.zip"
    with requests.get(url, timeout=60) as r:
        r.raise_for_status()
        data = r.content
    out.write_bytes(data)
    if progress:
        progress(f"Download concluído: {out}")
    return out
