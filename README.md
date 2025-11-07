<!--
README for QueueCTL

This file is written to be GitHub-friendly (markdown), easy to read, and contains
examples targeted at Windows PowerShell (the environment used for development in
this repository). Adjust shell commands for other platforms as needed.
-->

# QueueCTL — simple, persistent CLI job queue

QueueCTL is a minimal, production-minded command-line job queue. It lets you
enqueue shell commands as jobs, run one-or-more worker processes to execute
them, retry failures, and (later) move permanently failed jobs to a Dead
Letter Queue (DLQ).

This repository contains a Day-1 foundation: persistent storage (SQLite), a
clean CLI (Typer), a worker loop that executes commands, basic locking to
prevent duplicate processing, configuration persistence, and helper scripts to
exercise the system.

Key goals for Day 1
- Enqueue jobs from the CLI
- Persist jobs to disk (SQLite) so they survive restarts
- Single/multiple workers can pick up jobs without duplicates
- Jobs execute as shell commands and record completion/failure

## Features implemented (current)
- CLI commands: `enqueue`, `list`, `status`, `config set`, `worker start`
- SQLite-backed persistent storage (`jobs.db`) with a `jobs` table
- Worker process: picks a pending job, marks it `processing`, runs the command,
	updates the state (`completed`, `failed`, `dead`) and attempts
- Locking via atomic UPDATE .. RETURNING to prevent duplicate processing
- Basic helper scripts in `scripts/` to bulk enqueue and start workers
- Editable install via `pip install -e .` for easier local development

## Quick start (Windows PowerShell)

1. Create and activate virtual environment (already done in this repo for you):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

2. Install editable package (from project root):

```powershell
pip install -e .
```

3. Enqueue a job (PowerShell escaping):

```powershell
python -m queuectl enqueue '{"command": "echo Hello World"}'
```

4. Check queue status:

```powershell
python -m queuectl status
```

5. Start a worker to process jobs (run this in a separate terminal to keep it running):

```powershell
python -m queuectl worker start
```

Notes on Windows commands
- Use `ping -n N 127.0.0.1 > nul` as a portable sleep when testing long jobs on
	Windows (e.g. `ping -n 5 127.0.0.1 > nul` to sleep ~4 seconds).

## Project layout

```
queuectl/
	queuectl/             # python package
		__init__.py
		__main__.py         # enables `python -m queuectl`
		cli.py              # Typer CLI
		storage.py          # SQLite wrapper and queries
		models.py           # Job dataclass
		worker.py           # worker loop
		config.py           # config persistence
		utils.py            # helpers
	scripts/
		enqueue_test_jobs.py
		start_workers.py
	tests/
		test_basic_flow.py
	jobs.db                # (created at runtime)
	setup.py
	README.md
```

## Job schema (example)

Each job created by the system follows this schema:

```json
{
	"id": "uuid-or-custom-id",
	"command": "echo Hello",
	"state": "pending|processing|completed|failed|dead",
	"attempts": 0,
	"max_retries": 3,
	"created_at": "2025-11-07T07:11:05.526560",
	"updated_at": "2025-11-07T07:11:05.526560"
}
```

## How the worker picks jobs (locking)

- Workers call `get_pending_job_and_lock(worker_id)` which executes an atomic
	SQL `UPDATE ... WHERE id IN (SELECT id FROM jobs WHERE state='pending' ... LIMIT 1) RETURNING *`.
- This updates the chosen row to `processing` and sets `locked_by/locked_at` in
	a single statement so two workers cannot pick the same job.
- If your SQLite is older and doesn't support `RETURNING`, the project will
	need a small fallback (SELECT id then UPDATE within a transaction).

## Storage details (SQLite)

- File: `jobs.db` (created in the project root when first used)
- Table: `jobs` with columns (id, command, state, attempts, max_retries, created_at, updated_at, locked_by, locked_at)
- Important SQL patterns used:
	- Insert job: `INSERT INTO jobs (...) VALUES (?, ?, ... )`
	- Atomic lock & fetch: `UPDATE ... RETURNING *` (SQLite >= 3.35)
	- Update status: `UPDATE jobs SET state=?, attempts=?, updated_at=? WHERE id=?`

