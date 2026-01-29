from __future__ import annotations

from dafont_app.models.entities import Category

CATEGORIES: list[Category] = [
    Category(id=1, key="fantasia", theme_id=1, name_pt="Fantasia"),
    Category(id=2, key="estrangeiras", theme_id=2, name_pt="Estrangeiras"),
    Category(id=3, key="tecno", theme_id=3, name_pt="Tecno"),
    Category(id=4, key="gotica", theme_id=4, name_pt="Gótica"),
    Category(id=5, key="basica", theme_id=5, name_pt="Básica"),
    Category(id=6, key="escrita", theme_id=6, name_pt="Escrita"),
    Category(id=7, key="dingbats", theme_id=7, name_pt="Dingbats"),
    Category(id=8, key="festas", theme_id=8, name_pt="Festas"),
]

CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}
