from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class FontRow:
    slug: str
    name: str
    page_url: str
    download_url: str
    letter: str


def _slug_from_url(page_url: str) -> str:
    p = urlparse(page_url)
    last = (p.path or "").rstrip("/").split("/")[-1]
    if last.endswith(".font"):
        slug = re.sub(r"[^a-z0-9_-]+", "", last[:-5].lower())
        return slug or last[:-5].lower()
    return re.sub(r"[^a-z0-9_-]+", "", last.lower()) or last.lower()


def _letter_from_name(name: str) -> str:
    if not name:
        return "#"
    ch = name[0].upper()
    return ch if "A" <= ch <= "Z" else "#"


class SourceRepo:
    def __init__(self, fontes_db: Path) -> None:
        self.fontes_db = fontes_db
        self._conn = sqlite3.connect(str(self.fontes_db))
        self._conn.execute("PRAGMA query_only=ON;")

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def count_by_letter(self, letter: str, q: str = "") -> int:
        letter = letter.upper()
        qlike = f"%{q}%"
        if letter == "#":
            sql = "SELECT COUNT(1) FROM fontes WHERE upper(substr(nome,1,1)) NOT BETWEEN 'A' AND 'Z' AND lower(nome) LIKE lower(?)"
            return int(self._conn.execute(sql, (qlike,)).fetchone()[0])
        else:
            sql = "SELECT COUNT(1) FROM fontes WHERE upper(substr(nome,1,1))=? AND lower(nome) LIKE lower(?)"
            return int(self._conn.execute(sql, (letter, qlike)).fetchone()[0])

    def list_by_letter(self, letter: str, q: str = "", limit: int = 100, offset: int = 0) -> list[FontRow]:
        letter = letter.upper()
        qlike = f"%{q}%"
        if letter == "#":
            sql = (
                "SELECT nome, link, link_download FROM fontes "
                "WHERE upper(substr(nome,1,1)) NOT BETWEEN 'A' AND 'Z' AND lower(nome) LIKE lower(?) "
                "ORDER BY nome LIMIT ? OFFSET ?"
            )
            rows = self._conn.execute(sql, (qlike, limit, offset)).fetchall()
        else:
            sql = (
                "SELECT nome, link, link_download FROM fontes "
                "WHERE upper(substr(nome,1,1))=? AND lower(nome) LIKE lower(?) "
                "ORDER BY nome LIMIT ? OFFSET ?"
            )
            rows = self._conn.execute(sql, (letter, qlike, limit, offset)).fetchall()

        out: list[FontRow] = []
        for nome, link, link_download in rows:
            slug = _slug_from_url(link)
            name = str(nome)
            out.append(FontRow(slug=slug, name=name, page_url=str(link), download_url=str(link_download), letter=_letter_from_name(name)))
        return out