Recommendations for production-like runs
- Use `PRAGMA journal_mode = WAL;` to improve concurrent read/write behavior.
- Set `PRAGMA busy_timeout = 5000;` so writers wait if the DB is locked briefly.
- Store timestamps as ISO8601 strings (`.isoformat()`) for portability.

## CLI reference

- Enqueue a job (JSON string):

	```powershell
	python -m queuectl enqueue '{"command": "echo Hello World"}'
	```

- List jobs (optional state filter):

	```powershell
	python -m queuectl list --state pending
	python -m queuectl list --state completed
	```

- Show stats (counts per state):

	```powershell
	python -m queuectl status
	```

- Start a worker (run this in a separate terminal for long-running workers):

	```powershell
	python -m queuectl worker start
	```

## Inspecting jobs & active workers (programmatic)

The storage layer exposes convenience helpers to inspect jobs and active worker locks directly from Python. These are useful for debugging or building simple admin tooling (a CLI command for worker listing may be added later).

Examples (PowerShell):

```powershell
python -c "from queuectl.storage import Storage; import json; print(json.dumps([j.__dict__ for j in Storage().list_pending()], default=str, indent=2))"

python -c "from queuectl.storage import Storage; import json; print(json.dumps(Storage().list_workers(), default=str, indent=2))"
```

Convenience storage methods available:

- `list_pending()` — pending jobs
- `list_processing()` — currently processing jobs
- `list_completed()` — completed jobs
- `list_failed()` — failed jobs
- `list_dead()` — failed jobs that exhausted retries (dead-letter candidates)
- `get_job(job_id)` — fetch a single job by id
- `list_workers()` — returns a list of active worker summaries and the jobs they hold locks for

Timestamps are stored as ISO8601 strings and parsed back into Python `datetime` objects by these helpers.

- Set configuration (persisted to `config.json`):

	```powershell
	python -m queuectl config set max-retries 5
	```

## Running multiple workers

- Option A (multiple terminals): open N PowerShell windows and run the
	`python -m queuectl worker start` command in each — each worker will try to
	pick pending jobs.
- Option B (helper script): use `python scripts/start_workers.py N` to spawn N
	worker threads in a single process (useful for local testing, but separate
	processes are closer to production behavior).

## Testing

- Unit / integration test skeleton is in `queuectl/tests/test_basic_flow.py`.
- Run tests with:

```powershell
pytest -q
```

Note: tests use a temporary SQLite DB file and may need adjustments if a
leftover `test_jobs.db` file is present. Remove it before running tests if you
see permission issues.

## Troubleshooting & common gotchas

- `No module named queuectl.__main__` — solved by adding `queuectl/__main__.py`.
- `RETURNING` not supported — your Python's SQLite may be old; upgrade SQLite
	or the Python build, or I can add a fallback implementation that uses an
	explicit transaction.
- `database is locked` — use WAL journal mode and busy_timeout PRAGMA, or
	reduce contention by spreading workers/processes.

## Design decisions & assumptions

- Using SQLite for Day 1 keeps things simple and portable. For high
	throughput, a dedicated queue/db is recommended (Postgres, Redis streams).
- Jobs are shell commands executed with `subprocess.run(shell=True)`.
	This is flexible but requires trusting the commands. For untrusted input,
	validate/sandbox commands first.
- Locking is handled via atomic UPDATE; stale locks are reclaimed using a
	`locked_at < now - 5 minutes` condition in the selection subquery.

## Next steps (planned)

1. Exponential backoff retry scheduling (delay = base ** attempts)
2. Dead Letter Queue (DLQ) management and CLI (`dlq list`, `dlq retry`)
3. Persist job output and add per-job logs
4. Job timeouts and cancellation
5. More tests around concurrency and graceful shutdown

---

If you want, I can update this README with screenshots or a short recorded
demo link once you record the CLI demo. Want me to also add a troubleshooting
section with the exact PRAGMA changes and a fallback implementation for
`RETURNING`? 
