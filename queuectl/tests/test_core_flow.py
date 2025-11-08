import os
import time
import unittest
from datetime import datetime, timedelta
from queuectl.storage import Storage
from queuectl.models import Job
from queuectl.worker import Worker, WorkerPool
from queuectl.config import Config

class TestCoreFlow(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_jobs.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.storage = Storage(self.test_db)
        self.config = Config()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_basic_job_flow(self):
        """Test that a basic job completes successfully"""
        # Create and enqueue job
        job = Job.create("test1", "echo hello", max_retries=3)
        self.storage.add_job(job)

        # Start worker and process job
        worker = Worker(self.storage, self.config)
        worker._process_job(job)

        # Check job completed
        updated_job = self.storage.list_jobs()[0]
        self.assertEqual(updated_job.state, "completed")
        self.assertIn("hello", updated_job.output or "")

    def test_failed_job_retry(self):
        """Test that failed jobs retry with backoff"""
        # Create job with invalid command
        job = Job.create("test2", "invalid_command", max_retries=2)
        self.storage.add_job(job)

        worker = Worker(self.storage, self.config)
        worker._process_job(job)

        # Check job failed and scheduled for retry
        updated_job = self.storage.list_jobs()[0]
        self.assertEqual(updated_job.state, "failed")
        self.assertEqual(updated_job.attempts, 1)
        self.assertIsNotNone(updated_job.next_retry_at)

        # Process again to move to dead letter queue
        worker._process_job(updated_job)
        final_job = self.storage.list_jobs()[0]
        self.assertEqual(final_job.state, "dead")
        self.assertEqual(final_job.attempts, 2)

    def test_scheduled_job(self):
        """Test that scheduled jobs don't run before their time"""
        future = datetime.utcnow() + timedelta(hours=1)
        job = Job.create("test3", "echo scheduled", max_retries=3)
        job.run_at = future
        self.storage.add_job(job)

        worker = Worker(self.storage, self.config)
        # Try to get job - should return None as it's scheduled for future
        fetched_job = self.storage.get_pending_job_and_lock(worker.worker_id)
        self.assertIsNone(fetched_job)

    def test_job_timeout(self):
        """Test that jobs respect their timeout"""
        job = Job.create("test4", "sleep 10", max_retries=1)
        job.timeout = 1  # 1 second timeout
        self.storage.add_job(job)

        worker = Worker(self.storage, self.config)
        worker._process_job(job)

        updated_job = self.storage.list_jobs()[0]
        self.assertEqual(updated_job.state, "failed")
        self.assertIn("timeout", (updated_job.output or "").lower())

    def test_worker_pool(self):
        """Test multiple workers processing jobs"""
        # Create multiple jobs
        for i in range(3):
            job = Job.create(f"test{i}", f"echo job{i}", max_retries=1)
            self.storage.add_job(job)

        # Start worker pool with 2 workers
        pool = WorkerPool(self.storage, self.config)
        pool.start(count=2)

        # Give some time for processing
        time.sleep(2)
        pool.stop()

        # Check all jobs completed
        jobs = self.storage.list_jobs()
        completed = [j for j in jobs if j.state == "completed"]
        self.assertEqual(len(completed), 3)

if __name__ == '__main__':
    unittest.main()