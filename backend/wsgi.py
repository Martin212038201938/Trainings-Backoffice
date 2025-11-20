"""
WSGI entry point for the Trainings Backoffice application.

This module is used by WSGI servers like Gunicorn or uWSGI to serve the FastAPI application.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the Python path so imports work correctly
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.main import app

# Wrap the FastAPI app as a WSGI application using Starlette's built-in WSGI support
# FastAPI is based on Starlette, which has built-in ASGI support
# We create a WSGI-compatible application by importing it as an ASGI app
application = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
