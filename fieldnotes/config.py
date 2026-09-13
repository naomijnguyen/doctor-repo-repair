import os

DEFAULT_PORT = 8000
DEFAULT_DATA_FILE = "./data/fieldnotes.json"


def get_port() -> int:
    # Historical env var retained for compatibility.
    return int(os.getenv("FIELDNOTES_PORT", DEFAULT_PORT))


def get_data_file() -> str:
    return os.getenv("FIELD_NOTES_DATA", DEFAULT_DATA_FILE)
