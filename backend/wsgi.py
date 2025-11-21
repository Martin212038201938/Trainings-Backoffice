"""WSGI entry point for FastAPI on AlwaysData/uWSGI."""
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import FastAPI app
from app.main import app

# Convert ASGI to WSGI
from a2wsgi import ASGIMiddleware
application = ASGIMiddleware(app)
