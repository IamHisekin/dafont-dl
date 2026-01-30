from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple


@dataclass(frozen=True)
class FontRecord:
    name: str
    slug: str
    page_url: str
    download_url: str
    first_letter: str


_SLUG_RE = re.compile(r"/([^/]+)\.font(?:$|\?)", re.IGNORECASE)


def _slug_from_link(link: str) -> str:
    m = _SLUG_RE.search(link or "")
    if m:
        return m.group(1)
    # fallback: last path segment
    seg = (link or "").rstrip("/").split("/")[-1]
    return seg.replace(".font", "").strip()


def _first_letter(name: str) -> str:
    if not name:
        return "#"
    ch = name.strip()[:1].upper()
    return ch if ("A" <= ch <= "Z") else "#"


class Repo:
    """
    Repo para o schema do seu fontes.db (tabela: fontes com colunas: nome, link, link_download).

    - name: coluna 'nome'
    - page_url: coluna 'link'
    - download_url: coluna 'link_download'
    - slug: derivado do 'link' (…/pt/<slug>.font)
    """
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # ------------------ queries ------------------

    def _where_letter(self, letter: str) -> tuple[str, list]:
        if letter == "#":
            return "NOT (upper(substr(nome,1,1)) BETWEEN 'A' AND 'Z')", []
        return "upper(substr(nome,1,1)) = ?", [letter]

    def count_fonts(self, query: str, letter: str) -> int:
        q = (query or "").strip()
        where_letter, params = self._where_letter(letter)
        sql = f"SELECT COUNT(1) FROM fontes WHERE {where_letter}"
        if q:
            sql += " AND nome LIKE ?"
            params.append(f"%{q}%")
        return int(self._conn.execute(sql, params).fetchone()[0])

    def search_fonts(self, query: str, letter: str, limit: int = 100, offset: int = 0) -> list[FontRecord]:
        q = (query or "").strip()
        where_letter, params = self._where_letter(letter)
        sql = f"SELECT nome, link, link_download FROM fontes WHERE {where_letter}"
        if q:
            sql += " AND nome LIKE ?"
            params.append(f"%{q}%")
        sql += " ORDER BY nome COLLATE NOCASE ASC LIMIT ? OFFSET ?"
        params.extend([int(limit), int(offset)])

        rows = self._conn.execute(sql, params).fetchall()
        out: list[FontRecord] = []
        for r in rows:
            name = (r["nome"] or "").strip()
            page_url = (r["link"] or "").strip()
            download_url = (r["link_download"] or "").strip()
            slug = _slug_from_link(page_url)
            out.append(
                FontRecord(
                    name=name or slug,
                    slug=slug,
                    page_url=page_url or f"https://www.dafont.com/pt/{slug}.font",
                    download_url=download_url or f"https://dl.dafont.com/dl/?f={slug}",
                    first_letter=_first_letter(name),
                )
            )
        return out

    def get_font(self, slug: str) -> Optional[FontRecord]:
        s = (slug or "").strip()
        if not s:
            return None
        # match in link; safest available key
        row = self._conn.execute(
            "SELECT nome, link, link_download FROM fontes WHERE link LIKE ? LIMIT 1",
            (f"%/{s}.font%",),
        ).fetchone()
        if not row:
            return None
        name = (row["nome"] or "").strip()
        page_url = (row["link"] or "").strip()
        download_url = (row["link_download"] or "").strip()
        return FontRecord(
            name=name or s,
            slug=s,
            page_url=page_url or f"https://www.dafont.com/pt/{s}.font",
            download_url=download_url or f"https://dl.dafont.com/dl/?f={s}",
            first_letter=_first_letter(name),
        )
