def normalize_tag(tag: str) -> str:
    """Legacy import normalization."""
    return tag.strip().lower().replace(" ", "_")
