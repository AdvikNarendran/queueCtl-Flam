import json
import time
import sqlite3
from pathlib import Path
from typing import Optional, Any, List
from datetime import datetime, timedelta

import typer
import sys
from rich.console import Console
from rich.table import Table

from .storage import Storage
from .models import Job
from .worker import WorkerPool
from .config import Config
from .utils import generate_id, format_timestamp

app = typer.Typer(help="A production-grade job queue system with DLQ support.")

storage = Storage()
config = Config()
worker_pool = WorkerPool(storage, config)
console = Console(file=sys.stderr)  # Use stderr for rich output

# Enable debug mode for more verbose output
DEBUG = True

def debug_print(msg):
    """Print debug messages if debug mode is enabled"""
    if DEBUG:
        print(f"DEBUG: {msg}", file=sys.stderr)


# ----------------------------
# Helpers
# ----------------------------
def _coerce_value(value: str) -> Any:
    """Coerce a CLI string to int/bool/str for config-set."""
    if value.isdigit():
        return int(value)
    lower = value.lower()
    if lower in ("true", "false"):
        return lower == "true"
    return value


def _enqueue_from_dict(data: dict) -> str:
    """Create and store a job from a dict payload. Returns job_id."""
    debug_print(f"Enqueueing job with data: {data}")
    
    job_id = data.get("id", generate_id())
    command = data["command"]  # KeyError if missing -> handled by caller
    max_retries = int(data.get("max_retries", config.get("max_retries")))

    debug_print(f"Created job ID: {job_id}, command: {command}, max_retries: {max_retries}")
    
    job = Job.create(job_id, command, max_retries)
    storage.add_job(job)
    
    debug_print("Job added to storage successfully")
    return job_id


def _load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------
# Commands
# ----------------------------
@app.command(help="Add a new job using a raw JSON string (PowerShell: use single quotes).")
def enqueue(job_data: str = typer.Argument(..., help='JSON string, e.g. \'{"command": "echo hi"}\'')):
    """
    Example (PowerShell):
      python main.py enqueue '{"command": "echo hi"}'

    Example (CMD):
      python main.py enqueue "{\"command\": \"echo hi\"}"
    """
    print("Processing enqueue request...")
    try:
        data = json.loads(job_data)
        job_id = _enqueue_from_dict(data)
        print("\n=== Job Enqueued Successfully ===")
        print(f"Job ID: {job_id}")
        
        # Show job details
        job = next((j for j in storage.list_jobs() if j.id == job_id), None)
        if job:
            print(f"Command: {job.command}")
            print(f"State: {job.state}")
            print(f"Max Retries: {job.max_retries}")
            print(f"Created At: {format_timestamp(job.created_at)}")
            print("\nTip: Use 'queuectl status' to check queue status")
            print("Tip: Use 'queuectl worker start' to process the job\n")
        
    except json.JSONDecodeError as e:
        typer.echo("\n❌ Error: Invalid JSON format.", err=True)
        typer.echo("Tip: In PowerShell, use single quotes: queuectl enqueue '{\"command\": \"echo hello\"}'", err=True)
        raise typer.Exit(1)
    except KeyError:
        typer.echo('\n❌ Error: JSON must include a "command" field.', err=True)
        typer.echo('Example: {"command": "echo hello"}', err=True)
        raise typer.Exit(1)
    except sqlite3.IntegrityError:
        typer.echo("\n❌ Error: Job ID already exists. Use a unique ID.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"\n❌ Error enqueuing job: {e}", err=True)
        raise typer.Exit(1)


@app.command("enqueue-file", help="Add a new job from a JSON file.")
def enqueue_file(path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True)):
    """
    The JSON file should look like:
      {
        "command": "echo hello",
        "max_retries": 3
      }

    PowerShell:
      python -m queuectl.cli enqueue-file .\\job.json
    """
    try:
        data = _load_json_file(path)
        job_id = _enqueue_from_dict(data)
        typer.echo(f"Job {job_id} enqueued from {path}")
    except KeyError:
        typer.echo(f'Error: {path} must include a "command" field.', err=True)
        raise typer.Exit(1)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: invalid JSON in {path}: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error enqueuing from {path}: {e}", err=True)
        raise typer.Exit(1)


