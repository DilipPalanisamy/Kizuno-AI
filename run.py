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
    print("  KIZUNO-AI — CITIZEN COMPLAINT TRACKING & ACCOUNTABILITY SYSTEM")
    print("  Backend: Python 3.12 + FastAPI + SQLite (civictrack.db)")
    print("=" * 65)
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("  🌐 ACCESS URLS:")
    print(f"  [💻 Computer Browser]      http://localhost:8000")
    print(f"  [📱 Mobile Phone (Wi-Fi)]  http://{local_ip}:8000")
    print(f"  [👨‍💼 Officer Console]       http://{local_ip}:8000/officer")
    print(f"  [🛡️ Admin Console]         http://{local_ip}:8000/admin")
    print(f"  [☁️ Global Cloud Live]      https://kizuno-ai.onrender.com")
    print("=" * 65 + "\n")

    # Start server.py on 0.0.0.0 so mobile phones on the same Wi-Fi can connect
    try:
        webbrowser.open("http://localhost:8000")
        import uvicorn
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
    except KeyboardInterrupt:
        print("\nKizuno-AI server stopped cleanly.")
    except Exception as e:
        print(f"Error launching Kizuno-AI: {e}")

if __name__ == "__main__":
    main()
