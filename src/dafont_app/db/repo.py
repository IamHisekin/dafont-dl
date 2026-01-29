from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


# Ajuste estes dataclasses para bater com o que você já usa no projeto.
# Se no seu projeto já existem, pode remover daqui e importar os existentes.
@dataclass(frozen=True)
class Category:
    key: str
    name_pt: str
    theme_id: int
    url: str


@dataclass(frozen=True)
class FontRow:
    slug: str
    name: str
    category_key: str
    page_url: str
    download_url: str
    preview_ttf: Optional[str] = None


class Repo:
    """
    Repo SQLite thread-safe para uso com QThread/ThreadPool.
    - Uma conexão SQLite compartilhada com check_same_thread=False
    - Lock para serializar operações (SQLite não é ótimo com acesso paralelo na mesma conexão)
    """

    def __init__(self, db_file: Path):
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()

        # ✅ A correção principal:
        self._conn = sqlite3.connect(
            str(self.db_file),
            timeout=30,
            check_same_thread=False,  # permite uso por threads diferentes
        )
        self._conn.row_factory = sqlite3.Row

        # Boas práticas p/ concorrência e performance
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")

        self._ensure_schema()

    def set_font_name(self, slug: str, name: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE fonts SET name=? WHERE slug=?",
                (name, slug),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    # -------------------- schema --------------------
    def _ensure_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()

            # 1) cria tabelas no formato mais novo (se não existirem)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    key TEXT PRIMARY KEY,
                    name_pt TEXT NOT NULL,
                    theme_id INTEGER NOT NULL,
                    url TEXT NOT NULL
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fonts (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category_key TEXT NOT NULL,
                    page_url TEXT NOT NULL,
                    download_url TEXT NOT NULL,
                    preview_ttf TEXT,
                    last_seen INTEGER DEFAULT (strftime('%s','now')),
                    FOREIGN KEY (category_key) REFERENCES categories(key)
                );
                """
            )

            # 2) migrações: adiciona colunas ausentes
            def _columns(table: str) -> set[str]:
                rows = cur.execute(f"PRAGMA table_info({table});").fetchall()
                # table_info: (cid, name, type, notnull, dflt_value, pk)
                return {r[1] for r in rows}

            cat_cols = _columns("categories")
            if "url" not in cat_cols:
                # adiciona coluna url (sem NOT NULL porque ALTER não permite facilmente),
                # depois preenche e seguimos.
                cur.execute("ALTER TABLE categories ADD COLUMN url TEXT;")
                cur.execute("UPDATE categories SET url='' WHERE url IS NULL;")

            font_cols = _columns("fonts")
            if "preview_ttf" not in font_cols:
                cur.execute("ALTER TABLE fonts ADD COLUMN preview_ttf TEXT;")
            if "last_seen" not in font_cols:
                cur.execute(
                    "ALTER TABLE fonts ADD COLUMN last_seen INTEGER DEFAULT (strftime('%s','now'));"
                )

            # 3) índices
            cur.execute("CREATE INDEX IF NOT EXISTS idx_fonts_name ON fonts(name);")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_fonts_category ON fonts(category_key);"
            )

            self._conn.commit()

    # -------------------- categories --------------------
    def upsert_categories(self, categories: Iterable[Category]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executemany(
                """
                INSERT INTO categories(key, name_pt, theme_id, url)
                VALUES(?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                  name_pt=excluded.name_pt,
                  theme_id=excluded.theme_id,
                  url=excluded.url
                """,
                [(c.key, c.name_pt, c.theme_id, (c.url or "")) for c in categories],
            )
            self._conn.commit()

    # -------------------- fonts --------------------
    def upsert_fonts(self, fonts: Iterable[FontRow]) -> int:
        """
        Retorna quantos registros foram inseridos/atualizados (aproximação via rowcount total).
        """
        rows = [
            (f.slug, f.name, f.category_key, f.page_url, f.download_url, f.preview_ttf)
            for f in fonts
        ]
        if not rows:
            return 0

        with self._lock:
            cur = self._conn.cursor()
            cur.executemany(
                """
                INSERT INTO fonts(slug, name, category_key, page_url, download_url, preview_ttf, last_seen)
                VALUES(?,?,?,?,?,?, strftime('%s','now'))
                ON CONFLICT(slug) DO UPDATE SET
                  name=excluded.name,
                  category_key=excluded.category_key,
                  page_url=excluded.page_url,
                  download_url=excluded.download_url,
                  preview_ttf=COALESCE(excluded.preview_ttf, fonts.preview_ttf),
                  last_seen=strftime('%s','now')
                """,
                rows,
            )
            self._conn.commit()
            return cur.rowcount if cur.rowcount is not None else len(rows)

    def set_preview_ttf(self, slug: str, preview_ttf: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE fonts SET preview_ttf=? WHERE slug=?",
                (preview_ttf, slug),
            )
            self._conn.commit()

    def get_font(self, slug: str) -> Optional[FontRow]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT slug, name, category_key, page_url, download_url, preview_ttf
                FROM fonts
                WHERE slug=?
                """,
                (slug,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return FontRow(
            slug=row["slug"],
            name=row["name"],
            category_key=row["category_key"],
            page_url=row["page_url"],
            download_url=row["download_url"],
            preview_ttf=row["preview_ttf"],
        )

    def search_fonts(
        self, query: str, category_key: str, limit: int = 2000
    ) -> list[FontRow]:
        q = (query or "").strip()
        params = []
        where = []

        if category_key and category_key != "all":
            where.append("category_key=?")
            params.append(category_key)

        if q:
            where.append("name LIKE ?")
            params.append(f"%{q}%")

        sql_where = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT slug, name, category_key, page_url, download_url, preview_ttf
            FROM fonts
            {sql_where}
            ORDER BY name COLLATE NOCASE ASC
            LIMIT ?
        """
        params.append(int(limit))

        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            rows = cur.fetchall()

        return [
            FontRow(
                slug=r["slug"],
                name=r["name"],
                category_key=r["category_key"],
                page_url=r["page_url"],
                download_url=r["download_url"],
                preview_ttf=r["preview_ttf"],
            )
            for r in rows
        ]
