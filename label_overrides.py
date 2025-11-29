from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).parent.resolve()
IS_VERCEL = os.environ.get("VERCEL") == "1"
TMP_DIR = Path(os.environ.get("TMPDIR") or "/tmp")

# On Vercel, use /tmp for writable storage; otherwise use BASE_DIR
if IS_VERCEL:
    OVERRIDES_PATH = TMP_DIR / "label_overrides.json"
else:
    OVERRIDES_PATH = BASE_DIR / "label_overrides.json"

def load_overrides() -> Dict[str, Dict[str, float]]:
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        raw = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            cleaned: Dict[str, Dict[str, float]] = {}
            for key, value in raw.items():
                if isinstance(value, dict):
                    dx = value.get("dx")
                    dy = value.get("dy")
                    try:
                        cleaned[key] = {
                            "dx": float(dx) if dx is not None else 0.0,
                            "dy": float(dy) if dy is not None else 0.0,
                        }
                    except (TypeError, ValueError):
                        continue
            return cleaned
        return {}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}

def save_overrides(data: Dict[str, Dict[str, float]]) -> None:
    try:
        # Ensure parent directory exists (especially for /tmp on Vercel)
        OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, PermissionError) as e:
        # On Vercel or read-only filesystem, log but don't fail
        # Overrides will be lost between invocations, but that's acceptable
        import logging
        logging.warning(f"Could not save label overrides to {OVERRIDES_PATH}: {e}")

def update_override(city: str, dx: float, dy: float) -> Dict[str, Dict[str, float]]:
    data = load_overrides()
    entry = data.get(city, {"dx": 0.0, "dy": 0.0})
    entry["dx"] = entry.get("dx", 0.0) + dx
    entry["dy"] = entry.get("dy", 0.0) + dy
    data[city] = entry
    save_overrides(data)
    return data

def set_override(city: str, dx: float, dy: float) -> Dict[str, Dict[str, float]]:
    data = load_overrides()
    data[city] = {"dx": float(dx), "dy": float(dy)}
    save_overrides(data)
    return data

def reset_override(city: str | None = None) -> Dict[str, Dict[str, float]]:
    if city is None:
        data: Dict[str, Dict[str, float]] = {}
    else:
        data = load_overrides()
        data.pop(city, None)
    save_overrides(data)
    return data
