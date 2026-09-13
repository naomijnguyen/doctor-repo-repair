# API

Base URL: `http://127.0.0.1:8000`

This page documents the current implementation.

## GET /api/notes
Returns `{ "notes": [...] }`. Each note has `id`, `title`, `body`, `tags`, and `createdAt`.

## POST /api/notes
Body:
```json
{"title":"...","body":"...","tags":["a","b"]}
```

## DELETE /api/notes/:id
Returns `204` when deletion succeeds, `404` when the note does not exist, and `400` for an invalid ID.

## GET /api/search?q=term
Returns matching notes.

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

Errors use:

```json
{"error":{"code":"invalid_request","message":"..."}}
```

Unsupported methods on known routes return `405`. Unknown routes return `404`.
