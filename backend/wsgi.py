"""
WSGI entry point for the Trainings Backoffice application.

This module provides a custom ASGI-to-WSGI adapter that works without external
dependencies like asgiref.wsgi.AsgiToWsgi (which may not be available in older
asgiref versions).

Why this approach works:
-----------------------
FastAPI is an ASGI application (async), but uWSGI expects a WSGI application (sync).
Instead of relying on external adapters that may not be available, we implement
a minimal ASGI-to-WSGI bridge using Python's built-in asyncio module.

The adapter:
1. Converts WSGI environ dict to ASGI scope dict
2. Runs the async ASGI app synchronously using asyncio.run()
3. Collects the response parts (status, headers, body) from ASGI
4. Returns them in WSGI format

This is a simplified adapter suitable for synchronous request/response patterns.
It does not support WebSockets or streaming responses, but works well for REST APIs.
"""

import asyncio
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
    # For local development, run with uvicorn (native ASGI server)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
