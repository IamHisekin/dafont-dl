from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import requests

ProgressCb = Optional[Callable[[str], None]]


def download_zip(download_url: str, slug: str, target_dir: Path) -> str:
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"{slug}.zip"

    s = requests.Session()
    s.headers.update({"User-Agent": "dafont_app/1.0", "Accept": "*/*"})
    r = s.get(download_url, timeout=(10, 60), allow_redirects=True)
    r.raise_for_status()
    out.write_bytes(r.content)
    return str(out)


def _sanitize(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name or "fonte"


def download_zip_from_url(
    url: str, suggested_name: str, target_dir: Path, progress: ProgressCb = None
) -> str:
    target_dir.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers.update({"User-Agent": "dafont_app/1.0", "Accept": "*/*"})

    if progress:
        progress("Conectando…")
    r = s.get(url, timeout=(10, 90), allow_redirects=True, stream=True)

    try:
        r.raise_for_status()
    except Exception:
        code = getattr(r, "status_code", None)

        # 404: link .font inválido / fonte não existe
        if code == 404:
            raise RuntimeError(f"Fonte não encontrada (404): {url}") from None

        # outros status
        raise RuntimeError(f"Falha HTTP {code}: {url}") from None

    filename = None
    cd = r.headers.get("Content-Disposition") or ""
    m = re.search(r'filename="?([^"]+)"?', cd, flags=re.IGNORECASE)
    if m:
        filename = m.group(1)

    if not filename:
        try:
            p = urlparse(r.url)
            last = (p.path or "").rstrip("/").split("/")[-1]
            filename = last or None
        except Exception:
            filename = None

    if filename and not filename.lower().endswith(".zip"):
        filename += ".zip"
    if not filename:
        filename = _sanitize(suggested_name) + ".zip"

    out = target_dir / _sanitize(Path(filename).stem)
    out = out.with_suffix(".zip")

    total = int(r.headers.get("Content-Length") or 0)
    got = 0
    with open(out, "wb") as f:
        for chunk in r.iter_content(chunk_size=256 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            got += len(chunk)
            if progress and total:
                progress(f"Baixando… {got}/{total} bytes")

    if progress:
        progress("Download concluído.")
    return str(out)
