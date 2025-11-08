import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List
from .models import Job

def _iso(dt: datetime) -> str:
    return dt.utcnow().isoformat() if dt is None else dt.isoformat()

def _parse(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str)

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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    locked_by TEXT,
                    locked_at TEXT,
                    next_retry_at TEXT,
                    timeout INTEGER,
                    run_at TEXT,
                    output TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_next_retry ON jobs(next_retry_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_run_at ON jobs(run_at)
            """)
            conn.commit()

    def add_job(self, job: Job) -> None:
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO jobs (
                        id, command, state, attempts, max_retries,
                        created_at, updated_at, locked_by, locked_at,
                        next_retry_at, timeout, run_at, output
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.id,
                    job.command,
                    job.state,
                    job.attempts,
                    job.max_retries,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.locked_by,
                    job.locked_at.isoformat() if job.locked_at else None,
                    job.next_retry_at.isoformat() if job.next_retry_at else None,
                    job.timeout,
                    job.run_at.isoformat() if job.run_at else None,
                    job.output
                ))
                conn.commit()
            except sqlite3.IntegrityError as e:
                # re-raise for caller to decide
                raise

    def get_pending_job_and_lock(self, worker_id: str) -> Optional[Job]:
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.isolation_level = None  # autocommit off for manual transaction
                conn.execute("BEGIN IMMEDIATE")
                # fetch a candidate job
                cursor = conn.execute("""
                    SELECT id FROM jobs
                    WHERE (state = 'pending' OR state = 'failed')
                      AND (locked_by IS NULL OR locked_at < strftime('%Y-%m-%dT%H:%M:%S', datetime('now','-5 minutes')))
                      AND (next_retry_at IS NULL OR next_retry_at <= datetime('now'))
                      AND (run_at IS NULL OR run_at <= datetime('now'))
                    ORDER BY 
                        CASE state
                            WHEN 'failed' THEN 1
                            WHEN 'pending' THEN 0
                        END,
                        created_at
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row is None:
                    conn.execute("COMMIT")
                    return None

                job_id = row[0]
                now_iso = datetime.utcnow().isoformat()
                conn.execute("""
                    UPDATE jobs SET
                        state = 'processing',
                        locked_by = ?,
                        locked_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (worker_id, now_iso, now_iso, job_id))

                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                conn.execute("COMMIT")

                return Job(
                    id=row[0],
                    command=row[1],
                    state=row[2],
                    attempts=row[3],
                    max_retries=row[4],
                    created_at=_parse(row[5]),
                    updated_at=_parse(row[6]),
                    locked_by=row[7],
                    locked_at=_parse(row[8]) if row[8] else None,
                    next_retry_at=_parse(row[9]) if row[9] else None,
                    timeout=row[10],
                    run_at=_parse(row[11]) if row[11] else None,
                    output=row[12]
                )
            except sqlite3.Error:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                return None

    def update_job(self, job: Job) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE jobs 
                SET state = ?,
                    attempts = ?,
                    updated_at = ?,
                    locked_by = ?,
                    locked_at = ?,
                    next_retry_at = ?,
                    output = ?
                WHERE id = ?
            """, (
                job.state,
                job.attempts,
                datetime.utcnow().isoformat(),
                job.locked_by,
                job.locked_at.isoformat() if job.locked_at else None,
                job.next_retry_at.isoformat() if job.next_retry_at else None,
                job.output,
                job.id
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
                    created_at=_parse(row[5]),
                    updated_at=_parse(row[6]),
                    locked_by=row[7],
                    locked_at=_parse(row[8]) if row[8] else None
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
