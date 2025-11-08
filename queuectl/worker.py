import subprocess
import shlex
import time
import uuid
import signal
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from threading import Thread, Event
from .storage import Storage
from .models import Job
from .config import Config

class WorkerPool:
    def __init__(self, storage: Storage, config: Config):
        self.storage = storage
        self.config = config
        self.workers: Dict[str, Worker] = {}
        self.stop_event = Event()
        self.threads: List[Thread] = []

    def start(self, count: int = 1, use_shell: bool = False):
        """Start multiple workers"""
        print(f"Starting {count} worker(s)...")  # Debug output
        for i in range(count):
            worker = Worker(self.storage, self.config, use_shell)
            self.workers[worker.worker_id] = worker
            thread = Thread(target=worker.start, daemon=True, name=f"Worker-{i+1}")
            thread.start()
            self.threads.append(thread)
            print(f"Worker {worker.worker_id} started")  # Debug output

    def stop(self):
        """Stop all workers gracefully"""
        print("Stopping all workers...")  # Debug output
        self.stop_event.set()
        for worker in self.workers.values():
            worker.stop()
        
        # Wait for all threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        self.workers.clear()
        self.threads.clear()
        print("All workers stopped")  # Debug output

    def get_active_count(self) -> int:
        """Return number of active workers"""
        return sum(1 for t in self.threads if t.is_alive())

class Worker:
    def __init__(self, storage: Storage, config: Config, use_shell: bool = False):
        self.storage = storage
        self.config = config
        self.worker_id = str(uuid.uuid4())
        self.running = False
        self.use_shell = use_shell
        self.current_process: Optional[subprocess.Popen] = None
        print(f"Worker {self.worker_id} initialized")  # Debug output

    def start(self):
        print(f"Worker {self.worker_id} starting")  # Debug output
        self.running = True
        while self.running:
            try:
                job = self.storage.get_pending_job_and_lock(self.worker_id)
                if job:
                    print(f"Worker {self.worker_id} processing job {job.id}")  # Debug output
                    
                    if job.run_at and job.run_at > datetime.utcnow():
                        # Job scheduled for future, release lock
                        print(f"Job {job.id} scheduled for future, releasing lock")  # Debug output
                        job.locked_by = None
                        job.locked_at = None
                        self.storage.update_job(job)
                        time.sleep(1)
                        continue
                    
                    self._process_job(job)
                else:
                    # No job available, wait before polling again
                    time.sleep(1)
            except Exception as e:
                print(f"Worker {self.worker_id} error: {str(e)}")  # Debug output
                time.sleep(1)  # Wait before retrying

    def stop(self):
        """Stop worker gracefully"""
        self.running = False
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)  # Wait up to 5 seconds
            except Exception:
                # Force kill if graceful termination fails
                self.current_process.kill()

    def _run_command(self, command: str, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """Run command with timeout support"""
        try:
            if self.use_shell:
                self.current_process = subprocess.Popen(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                self.current_process = subprocess.Popen(
                    shlex.split(command), 
                    shell=False, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            stdout, stderr = self.current_process.communicate(timeout=timeout)
            return subprocess.CompletedProcess(
                args=command,
                returncode=self.current_process.returncode,
                stdout=stdout,
                stderr=stderr
            )
        except subprocess.TimeoutExpired:
            if self.current_process:
                self.current_process.terminate()
            raise
        finally:
            self.current_process = None

    def _calculate_next_retry(self, attempts: int) -> datetime:
        """Calculate next retry time using exponential backoff"""
        backoff_base = self.config.get("backoff_base")
        delay = backoff_base ** attempts  # exponential backoff
        return datetime.utcnow() + timedelta(seconds=delay)

    def _process_job(self, job: Job):
        try:
            result = self._run_command(job.command, timeout=job.timeout)
            
            # Store command output
            job.output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

            if result.returncode == 0:
                job.state = "completed"
            else:
                job.attempts += 1
                if job.attempts >= job.max_retries:
                    job.state = "dead"  # Move to DLQ
                else:
                    job.state = "failed"  # Mark as failed for retry
                    job.next_retry_at = self._calculate_next_retry(job.attempts)

        except subprocess.TimeoutExpired:
            job.attempts += 1
            job.output = "Error: Job timed out"
            if job.attempts >= job.max_retries:
                job.state = "dead"
            else:
                job.state = "failed"
                job.next_retry_at = self._calculate_next_retry(job.attempts)

        except Exception as e:
            job.attempts += 1
            job.output = f"Error: {str(e)}"
            if job.attempts >= job.max_retries:
                job.state = "dead"
            else:
                job.state = "failed"
                job.next_retry_at = self._calculate_next_retry(job.attempts)

        finally:
            # Release lock
            job.locked_by = None
            job.locked_at = None
            self.storage.update_job(job)
