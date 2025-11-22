"""Simple WSGI entry point for AlwaysData."""
import json
from datetime import datetime

def application(environ, start_response):
    """Simple WSGI application."""
    path = environ.get('PATH_INFO', '/')

    # Root endpoint
    if path == '/':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [json.dumps({
            "app": "Trainings Backoffice",
            "status": "running",
            "version": "1.0.0"
        }).encode('utf-8')]

    # Health check
    if path == '/health':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [json.dumps({
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat()
        }).encode('utf-8')]

    # Ping
    if path == '/ping':
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [json.dumps({
            "ping": "pong"
        }).encode('utf-8')]

    # 404 for everything else
    status = '404 Not Found'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)
    return [json.dumps({
        "error": "Not found",
        "path": path
    }).encode('utf-8')]
