import pytest
import os
import time
import threading
from queuectl.storage import Storage
from queuectl.models import Job
from queuectl.worker import Worker

@pytest.fixture
def storage():
    # Use a test database
    db_path = "test_jobs.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    return Storage(db_path)

def test_basic_flow(storage):
    # Create and enqueue a job
    job = Job.create("test-job", "echo 'Hello World'")
    storage.add_job(job)

    # Verify job is in pending state
    jobs = storage.list_jobs("pending")
    assert len(jobs) == 1
    assert jobs[0].id == "test-job"

    # Start a worker and let it process the job
    worker = Worker(storage)
    worker_thread = threading.Thread(target=worker.start)
    worker_thread.daemon = True
    worker_thread.start()

    # Wait for job to complete
    time.sleep(2)
    worker.stop()
    worker_thread.join(timeout=1)

    # Verify job completed successfully
    jobs = storage.list_jobs("completed")
    assert len(jobs) == 1
    assert jobs[0].id == "test-job"

def test_failed_job(storage):
    # Create a job with an invalid command
    job = Job.create("fail-job", "invalid_command")
    storage.add_job(job)

    # Start a worker and let it process the job
    worker = Worker(storage)
    worker_thread = threading.Thread(target=worker.start)
    worker_thread.daemon = True
    worker_thread.start()

    # Wait for job to fail
    time.sleep(2)
    worker.stop()
    worker_thread.join(timeout=1)

    # Verify job is marked as failed
    jobs = storage.list_jobs("failed")
    assert len(jobs) == 1
    assert jobs[0].id == "fail-job"
    assert jobs[0].attempts == 1