@app.command("enqueue-dir", help="Batch enqueue: all *.json files in a directory.")
def enqueue_dir(
    dir_path: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    pattern: str = typer.Option("*.json", help="Glob pattern for job files."),
    stop_on_error: bool = typer.Option(False, help="Stop immediately if any file fails."),
):
    """
    Enqueues each JSON file (matching pattern) as one job.
    """
    files: List[Path] = sorted(dir_path.glob(pattern))
    if not files:
        typer.echo(f"No files matching {pattern} found in {dir_path}")
        raise typer.Exit(0)

    successes, failures = 0, 0
    for fp in files:
        try:
            data = _load_json_file(fp)
            job_id = _enqueue_from_dict(data)
            successes += 1
            typer.echo(f"[OK] {fp.name} -> job {job_id}")
        except Exception as e:
            failures += 1
            typer.echo(f"[FAIL] {fp.name}: {e}", err=True)
            if stop_on_error:
                break

    typer.echo(f"Done. Success: {successes}, Failures: {failures}")


@app.command("enqueue-args", help="Add a job with CLI flags instead of JSON.")
def enqueue_args(
    command: str = typer.Option(..., "--command", "-c", help="Command to execute."),
    max_retries: Optional[int] = typer.Option(None, "--max-retries", "-r", help="Override default max_retries."),
    job_id: Optional[str] = typer.Option(None, "--id", "-i", help="Optional custom job ID."),
):
    """
    Example:
      python -m queuectl.cli enqueue-args -c "echo hi" -r 5
    """
    try:
        data = {
            "command": command,
        }
        if job_id:
            data["id"] = job_id
        if max_retries is not None:
            data["max_retries"] = str(max_retries)
        new_id = _enqueue_from_dict(data)
        typer.echo(f"Job {new_id} enqueued successfully")
    except Exception as e:
        typer.echo(f"Error enqueuing job: {e}", err=True)
        raise typer.Exit(1)


