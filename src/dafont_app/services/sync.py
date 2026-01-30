from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

from dafont_app.db.cache_repo import CacheRepo

DEFAULT_REMOTE_DB_URL = "https://raw.githubusercontent.com/IamHisekin/dafont-dl/main/src/db-sync/fontes.db"


@dataclass(frozen=True)
class SyncResult:
    updated: bool
    reason: str
    bytes_downloaded: int = 0
    sha256: str | None = None
    # Compat fields expected by UI
    remote_etag: str | None = None
    remote_size: int | None = None

    # Backward-compat alias (some code may use .etag)
    @property
    def etag(self) -> str | None:  # pragma: no cover
        return self.remote_etag


class DbSyncService:
    def __init__(self, cache_repo: CacheRepo, remote_url: str = DEFAULT_REMOTE_DB_URL, timeout: float = 30.0):
        self.cache_repo = cache_repo
        self.remote_url = remote_url
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "dafont_app/1.0", "Accept": "*/*"})

    def _sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _progress(self, cb: Optional[Callable[[str], None]], msg: str) -> None:
        if cb:
            cb(msg)

    def sync_if_needed(self, local_db_path: Path, progress: Optional[Callable[[str], None]] = None) -> SyncResult:
        meta = self.cache_repo.get_sync_meta()

        self._progress(progress, "Verificando DB remoto (GitHub)…")

        etag = None
        size = None

        try:
            r = self._session.head(self.remote_url, timeout=self.timeout, allow_redirects=True)
            if r.ok:
                etag = r.headers.get("ETag")
                cl = r.headers.get("Content-Length")
                size = int(cl) if cl and cl.isdigit() else None
        except Exception:
            pass

        if not local_db_path.exists():
            self._progress(progress, "DB local não encontrado. Baixando…")
            return self._download_and_replace(local_db_path, progress, etag=etag, size=size)

        if etag and meta and meta.etag == etag:
            return SyncResult(updated=False, reason="ETag igual (sem mudanças).", remote_etag=etag, remote_size=size)

        if (not etag) and meta and size and meta.size and meta.size != size:
            self._progress(progress, "Tamanho remoto mudou. Baixando…")
            return self._download_and_replace(local_db_path, progress, etag=etag, size=size)

        if (not etag) and (not meta):
            self._progress(progress, "Sem meta local. Baixando para sincronizar…")
            return self._download_and_replace(local_db_path, progress, etag=etag, size=size)

        self._progress(progress, "Baixando para verificar alterações…")
        return self._download_and_replace(local_db_path, progress, etag=etag, size=size)

    def _download_and_replace(self, local_db_path: Path, progress: Optional[Callable[[str], None]], etag: str | None, size: int | None) -> SyncResult:
        tmp = local_db_path.with_suffix(".db.tmp")
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass

        headers = {}
        meta = self.cache_repo.get_sync_meta()
        if meta and meta.etag:
            headers["If-None-Match"] = meta.etag

        r = self._session.get(self.remote_url, timeout=self.timeout, stream=True, headers=headers, allow_redirects=True)

        if r.status_code == 304:
            return SyncResult(updated=False, reason="Servidor retornou 304 (sem mudanças).", remote_etag=meta.etag if meta else None, remote_size=meta.size if meta else None)

        r.raise_for_status()

        total = 0
        self._progress(progress, "Baixando fontes.db…")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                total += len(chunk)

        sha = self._sha256_file(tmp)

        os.replace(str(tmp), str(local_db_path))

        new_etag = r.headers.get("ETag") or etag
        cl = r.headers.get("Content-Length")
        new_size = int(cl) if cl and cl.isdigit() else (size or total)

        updated_at = datetime.now(timezone.utc).isoformat()
        self.cache_repo.set_sync_meta(etag=new_etag, sha256=sha, size=new_size, updated_at=updated_at)

        self._progress(progress, f"DB atualizado. bytes={total} sha256={sha[:12]}…")
        return SyncResult(updated=True, reason="Atualizado.", bytes_downloaded=total, sha256=sha, remote_etag=new_etag, remote_size=new_size)


# Backward compat aliases
DBSyncService = DbSyncService
SyncService = DbSyncService
