import os
import sys
from pathlib import Path

# matplotlib on Vercel needs a writable config dir; set before backend imports it
if os.environ.get("VERCEL") == "1":
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Vercel (CLI 65+) needs a top-level Flask "app" in this entrypoint
from backend import app  # noqa: E402

__all__ = ["app"]
