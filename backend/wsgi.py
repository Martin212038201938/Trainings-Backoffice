"""
WSGI entry point for the Trainings Backoffice application.

This module is used by WSGI servers like Gunicorn to serve the FastAPI application.
"""

from app.main import app

# For WSGI servers that need a 'application' callable
application = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
