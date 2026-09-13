"""Old response adapter retained during the UI migration."""


def note_to_frontend(note: dict) -> dict:
    return {
        "id": note["id"],
        "title": note["title"],
        "body": note["body"],
        "tags": note["tags"],
        "createdAt": note.get("created_at"),
    }
