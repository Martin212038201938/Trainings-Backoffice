"""
WSGI entry point for the Trainings Backoffice application.

Uses a2wsgi to convert the FastAPI ASGI application to WSGI for deployment
on servers like AlwaysData that use uWSGI.
"""

import logging
import sys
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Add the backend directory to the Python path so imports work correctly
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# TEMPORARY: Simple test to verify uWSGI is working
def test_application(environ, start_response):
    """Simple WSGI app to test if uWSGI works at all."""
    path = environ.get('PATH_INFO', '/')
    logger.info(f"Test app received request: {path}")

    status = '200 OK'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)

    response = f'{{"test": "ok", "path": "{path}", "message": "uWSGI is working!"}}'
    return [response.encode('utf-8')]

# Use test app first to verify uWSGI works
application = test_application
logger.info("Test WSGI application ready")

if __name__ == "__main__":
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="0.0.0.0", port=8000)
