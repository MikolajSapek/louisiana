import os
import sys
from pathlib import Path

# Configure matplotlib for Vercel BEFORE any imports (must be first)
if os.environ.get("VERCEL") == "1":
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

# Add parent directory to path to import backend
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    # Import Flask app from backend (NOT app.py!)
    from backend import app
    
    # Vercel Python runtime can use either 'app' or 'handler'
    # Export both for maximum compatibility
    handler = app
    
    # Verify that handler is actually a Flask app
    if not hasattr(handler, 'wsgi_app'):
        raise TypeError("Handler is not a valid WSGI application")
        
except Exception as e:
    # Log error for debugging
    import traceback
    error_msg = f"Failed to import Flask app: {e}\n{traceback.format_exc()}"
    print(error_msg, file=sys.stderr)
    raise

# Export both 'handler' and 'app' for Vercel compatibility
__all__ = ["handler", "app"]
