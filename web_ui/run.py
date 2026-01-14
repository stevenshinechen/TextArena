"""
Simple script to run the TextArena Web UI.
Starts both backend and frontend servers.
"""

import subprocess
import sys
import os
import time
from pathlib import Path


def main():
    root_dir = Path(__file__).parent
    backend_dir = root_dir / "backend"
    frontend_dir = root_dir / "frontend"

    # Check if npm dependencies are installed
    if not (frontend_dir / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=True)

    print("Starting TextArena Web UI...")
    print("-" * 40)

    # Start backend
    print("Starting backend server on http://localhost:8000")
    backend_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=backend_dir,
    )

    time.sleep(2)  # Give backend time to start

    # Start frontend
    print("Starting frontend server on http://localhost:3000")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True,
    )

    print("-" * 40)
    print("🎮 TextArena Web UI is running!")
    print("   Open http://localhost:3000 in your browser")
    print("   Press Ctrl+C to stop")
    print("-" * 40)

    try:
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        backend_process.terminate()
        frontend_process.terminate()


if __name__ == "__main__":
    main()
