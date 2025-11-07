import json
import typer
from typing import Optional, Any
from .storage import Storage
from .models import Job
from .worker import Worker
from .config import Config
from .utils import generate_id

app = typer.Typer()
storage = Storage()
config = Config()

@app.command()
def enqueue(job_data: str):
    """Add a new job to the queue"""
    try:
        data = json.loads(job_data)
        job_id = data.get("id", generate_id())
        command = data["command"]
        max_retries = data.get("max_retries", config.get("max_retries"))
        
        job = Job.create(job_id, command, max_retries)
        storage.add_job(job)
        typer.echo(f"Job {job_id} enqueued successfully")
    
    except (json.JSONDecodeError, KeyError) as e:
        typer.echo(f"Error: Invalid job data - {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def list_jobs(state: Optional[str] = None):
    """List jobs, optionally filtered by state"""
    jobs = storage.list_jobs(state)
    for job in jobs:
        typer.echo(
            f"Job {job.id}: {job.command} "
            f"(state={job.state}, attempts={job.attempts})"
        )

@app.command()
def status():
    """Show queue status and stats"""
    stats = storage.get_stats()
    typer.echo("Queue Status:")
    for state, count in stats.items():
        typer.echo(f"  {state}: {count} jobs")

@app.command()
def config_set(key: str, value: str):
    """Set configuration value"""
    try:
        # Try to convert string values to appropriate types
        actual_value: Any
        if value.isdigit():
            actual_value = int(value)
        elif value.lower() in ('true', 'false'):
            actual_value = value.lower() == 'true'
        else:
            actual_value = value
        
        config.set(key, actual_value)
        typer.echo(f"Configuration {key} set to {actual_value}")
    
    except Exception as e:
        typer.echo(f"Error setting configuration: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def worker(action: str = typer.Argument(..., help="Action: start/stop")):
    """Manage workers"""
    if action == "start":
        worker = Worker(storage)
        typer.echo(f"Starting worker {worker.worker_id}")
        try:
            worker.start()
        except KeyboardInterrupt:
            worker.stop()
            typer.echo("\nWorker stopped")
    else:
        typer.echo("Invalid action. Use 'start' or 'stop'", err=True)
        raise typer.Exit(1)

def run():
    app()