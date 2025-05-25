#!/usr/bin/env python3
import sys
import os

# Add your project directory to sys.path
# Dynamic path - works regardless of where the project is located
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set environment variables if needed
os.environ.setdefault('FLASK_APP', 'app.py')
os.environ.setdefault('FLASK_ENV', 'production')  # or 'development' for dev environment

# Import your Flask app
try:
    from app import app as application
except ImportError:
    # If the above doesn't work, try this alternative
    import app as application

# This is important for WSGI servers
if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000, debug=False)
