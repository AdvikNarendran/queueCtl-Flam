from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Job:
    id: str
    command: str
    state: str
    attempts: int
    max_retries: int
    created_at: datetime
    updated_at: datetime
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None

    @staticmethod
    def create(id: str, command: str, max_retries: int = 3) -> "Job":
        now = datetime.utcnow()
        return Job(
            id=id,
            command=command,
            state="pending",
            attempts=0,
            max_retries=max_retries,
            created_at=now,
            updated_at=now
        )