@app.command("list-jobs", help="List jobs with optional state filter and rich formatting.")
def list_jobs(
    state: Optional[str] = typer.Option(None, help="Filter by state: pending/processing/completed/failed/dead"),
    show_output: bool = typer.Option(False, "--output", help="Show job output")
):
    """List jobs with detailed information."""
    try:
        jobs = storage.list_jobs(state)
        typer.echo(f"\nTotal jobs found: {len(jobs)}")
        
        if not jobs:
            typer.echo("No jobs in the queue.")
            return

        table = Table(
            "ID", 
            "Command", 
            "State", 
            "Attempts", 
            "Next Retry", 
            "Created",
            "Output",
            title="Queue Jobs",
            show_lines=True
        )
        
        for job in jobs:
            next_retry = (
                format_timestamp(job.next_retry_at)
                if job.next_retry_at and job.state == "failed"
                else "N/A"
            )
            output = (
                (job.output[:100] + "...") if job.output and len(job.output) > 100 else job.output
                if show_output and job.output
                else "N/A"
            )
            table.add_row(
                str(job.id),
                str(job.command),
                str(job.state),
                f"{job.attempts}/{job.max_retries}",
                str(next_retry),
                format_timestamp(job.created_at),
                str(output)
            )
        
        console.print("\n")
        console.print(table)
        console.print("\n")
        
    except Exception as e:
        typer.echo(f"Error listing jobs: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command(help="Show detailed queue status and worker information.")
def status():
    """Show comprehensive queue status including worker info."""
    try:
        stats = storage.get_stats()
        typer.echo("\n=== Queue System Status ===\n")

        # Queue status table
        queue_table = Table(
            title="Queue Status",
            show_header=True,
            header_style="bold magenta",
            show_lines=True
        )
        queue_table.add_column("State")
        queue_table.add_column("Count")

        states = ["pending", "processing", "completed", "failed", "dead"]
        total_jobs = 0
        for state in states:
            count = stats.get(state, 0)
            total_jobs += count
            queue_table.add_row(state, str(count))
        queue_table.add_row("Total", str(total_jobs), style="bold")

        # Worker status table
        worker_table = Table(
            title="Worker Status",
            show_header=True,
            header_style="bold blue",
            show_lines=True
        )
        worker_table.add_column("Active Workers")
        worker_table.add_column("Shell Mode")
        worker_count = worker_pool.get_active_count()
        worker_table.add_row(
            str(worker_count),
            "Mixed" if any(w.use_shell for w in worker_pool.workers.values()) else "False"
        )

        # Config table
        config_data = config.get_all()
        config_table = Table(
            title="Configuration",
            show_header=True,
            header_style="bold green",
            show_lines=True
        )
        config_table.add_column("Setting")
        config_table.add_column("Value")
        for key, value in sorted(config_data.items()):
            config_table.add_row(str(key), str(value))

        # Print all tables with spacing
        console.print("\n")
        console.print(queue_table)
        console.print("\n")
        console.print(worker_table)
        console.print("\n")
        console.print(config_table)
        console.print("\n")

        if worker_count == 0 and total_jobs > 0:
            typer.echo("\n[yellow]Warning: There are jobs in the queue but no active workers![/yellow]")

    except Exception as e:
        typer.echo(f"Error getting status: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("config-set", help="Set configuration key/value.")
def config_set(key: str, value: str):
    """
    Coerces 'true'/'false' to bool, digits to int; otherwise stores as string.
    """
    try:
        actual: Any = _coerce_value(value)
        config.set(key, actual)
        typer.echo(f"Configuration {key} set to {actual}")
    except Exception as e:
        typer.echo(f"Error setting configuration: {e}", err=True)
        raise typer.Exit(1)


@app.command(help="Manage worker processes.")
def worker(
    action: str = typer.Argument(..., help="Action: start/stop"),
    count: int = typer.Option(1, "--count", "-c", help="Number of workers to start"),
    shell: bool = typer.Option(False, help="Run commands via shell=True (less safe)"),
):
    """
    Start or stop worker processes.
    
    Examples:
      queuectl worker start --count 3
      queuectl worker stop
    """
    if action == "start":
        try:
            print(f"\nStarting {count} worker(s)...")
            worker_pool.start(count=count, use_shell=shell)
            print("Workers started successfully")
            print("\nPress Ctrl+C to stop workers gracefully")
            
            # Keep the main thread running
            while True:
                time.sleep(1)
                active_count = worker_pool.get_active_count()
                if active_count == 0:
                    print("All workers have stopped unexpectedly")
                    break
                
        except KeyboardInterrupt:
            print("\nReceived stop signal. Stopping workers gracefully...")
            worker_pool.stop()
            print("All workers stopped")
    
    elif action == "stop":
        worker_pool.stop()
        print("Workers stopped gracefully")
    
    else:
        print("Invalid action. Use 'start' or 'stop'", file=sys.stderr)
        raise typer.Exit(1)

@app.command(help="Dead Letter Queue operations")
def dlq(
    action: str = typer.Argument(..., help="Action: list/retry"),
    job_id: Optional[str] = typer.Argument(None, help="Job ID for retry action"),
):
    """
    Manage Dead Letter Queue.
    
    Examples:
      queuectl dlq list
      queuectl dlq retry job123
    """
    if action == "list":
        jobs = storage.list_jobs("dead")
        if not jobs:
            typer.echo("DLQ is empty")
            return
        
        table = Table("ID", "Command", "Attempts", "Last Output")
        for job in jobs:
            table.add_row(
                job.id,
                job.command,
                f"{job.attempts}/{job.max_retries}",
                job.output[-100:] if job.output else "N/A"
            )
        console.print(table)
            
    elif action == "retry":
        if not job_id:
            typer.echo("Job ID required for retry action", err=True)
            raise typer.Exit(1)
            
        jobs = storage.list_jobs("dead")
        job = next((j for j in jobs if j.id == job_id), None)
        if not job:
            typer.echo(f"Job {job_id} not found in DLQ", err=True)
            raise typer.Exit(1)
            
        # Reset job for retry
        job.state = "pending"
        job.attempts = 0
        job.next_retry_at = None
        storage.update_job(job)
        typer.echo(f"Job {job_id} queued for retry")
    else:
        typer.echo("Invalid action. Use 'list' or 'retry'", err=True)
        raise typer.Exit(1)

@app.command(help="Schedule a job for future execution")
def schedule(
    command: str = typer.Option(..., "--command", "-c", help="Command to execute"),
    run_at: str = typer.Option(..., "--at", help="Run at time (ISO format)"),
    max_retries: Optional[int] = typer.Option(None, "--max-retries", "-r"),
    timeout: Optional[int] = typer.Option(None, "--timeout", "-t", help="Timeout in seconds"),
):
    """
    Schedule a job for future execution.
    
    Example:
      queuectl schedule -c "echo hello" --at "2025-12-01T10:00:00Z"
    """
    try:
        run_at_dt = datetime.fromisoformat(run_at.rstrip("Z"))
        if run_at_dt < datetime.utcnow():
            typer.echo("Schedule time must be in the future", err=True)
            raise typer.Exit(1)
            
        job = Job.create(
            id=generate_id(),
            command=command,
            max_retries=max_retries or config.get("max_retries")
        )
        job.run_at = run_at_dt
        job.timeout = timeout
        
        storage.add_job(job)
        typer.echo(f"Job {job.id} scheduled for {run_at}")
        
    except ValueError:
        typer.echo("Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)", err=True)
        raise typer.Exit(1)


def run():
    """Entrypoint so you can: python -m queuectl.cli ... or from main.py."""
    app()
