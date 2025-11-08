import sys
import os
from queuectl.cli import run

if __name__ == "__main__":
    # Ensure we're using line buffering for output
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)
    try:
        print("Starting queuectl...")
        run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
