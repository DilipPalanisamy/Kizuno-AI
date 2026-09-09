"""
CivicTrack (Kizuna-AI) - One-Command Launcher
Launches the Python FastAPI backend, connects to SQLite database,
and opens the application in your default web browser.
"""

import sys
import webbrowser
import time
import subprocess

def main():
    print("=" * 65)
    print("  CIVICTRACK — CITIZEN COMPLAINT TRACKING & ACCOUNTABILITY SYSTEM")
    print("  Backend: Python 3.12 + FastAPI + SQLite (civictrack.db)")
    print("=" * 65)
    print("\nStarting local server on http://127.0.0.1:8000 ...")

    # Start server.py
    try:
        # Give a small delay then open browser
        webbrowser.open("http://127.0.0.1:8000")
        import uvicorn
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
    except KeyboardInterrupt:
        print("\nCivicTrack server stopped cleanly.")
    except Exception as e:
        print(f"Error launching CivicTrack: {e}")

if __name__ == "__main__":
    main()
