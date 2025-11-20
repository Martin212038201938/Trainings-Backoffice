"""
WSGI entry point for the Trainings Backoffice application.

This module is used by WSGI servers like Gunicorn or uWSGI to serve the FastAPI application.
"""

import os
import sys
from pathlib import Path
from asgiref.wsgi import AsgiToWsgi
# Add the backend directory to the Python path so imports work correctly
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.main import app

# Wrap the ASGI FastAPI app with WsgiToAsgi to make it WSGI-compatible for uWSGI
application = AsgiToWsgi(app)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Force deployment to restart uWSGI with correct ASGI to WSGI wrapper
