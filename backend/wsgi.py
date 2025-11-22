"""WSGI entry point for Flask app on AlwaysData."""
import sys
import site
from pathlib import Path

# Add user site-packages for pip --user installed packages
user_site = Path.home() / ".local/lib/python3.11/site-packages"
if user_site.exists():
    site.addsitedir(str(user_site))

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import Flask app
from app.flask_app import application
