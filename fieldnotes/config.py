import os

DEFAULT_PORT = 8000
DEFAULT_DATA_FILE = "./data/fieldnotes.sqlite3"


def get_port() -> int:
    return int(os.getenv("FIELDNOTES_PORT", DEFAULT_PORT))


def get_data_file() -> str:
    return os.getenv(
        "FIELDNOTES_DATA",
        os.getenv("FIELD_NOTES_DATA", DEFAULT_DATA_FILE),
    )
