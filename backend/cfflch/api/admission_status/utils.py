import unicodedata


def normalize_text(text: str) -> str:
    stripped = text.strip()
    normalized = unicodedata.normalize("NFKD", stripped)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()
