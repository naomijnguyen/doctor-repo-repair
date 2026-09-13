import re


def normalize_tag(tag: str) -> str:
    """Normalize a tag for API-created notes."""
    tag = tag.strip().lower()
    tag = re.sub(r"\\s+", "-", tag)
    return re.sub(r"[^a-z0-9_-]", "", tag)


def normalize_query(value: str) -> str:
    return " ".join(value.lower().split())
