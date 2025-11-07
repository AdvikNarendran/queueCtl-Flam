import subprocess
import time
import uuid
from datetime import datetime
from typing import Optional
from .storage import Storage
from .models import Job

class Worker:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.worker_id = str(uuid.uuid4())
        self.running = False

    def start(self):
        self.running = True
        while self.running:
            job = self.storage.get_pending_job_and_lock(self.worker_id)
            if job:
                self._process_job(job)
            else:
                # No jobs available, wait before polling again
                time.sleep(1)

    def stop(self):
        self.running = False

    def _process_job(self, job: Job):
        try:
            # Run the command
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True
            )

            # Update job based on command result
            if result.returncode == 0:
                job.state = "completed"
            else:
                job.attempts += 1
                if job.attempts >= job.max_retries:
                    job.state = "dead"
                else:
                    job.state = "failed"

            # Release lock
            job.locked_by = None
            job.locked_at = None
            
            # Update job in storage
            self.storage.update_job(job)

        except Exception as e:
            # Handle any unexpected errors
            job.state = "failed"
            job.attempts += 1
            job.locked_by = None
            job.locked_at = None
            self.storage.update_job(job)