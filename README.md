<!--
README for QueueCTL

This file is written to be GitHub-friendly (markdown), easy to read, and contains
examples targeted at Windows PowerShell (the environment used for development in
this repository). Adjust shell commands for other platforms as needed.
-->

# 🚀 QueueCTL  
### **A Lightweight, Production-Grade Background Job Queue with Worker Pools & DLQ Support**

QueueCTL is a **robust, developer-friendly background job queue system** designed for executing 
command-based tasks asynchronously.  
It provides a clean CLI to enqueue jobs, run multiple workers, schedule future jobs, retry failures 
using exponential backoff, and safely handle permanently failed jobs using a **Dead Letter Queue (DLQ)**.

Perfect for:  
✅ Task automation  
✅ Background processing  
✅ Local distributed systems  
✅ Worker orchestration demos  
✅ Learning internal mechanics of job queues  

QueueCTL is intentionally lightweight yet implements real-world queueing concepts — making it both 
**practical** and **educational**.

---

# ⭐ Key Features & Benefits

###  **1. CLI-Based Job Management**
- Enqueue jobs  
- Start/stop workers  
- Query job states  
- Manage DLQ and retries  

###  **2. Persistent Storage (SQLite)**
Jobs survive restarts thanks to durable on-disk storage.

###  **3. Automatic Retry System**
Failed jobs automatically retry with **exponential backoff**.

###  **4. Dead Letter Queue (DLQ)**
Failed jobs are moved to DLQ for inspection & manual retry.

###  **5. Multi-Worker Parallel Execution**
Supports multiple concurrent worker processes.

###  **6. Job Locking & No-Duplicate Guarantee**
Ensures only one worker processes a job.

###  **7. Job Scheduling**
Run jobs at a future timestamp with `run_at`.

###  **8. Built-In Timeout Handling**
Jobs exceeding their timeout are cleanly terminated.

###  **9. Detailed Execution Logs**
Each job stores stdout/stderr, timestamps, and duration.

---

# 📘 Why This Project Exists

QueueCTL was built to:

✅ Teach real-world queue mechanics  
✅ Demonstrate concurrency design  
✅ Provide a flexible worker system for automation  
✅ Offer a lightweight alternative to Celery/RQ  
✅ Serve as an internship-ready project showcasing engineering depth  

Internally, it demonstrates:
- Persistent job orchestration  
- Transaction-safe locking  
- Fault tolerance  
- Scheduling & backoff algorithms  
- Cross-platform process execution  

---

# 🏗 Architecture Overview

## 🔹 1. Job Creation
Jobs include metadata such as command, retries, and timestamps.

## 🔹 2. Workers Poll for Jobs
Workers fetch, lock, execute, log, and update jobs.

## 🔹 3. Retry & Backoff
Failed jobs retry with exponential backoff.

## 🔹 4. Dead Letter Queue
Jobs exceeding retries move to DLQ.

## 🔹 5. Concurrency Guarantees
Safe job locking ensures no duplicate execution.

---

# 📥 Installation

```bash
git clone https://github.com/adviktoppernarendran-prog/queueCtl-Flam.git
cd queueCtl-Flam
```

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows
```

```bash
pip install -e .
```

---

# ▶️ Quick Usage

```bash
queuectl enqueue "python -c \"print('Hello')\""
```

```bash
queuectl worker start --count 3
```

```bash
queuectl dlq list
```

---

# ⚙️ Configuration

Location:
```
~/.queuectl/config.json
```

Example:
```json
{
  "max_retries": 5,
  "backoff_base": 3,
  "worker_count": 2
}
```

---

# Project Structure

```
queueCtl-Flam/
│
├── README.md
├── main.py
├── queuectl/
│   ├── cli.py
│   ├── worker.py
│   ├── storage.py
│   ├── config.py
│   ├── models.py
│   ├── utils.py
│   ├── tests/
│   └── job2.json
└── setup.py
```

---




#  Acknowledgments

- Typer — CLI framework  
- Rich — Terminal visuals  
- SQLite — Persistent storage  
- Python multiprocessing — Worker orchestration  
