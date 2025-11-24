from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).parent.resolve()
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
    OVERRIDES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

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
