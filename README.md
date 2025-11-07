# QueueCTL

A CLI-based background job queue system that manages jobs with worker processes, handles retries using exponential backoff, and maintains a Dead Letter Queue (DLQ) for permanently failed jobs.

## Features

- Job queuing and execution
- Multiple worker support
- Automatic retries with exponential backoff
- Dead Letter Queue (DLQ)
- Persistent storage using SQLite
- Configuration management
- Clean CLI interface

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd queuectl
```

2. Create a virtual environment and activate it:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Enqueue a job
```bash
queuectl enqueue '{"id":"job1","command":"echo Hello World"}'
```

### List jobs
```bash
queuectl list
queuectl list --state pending
```

### Check queue status
```bash
queuectl status
```

### Start a worker
```bash
queuectl worker start
```

### Configure settings
```bash
queuectl config set max-retries 3
```

## Development

Run tests:
```bash
pytest
```