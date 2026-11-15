"""
EduSim FastAPI Application Entry Point Proxy
Allows starting via `uvicorn app.main:app` from EduSim_API directory.
"""
import sys
import os

api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from main import app  # noqa: F401
