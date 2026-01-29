from __future__ import annotations

from pathlib import Path

import requests

from dafont_app.utils.paths import downloads_dir


class DownloadError(RuntimeError):
    pass


def _safe_filename(name: str) -> str:
    keep: list[str] = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)


def download_zip(download_url: str, slug: str, target_dir: Path | None = None) -> Path:
    """Download the font zip from DaFont.

    Returns the path to the saved zip.
    """
    target_dir = target_dir or downloads_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    file_name = _safe_filename(slug.replace("-", "_")) + ".zip"
    out_path = target_dir / file_name

    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    try:
        with requests.get(download_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        # Cleanup partial file
        if out_path.exists():
            try:
                out_path.unlink()
            except Exception:
                pass
        raise DownloadError(str(e)) from e

    return out_path
