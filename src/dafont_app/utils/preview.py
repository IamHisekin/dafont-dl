from urllib.parse import quote_plus

def preview_image_url(text: str, ttf: str, size: int = 63, y: int | None = None) -> str:
    text_enc = quote_plus(text or " ")
    if y is None:
        y = max(size - 2, 1)
    return (
        "https://img.dafont.com/preview.php"
        f"?text={text_enc}&ttf={ttf}&ext=1&size={size}&psize=m&y={y}"
    )
