import sqlite3
from datetime import datetime
from typing import Optional, List
from .models import Job

class Storage:
    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_retries INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    locked_by TEXT,
                    locked_at TIMESTAMP
                )
            """)
            conn.commit()

    def add_job(self, job: Job) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO jobs (
                    id, command, state, attempts, max_retries,
                    created_at, updated_at, locked_by, locked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id, job.command, job.state, job.attempts,
                job.max_retries, job.created_at, job.updated_at,
                job.locked_by, job.locked_at
            ))
            conn.commit()

    def get_pending_job_and_lock(self, worker_id: str) -> Optional[Job]:
        with sqlite3.connect(self.db_path) as conn:
            # Start transaction
            try:
                # Get the first pending job and lock it atomically
                cursor = conn.execute("""
                    UPDATE jobs 
                    SET state = 'processing',
                        locked_by = ?,
                        locked_at = ?,
                        updated_at = ?
                    WHERE id IN (
                        SELECT id FROM jobs 
                        WHERE state = 'pending'
                        AND (locked_by IS NULL OR locked_at < datetime('now', '-5 minutes'))
                        LIMIT 1
                    )
                    RETURNING *
                """, (worker_id, datetime.utcnow(), datetime.utcnow()))
                
                row = cursor.fetchone()
                if row is None:
                    return None

                # Convert row to Job object
                return Job(
                    id=row[0],
                    command=row[1],
                    state=row[2],
                    attempts=row[3],
                    max_retries=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    locked_by=row[7],
                    locked_at=datetime.fromisoformat(row[8]) if row[8] else None
                )
            except sqlite3.Error:
                conn.rollback()
                return None

    def update_job(self, job: Job) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE jobs 
                SET state = ?,
                    attempts = ?,
                    updated_at = ?,
                    locked_by = ?,
                    locked_at = ?
                WHERE id = ?
            """, (
                job.state, job.attempts, datetime.utcnow(),
                job.locked_by, job.locked_at, job.id
            ))
            conn.commit()

    def list_jobs(self, state: Optional[str] = None) -> List[Job]:
        with sqlite3.connect(self.db_path) as conn:
            if state:
                cursor = conn.execute("SELECT * FROM jobs WHERE state = ?", (state,))
            else:
                cursor = conn.execute("SELECT * FROM jobs")

            jobs = []
            for row in cursor:
                jobs.append(Job(
                    id=row[0],
                    command=row[1],
                    state=row[2],
                    attempts=row[3],
                    max_retries=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    locked_by=row[7],
                    locked_at=datetime.fromisoformat(row[8]) if row[8] else None
                ))
            return jobs

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT state, COUNT(*) 
                FROM jobs 
                GROUP BY state
            """)
            return dict(cursor.fetchall())