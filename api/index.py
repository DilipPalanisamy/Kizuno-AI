import os
import sys

# Set serverless flag for Vercel execution environment
os.environ["VERCEL"] = "1"

# Add project root directory to Python path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Import the FastAPI application from server.py
from server import app
