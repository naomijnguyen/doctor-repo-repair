# API

Default base URL: `http://127.0.0.1:8000`

This page documents the current implementation.

## Note representation

```json
{
  "id": 1,
  "title": "Plate review",
  "body": "Check the edge wells.",
  "tags": ["assay-review"],
  "createdAt": "2026-09-12T20:30:00+00:00"
}
```

IDs are assigned locally. Public timestamps use `createdAt` and are serialized
as timezone-aware UTC ISO 8601 strings.

## GET /api/notes

Returns the stored notes in ID order:

```json
{"notes": []}
```

## POST /api/notes

Body:

```json
{"title":"...","body":"...","tags":["a","b"]}
```

`title` is required. `body` and `tags` may be omitted. The service trims text,
normalizes tags, assigns a UTC timestamp, commits the note, and returns the
complete stored representation with `201 Created`.

Unknown object fields are currently ignored for both create and individual
import records. This is an explicit compatibility policy for the local beta, not
evidence that those fields are stored. Equivalent normalized tags are
deduplicated in first-seen order.

## DELETE /api/notes/:id

Returns `204` when deletion commits, `404` when the note does not exist, and
`400` for an invalid ID.

## GET /api/search?q=term

Returns notes whose normalized title, body, or tags contain the normalized query.
A blank query returns the complete note list.

## POST /api/import

Body:

```json
{
  "notes": [
    {
      "title": "Observation",
      "body": "Optional details",
      "tags": ["field-work"],
      "createdAt": "2026-09-12T20:30:00Z"
    }
  ]
}
```

The complete payload is validated before storage begins. A non-empty committed
batch returns `201`; an accepted empty batch returns `200`. Source IDs are
ignored. Valid timezone-aware `createdAt` values preserve their instant in
canonical UTC; missing timestamps are assigned by the application.

The operation is atomic for one request. A storage failure rolls back the
complete batch. It is not currently idempotent after an ambiguous lost response.

## GET /api/export

Returns a portable UTF-8 JSON document with a top-level `notes` array and the
same public note fields shown above. Export reads through the running
application; the command does not open SQLite as a second state owner.

Source IDs are included for readability but are not recovery identities. Import
assigns IDs locally in the destination database while preserving note order,
titles, bodies, tags, and valid timestamps.

## Local request boundary

The application is loopback-only and serves UI and API from one origin.
Browser mutation requests that include `Origin` must match the actual server
origin. Foreign origins and `Origin: null` receive `403 origin_not_allowed`
before mutation. CLI requests without an `Origin` header remain supported.

`POST /api/notes` and `POST /api/import` require an `application/json` media
type; parameters such as `charset=utf-8` are accepted. Missing or different
media types receive `415 unsupported_media_type` before mutation.

## Errors

Errors use:

```json
{"error":{"code":"invalid_request","message":"..."}}
```

Expected validation and routing failures use stable codes and human-readable
messages. Unexpected application failures are converted by the HTTP server to a
generic `500 internal_error` response.

Unsupported methods on known routes return structured `405` responses through
the API adapter, including `PUT` and `PATCH`. Unknown routes return `404`.
Bodies above 1,000,000 bytes return structured `413 request_too_large` before
the handler reads or mutates application state.
