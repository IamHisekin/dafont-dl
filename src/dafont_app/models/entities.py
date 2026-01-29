from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Category:
    id: int
    key: str  # internal key, e.g. "fantasia"
    theme_id: int  # dafont mtheme id
    name_pt: str

    @property
    def url(self) -> str:
        return f"https://www.dafont.com/pt/mtheme.php?id={self.theme_id}"


@dataclass(frozen=True)
class Font:
    slug: str  # e.g. "sakuna"
    name: str
    category_key: str
    page_url: str
    download_url: str
    preview_ttf: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
