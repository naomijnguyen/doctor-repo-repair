from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _sync_directory(directory: Path) -> None:
    """Persist the directory entry where the platform supports directory fsync."""
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def write_export(
    destination: str | Path,
    payload: dict[str, Any],
    *,
    replace: bool = False,
) -> None:
    """Atomically publish one complete UTF-8 JSON export."""
    target = Path(destination)
    directory = target.parent
    if not directory.is_dir():
        raise FileNotFoundError(f"export directory does not exist: {directory}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=directory
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        if replace:
            os.replace(temporary, target)
        else:
            os.link(temporary, target)
            temporary.unlink()
        _sync_directory(directory)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
