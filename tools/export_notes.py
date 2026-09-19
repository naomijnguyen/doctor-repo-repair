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
from fieldnotes.exporter import write_export


class ApiExportClient:
    """Read one portable export document from the running application."""

    def __init__(self, api_url: str) -> None:
        self.api_url = api_url.rstrip("/")

    def export_payload(self) -> dict:
        request = Request(f"{self.api_url}/api/export", method="GET")
        try:
            with urlopen(request) as response:
                result = json.loads(response.read())
        except HTTPError as exc:
            try:
                error_payload = json.loads(exc.read())
                detail = error_payload.get("error", {}).get("message")
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                detail = None
            finally:
                exc.close()
            raise RuntimeError(
                f"API rejected the export: {detail or exc.reason or 'request failed'}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Could not connect to the Field Notes API at {self.api_url}"
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("Field Notes API returned invalid export JSON") from exc

        if not isinstance(result, dict) or not isinstance(result.get("notes"), list):
            raise RuntimeError("Field Notes API returned an invalid export response")
        return result


def export_notes(
    client: ApiExportClient,
    destination: str | Path,
    *,
    replace: bool = False,
) -> int:
    payload = client.export_payload()
    write_export(destination, payload, replace=replace)
    return len(payload["notes"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export Field Notes to portable JSON")
    parser.add_argument("destination", help="JSON file to publish")
    parser.add_argument(
        "--api-url",
        default=f"http://127.0.0.1:{get_port()}",
        help="running Field Notes application URL",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="intentionally replace an existing export",
    )
    args = parser.parse_args(argv)

    try:
        count = export_notes(
            ApiExportClient(args.api_url),
            args.destination,
            replace=args.replace,
        )
    except FileExistsError:
        print(
            f"Export destination already exists: {args.destination} "
            "(use --replace to replace it)",
            file=sys.stderr,
        )
        return 1
    except (OSError, RuntimeError) as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1

    print(f"Exported {count} notes to {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
