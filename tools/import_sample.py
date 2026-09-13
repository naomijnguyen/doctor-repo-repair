from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fieldnotes.config import get_port


class ApiImportClient:
    """Send one complete import payload to the running Field Notes API."""

    def __init__(self, api_url: str) -> None:
        self.api_url = api_url.rstrip("/")

    def import_payload(self, payload) -> dict:
        request = Request(
            f"{self.api_url}/api/import",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request) as response:
                result = json.loads(response.read())
        except HTTPError as exc:
            try:
                error_payload = json.loads(exc.read())
                detail = error_payload.get("error", {}).get("message")
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                detail = None
            message = detail or exc.reason or "request failed"
            raise RuntimeError(f"API rejected the import: {message}") from exc
        except URLError as exc:
            raise RuntimeError(
                f"Could not connect to the Field Notes API at {self.api_url}"
            ) from exc

        if (
            not isinstance(result, dict)
            or not isinstance(result.get("imported"), int)
            or not isinstance(result.get("notes"), list)
        ):
            raise RuntimeError("Field Notes API returned an invalid import response")
        return result


def read_import_payload(path: str | Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Could not read import file {path}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a Field Notes JSON file through the running API."
    )
    parser.add_argument("path", nargs="?", default="data/sample.json")
    parser.add_argument(
        "--api-url",
        default=f"http://127.0.0.1:{get_port()}",
        help="Field Notes API origin (default: local configured port)",
    )
    args = parser.parse_args()

    client = ApiImportClient(args.api_url)
    result = client.import_payload(read_import_payload(args.path))
    print(f"Imported {result['imported']} notes")
    for note in result["notes"]:
        print(note)


if __name__ == "__main__":
    main()
