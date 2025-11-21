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

# Import the FastAPI app with error handling
try:
    from app.main import app
    logger.info("FastAPI application loaded successfully")
except Exception as e:
    logger.error(f"Failed to load FastAPI application: {e}")
    logger.error(traceback.format_exc())
    raise

# Use a2wsgi for ASGI to WSGI conversion
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
    logger.info("WSGI application ready (using a2wsgi)")
except Exception as e:
    logger.error(f"Failed to create WSGI application: {e}")
    logger.error(traceback.format_exc())
    raise

if __name__ == "__main__":
    # For local development, run with uvicorn (native ASGI server)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
