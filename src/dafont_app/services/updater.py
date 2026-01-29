from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from dafont_app.services.catalog import CATEGORIES
from dafont_app.services.dafont_client import DaFontClient
from dafont_app.models.entities import Font, Category


@dataclass(frozen=True)
class UpdateResult:
    new_fonts: int
    total_seen: int


class DatabaseUpdater:
    def __init__(self, repo, client: DaFontClient, progress_cb: Optional[Callable[[str], None]] = None) -> None:
        self.repo = repo
        self.client = client
        self.progress_cb = progress_cb

    def _progress(self, msg: str) -> None:
        if self.progress_cb:
            self.progress_cb(msg)

    @staticmethod
    def _extract_slug_from_href(href: str) -> str | None:
        p = urlparse(href)
        last = (p.path or "").rstrip("/").split("/")[-1]
        if not last.endswith(".font"):
            return None
        slug = re.sub(r"[^a-z0-9_-]+", "", last[:-5].lower())
        return slug or None

    def _parse_listing_page(self, html: str, category: Category) -> list[Font]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Font] = []
        seen: set[str] = set()
        base = "https://www.dafont.com"

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if ".font" not in href:
                continue
            abs_url = urljoin(base, href)
            slug = self._extract_slug_from_href(abs_url)
            if not slug or slug in seen:
                continue
            seen.add(slug)

            name = (a.get_text(strip=True) or "").strip() or slug.replace("-", " ").title()

            out.append(
                Font(
                    slug=slug,
                    name=name,
                    category_key=category.key,
                    page_url=f"https://www.dafont.com/pt/{slug}.font",
                    download_url=f"https://dl.dafont.com/dl/?f={slug}",
                    preview_ttf=None,
                )
            )
        return out

    def update_all_categories(self) -> UpdateResult:
        total_new = 0
        total_seen = 0
        self._progress("Atualização iniciada: varrendo categorias…")

        for cat in CATEGORIES:
            self._progress(f"Categoria: {cat.name_pt} (id={cat.theme_id})")
            last_page = self.client.get_last_page_for_category(cat) or 1
            for page in range(1, last_page + 1):
                self._progress(f"  Página {page}/{last_page}…")
                url = f"{cat.url}&page={page}" if "?" in cat.url else f"{cat.url}?page={page}"
                html = self.client.fetch_html(url)
                fonts = self._parse_listing_page(html, cat)
                inserted = self.repo.upsert_fonts(fonts)
                total_seen += len(fonts)
                total_new += max(inserted, 0)
                self._progress(f"    Itens: {len(fonts)} | +{max(inserted, 0)} novas")

        self._progress(f"Atualização concluída: +{total_new} novas | total vistas: {total_seen}")
        return UpdateResult(new_fonts=total_new, total_seen=total_seen)
