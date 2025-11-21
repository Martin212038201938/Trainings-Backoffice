"""WSGI entry point for FastAPI on AlwaysData/uWSGI."""
import sys
import site
import json
from pathlib import Path
from datetime import datetime

# Add user site-packages for pip --user installed packages
user_site = Path.home() / ".local/lib/python3.11/site-packages"
if user_site.exists():
    site.addsitedir(str(user_site))

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import FastAPI app
from app.main import app

# Convert ASGI to WSGI
from a2wsgi import ASGIMiddleware
asgi_app = ASGIMiddleware(app)

def application(environ, start_response):
    """WSGI application with direct handlers for critical endpoints."""
    path = environ.get('PATH_INFO', '/')

    # Handle critical endpoints directly for reliability
    if path == '/ping':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        body = json.dumps({
            "ping": "pong",
            "timestamp": datetime.utcnow().isoformat()
        })
        return [body.encode('utf-8')]

    if path == '/health':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        body = json.dumps({
            "status": "ok",
            "app": "Trainings Backoffice",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": "production"
        })
        return [body.encode('utf-8')]

    if path == '/':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        body = json.dumps({
            "app": "Trainings Backoffice",
            "status": "running",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health"
        })
        return [body.encode('utf-8')]

    # Pass all other requests to FastAPI via a2wsgi
    return asgi_app(environ, start_response)
