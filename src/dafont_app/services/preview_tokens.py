from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import requests


class PreviewTokenError(RuntimeError):
    pass


@dataclass(frozen=True)
class TokensResult:
    tokens: list[str]
    source: str  # 'cache' or 'zip'


class PreviewTokenService:
    """Deriva tokens de preview a partir do ZIP (sem puxar HTML do site).

    A imagem do DaFont usa `ttf=<token>` que geralmente corresponde ao nome do arquivo .ttf/.otf dentro do ZIP.
    Ex.: academy0.ttf -> token academy0
    """

    def __init__(self, cache_repo, timeout: float = 45.0) -> None:
        self.cache_repo = cache_repo
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "dafont_app/0.3 (+preview-token)",
                "Accept": "*/*",
            }
        )

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    @staticmethod
    def _normalize_token(name: str) -> str:
        name = name.strip().rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return re.sub(r"[^a-z0-9_-]+", "", name.lower())

    def get_tokens(self, slug: str, download_url: str, progress: Optional[Callable[[str], None]] = None) -> TokensResult:
        cached = self.cache_repo.get_preview_tokens(slug)
        if cached:
            return TokensResult(tokens=cached, source="cache")

        if progress:
            progress("Baixando ZIP para derivar preview…")

        r = self._session.get(download_url, timeout=self.timeout)
        r.raise_for_status()

        # DaFont returns zip bytes
        data = io.BytesIO(r.content)
        try:
            z = zipfile.ZipFile(data)
        except Exception as e:
            raise PreviewTokenError(f"Não foi possível abrir ZIP: {e}")

        tokens: list[str] = []
        # Prefer ttf/otf in root or nested
        for info in z.infolist():
            name = info.filename
            low = name.lower()
            if low.endswith(".ttf") or low.endswith(".otf"):
                tok = self._normalize_token(name)
                if tok and tok not in tokens:
                    tokens.append(tok)
            if len(tokens) >= 6:
                break

        if not tokens:
            raise PreviewTokenError("Nenhum arquivo .ttf/.otf encontrado no ZIP.")

        ts = datetime.now().isoformat(timespec="seconds")
        self.cache_repo.set_preview_tokens(slug, tokens, ts)
        return TokensResult(tokens=tokens, source="zip")
