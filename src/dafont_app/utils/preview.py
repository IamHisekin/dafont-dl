from __future__ import annotations
from urllib.parse import quote_plus

def preview_image_url(text: str, ttf_token: str, size: int = 63, y: int | None = None) -> str:
    # Uses DaFont image service (no HTML fetching). Needs ttf token, derived from zip's font filename.
    text_enc = quote_plus(text or " ")
    if y is None:
        y = max(size - 2, 1)
    return (
        "https://img.dafont.com/preview.php"
        f"?text={text_enc}&ttf={ttf_token}&ext=1&size={size}&psize=m&y={y}"
    )
