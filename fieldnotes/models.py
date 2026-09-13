from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class Note:
    id: int
    title: str
    body: str
    tags: list[str]
    created_at: str

    @classmethod
    def create(cls, note_id: int, title: str, body: str, tags: list[str]):
        return cls(
            id=note_id,
            title=title,
            body=body,
            tags=tags,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict:
        return asdict(self)
