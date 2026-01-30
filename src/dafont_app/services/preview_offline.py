from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

from dafont_app.utils.paths import app_root


ProgressCb = Optional[Callable[[str], None]]
RGBA = Tuple[int, int, int, int]


@dataclass(frozen=True)
class PreviewResult:
    slug: str
    text: str
    image_path: Path
    font_file: str


class OfflinePreviewService:
    """
    Cache persistente durante a sessão.
    (O app limpa os caches ao fechar, por pedido do usuário.)
    """
    def __init__(self, timeout: float = 25.0, auto_cleanup: bool = False):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "dafont_app/1.0", "Accept": "*/*"})

        root = app_root()
        self.cache_dir = root / "cache"
        self.zip_dir = self.cache_dir / "zips"
        self.font_dir = self.cache_dir / "fonts"
        self.preview_dir = self.cache_dir / "previews"
        for d in (self.zip_dir, self.font_dir, self.preview_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.auto_cleanup = auto_cleanup

    def _progress(self, cb: ProgressCb, msg: str) -> None:
        if cb:
            cb(msg)

    def _zip_path(self, slug: str) -> Path:
        return self.zip_dir / f"{slug}.zip"

    def _pick_font_member(self, z: zipfile.ZipFile) -> str | None:
        members = [m for m in z.namelist() if m.lower().endswith((".ttf", ".otf")) and not m.endswith("/")]
        if not members:
            return None
        members.sort(key=lambda s: (0 if s.lower().endswith(".ttf") else 1, len(s), s.lower()))
        return members[0]

    def _font_cache_path(self, slug: str, member_name: str) -> Path:
        safe = member_name.replace("\\", "/").split("/")[-1]
        return self.font_dir / f"{slug}__{safe}"

    def ensure_zip_cached(self, slug: str, download_url: str, progress: ProgressCb = None) -> Path:
        zp = self._zip_path(slug)
        if zp.exists() and zp.stat().st_size > 0:
            return zp

        self._progress(progress, "Baixando ZIP para cache…")
        r = self._session.get(download_url, timeout=(10, self.timeout), allow_redirects=True)
        r.raise_for_status()
        data = r.content
        zp.write_bytes(data)
        self._progress(progress, f"ZIP cacheado. bytes={len(data)}")
        return zp

    def ensure_font_extracted(self, slug: str, zip_path: Path, progress: ProgressCb = None) -> tuple[Path, str]:
        with zipfile.ZipFile(zip_path, "r") as z:
            member = self._pick_font_member(z)
            if not member:
                raise RuntimeError("ZIP não contém .ttf/.otf")

            out_path = self._font_cache_path(slug, member)
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path, member

            self._progress(progress, "Extraindo fonte do ZIP…")
            out_path.write_bytes(z.read(member))
            self._progress(progress, f"Fonte extraída: {out_path.name}")
            return out_path, member

    def _preview_key(self, slug: str, font_path: Path, text: str, size: int, width: int, fg: RGBA) -> str:
        h = hashlib.sha256()
        h.update(slug.encode("utf-8"))
        h.update(b"|")
        h.update(font_path.name.encode("utf-8"))
        h.update(b"|")
        h.update(text.encode("utf-8"))
        h.update(b"|")
        h.update(str(size).encode("ascii"))
        h.update(b"|")
        h.update(str(width).encode("ascii"))
        h.update(b"|")
        h.update(bytes(fg))
        return h.hexdigest()[:24]

    def render_preview(
        self,
        slug: str,
        download_url: str,
        text: str,
        progress: ProgressCb = None,
        size: int = 64,
        width: int = 900,
        padding: int = 18,
        fg: RGBA = (255, 255, 255, 235),
    ) -> PreviewResult:
        text = (text or "").strip() or "Teste"

        zip_path = self.ensure_zip_cached(slug, download_url, progress=progress)
        font_path, member = self.ensure_font_extracted(slug, zip_path, progress=progress)

        key = self._preview_key(slug, font_path, text, size, width, fg)
        out = self.preview_dir / f"{slug}__{key}.png"
        if out.exists() and out.stat().st_size > 0:
            return PreviewResult(slug=slug, text=text, image_path=out, font_file=member)

        self._progress(progress, "Renderizando prévia (offline)…")

        try:
            font = ImageFont.truetype(str(font_path), size=size)
        except Exception:
            font = ImageFont.load_default()

        dummy = Image.new("RGBA", (width, 10), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_h = max(1, bbox[3] - bbox[1])
        height = max(120, text_h + padding * 2)

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        x = padding
        y = (height - text_h) // 2

        # sombra adaptativa
        if fg[0] + fg[1] + fg[2] > (255 * 3) // 2:
            shadow = (0, 0, 0, 120)
        else:
            shadow = (255, 255, 255, 110)

        draw.text((x + 2, y + 2), text, font=font, fill=shadow)
        draw.text((x, y), text, font=font, fill=fg)

        img.save(out, "PNG")
        self._progress(progress, f"Prévia gerada: {out.name}")
        return PreviewResult(slug=slug, text=text, image_path=out, font_file=member)
