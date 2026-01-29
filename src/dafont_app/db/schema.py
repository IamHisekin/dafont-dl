from __future__ import annotations

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS categories (
  key TEXT PRIMARY KEY,
  theme_id INTEGER NOT NULL,
  name_pt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fonts (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category_key TEXT NOT NULL REFERENCES categories(key) ON DELETE RESTRICT,
  page_url TEXT NOT NULL,
  download_url TEXT NOT NULL,
  preview_ttf TEXT,
  first_seen TEXT,
  last_seen TEXT
);

CREATE INDEX IF NOT EXISTS idx_fonts_name ON fonts(name);
CREATE INDEX IF NOT EXISTS idx_fonts_category ON fonts(category_key);
"""
