from __future__ import annotations

import random
import re
import time
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class DaFontError(RuntimeError):
    pass


class DaFontClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
            }
        )

        retry = Retry(
            total=6,
            connect=6,
            read=6,
            status=6,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        self._min_delay = 0.45
        self._max_delay = 1.05
        self._last_request_ts = 0.0

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    def _throttle(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_ts
        target = random.uniform(self._min_delay, self._max_delay)
        if elapsed < target:
            time.sleep(target - elapsed)
        self._last_request_ts = time.time()

    def fetch_html(self, url: str) -> str:
        self._throttle()
        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                r = self._session.get(url, timeout=self._timeout)
                if r.status_code == 429:
                    ra = r.headers.get("Retry-After")
                    if ra and ra.isdigit():
                        time.sleep(int(ra))
                    else:
                        time.sleep(2.0 + attempt)
                    continue
                r.raise_for_status()
                return r.text
            except requests.exceptions.RequestException as e:
                last_err = e
                time.sleep(0.9 * attempt + random.uniform(0.0, 0.6))
        raise DaFontError(f"Falha ao conectar ao DaFont. URL={url}\nErro: {last_err}")

    @staticmethod
    def _slug_from_font_page(url: str) -> str | None:
        p = urlparse(url)
        last = (p.path or "").rstrip("/").split("/")[-1]
        if last.endswith(".font"):
            slug = re.sub(r"[^a-z0-9_-]+", "", last[:-5].lower())
            return slug or None
        return None

    def fetch_charmap_tokens(self, slug: str) -> list[str]:
        tokens: list[str] = []
        url = f"https://www.dafont.com/pt/{slug}.charmap?f=0"
        try:
            html = self.fetch_html(url)
        except Exception:
            return tokens

        if "Conjunto de caracteres indisponível" in html:
            return tokens

        for m in re.finditer(r"fontFileName\s*=\s*'([^']+\.ttf)'", html):
            fname = m.group(1).split("/")[-1]
            tok = re.sub(r"[^a-z0-9_-]+", "", fname[:-4].lower())
            if tok and tok not in tokens:
                tokens.append(tok)
        return tokens

    def fetch_font_details(self, page_url: str) -> dict:
        html = self.fetch_html(page_url)
        soup = BeautifulSoup(html, "html.parser")

        name = None
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True) or None

        tokens: list[str] = []

        # preview.php?ttf=
        for div in soup.find_all("div", class_="preview"):
            style = div.get("style", "") or ""
            m = re.search(r"(?:\?|&|&amp;)ttf=([^&\"';]+)", style)
            if m:
                t = m.group(1).strip()
                if t and t not in tokens:
                    tokens.append(t)

        # /img/preview/.../academy0.png
        for div in soup.find_all("div", class_="preview"):
            style = div.get("style", "") or ""
            m = re.search(r"/img/preview/.+?/([a-z0-9_-]+)\.png", style, flags=re.I)
            if m:
                t = m.group(1).strip()
                if t and t not in tokens:
                    tokens.append(t)

        # charmap fallback
        if not tokens:
            slug = self._slug_from_font_page(page_url)
            if slug:
                tokens.extend(self.fetch_charmap_tokens(slug))

        return {"name": name, "preview_tokens": tokens}

    def get_last_page_for_category(self, category) -> int:
        html = self.fetch_html(category.url)
        soup = BeautifulSoup(html, "html.parser")

        last = 1
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "page=" in href:
                m = re.search(r"page=(\d+)", href)
                if m:
                    last = max(last, int(m.group(1)))
        return last

    def normalize_any_link(self, link: str) -> dict:
        link = link.strip()
        p = urlparse(link)
        qs = parse_qs(p.query)
        if "f" in qs and qs["f"]:
            slug = re.sub(r"[^a-z0-9_-]+", "", qs["f"][0].lower())
            return {
                "slug": slug,
                "name": slug.replace("-", " ").title(),
                "download_url": f"https://dl.dafont.com/dl/?f={slug}",
                "page_url": f"https://www.dafont.com/pt/{slug}.font",
            }

        slug = self._slug_from_font_page(link)
        if slug:
            return {
                "slug": slug,
                "name": slug.replace("-", " ").title(),
                "download_url": f"https://dl.dafont.com/dl/?f={slug}",
                "page_url": f"https://www.dafont.com/pt/{slug}.font",
            }

        raise DaFontError("Link não reconhecido. Cole um link .font ou dl/?f=...")
