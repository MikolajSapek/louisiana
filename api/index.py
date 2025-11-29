import os
import sys
from pathlib import Path

# Konfiguracja matplotlib dla Vercel MUSI być przed innymi importami
if os.environ.get("VERCEL") == "1":
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

# Dodanie katalogu nadrzędnego do ścieżki, aby zaimportować backend
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    # Importujemy aplikację Flask z pliku backend.py
    from backend import app
    
    # WAŻNE: Nie przypisuj tutaj 'handler = app'.
    # Vercel automatycznie znajdzie zmienną 'app' i potraktuje ją jako WSGI.
    # Przypisanie jej do 'handler' powoduje błąd issubclass().

except Exception as e:
    # Logowanie błędów importu
    import traceback
    print(f"Failed to import Flask app: {e}\n{traceback.format_exc()}", file=sys.stderr)
    raise

# Eksportujemy tylko app
__all__ = ["app"]
