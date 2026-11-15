"""MCP server: generate route posters from the terminal (Claude Code) on this Mac.

Run: .venv/bin/python mcp_server.py   (stdio transport)
Register: claude mcp add louisiana -s user -- <repo>/.venv/bin/python <repo>/mcp_server.py
"""
from __future__ import annotations

import base64
import contextlib
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

import backend
import label_overrides

PREVIEW_PORT = 5055  # 5000 is taken by macOS AirPlay
PREVIEW_URL = f"http://127.0.0.1:{PREVIEW_PORT}/preview"
SITE_URL = "https://louisiana.vercel.app/"
REPO_DIR = Path(__file__).parent.resolve()
PAPER_FORMATS = ("POSTER_50X70", "POSTER_70X50", "POSTER_60X100", "POSTER_100X60", "POSTCARD")

server = MCPServer(
    name="louisiana",
    instructions=(
        "Route poster generator. Cities are labelled exactly as typed. "
        "No commas inside a city name; add a region without a comma when a name is "
        "ambiguous (e.g. 'Bird Manitoba'). Run check_cities first for unusual names."
    ),
)


def _place_name(lat: float, lon: float) -> str:
    """Human-readable place for coordinates, so wrong matches are easy to spot."""
    try:
        location = backend.get_geocoder().geolocator.reverse((lat, lon), language="pl", zoom=10, timeout=10)
        return location.address if location else ""
    except Exception:  # network/geocoder failure must not break the check
        return ""


def _ensure_preview_server() -> str | None:
    """Start the local Flask site in the background (once) so /preview shows new posters."""
    with socket.socket() as sock:
        sock.settimeout(0.3)
        if sock.connect_ex(("127.0.0.1", PREVIEW_PORT)) == 0:
            return PREVIEW_URL
    try:
        log = open(REPO_DIR / "preview_server.log", "ab")
        subprocess.Popen(
            [sys.executable, "-m", "flask", "--app", "backend", "run", "--port", str(PREVIEW_PORT)],
            cwd=REPO_DIR, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
        )
    except OSError as exc:
        print(f"Preview server failed to start: {exc}", file=sys.stderr)
        return None
    return PREVIEW_URL


@server.tool()
def open_preview() -> str:
    """Start (if needed) the local site and return the preview page URL."""
    return _ensure_preview_server() or "Preview server could not start; see preview_server.log"


@server.tool()
def check_cities(cities: list[str]) -> list[dict[str, Any]]:
    """Geocode each city (same lookup as the poster) and show where it lands."""
    geocoder = backend.get_geocoder()
    results: list[dict[str, Any]] = []
    for city in cities:
        with contextlib.redirect_stdout(sys.stderr):  # stdout is the MCP channel; geocoder prints errors
            coords = geocoder.get_coordinates(city)
        if coords is None:
            results.append({"city": city, "found": False})
            continue
        lat, lon = coords
        results.append({"city": city, "found": True, "lat": lat, "lon": lon, "place": _place_name(lat, lon)})
    return results


def _encode_link(project: dict[str, Any]) -> str:
    """Site URL that opens the project in the web form (static/app.js reads #p=)."""
    data = {k: ("\n".join(v) if isinstance(v, list) else v) for k, v in project.items() if v is not None}
    token = base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False).encode()).decode().rstrip("=")
    return f"{SITE_URL}#p={token}"


@server.tool()
def site_link(
    cities: list[str],
    title: str | None = None,
    footer_left: str | None = None,
    footer_right: str | None = None,
    paper_format: str | None = None,
    dpi: int | None = None,
    background: str | None = None,
    font_color: str | None = None,
    line_style: str | None = None,
    line_color: str | None = None,
    point_style: str | None = None,
    point_color: str | None = None,
    show_borders: bool | None = None,
    merge_bidirectional_routes: bool | None = None,
) -> str:
    """Link that opens this project on louisiana.vercel.app: form filled in, poster generated, labels editable there."""
    return _encode_link({
        "cities": cities, "title": title, "footer_left": footer_left, "footer_right": footer_right,
        "paper_format": paper_format, "dpi": dpi, "background": background, "font_color": font_color,
        "line_style": line_style, "line_color": line_color, "point_style": point_style,
        "point_color": point_color, "show_borders": show_borders,
        "merge_bidirectional_routes": merge_bidirectional_routes,
    })


@server.tool()
def generate_poster(
    cities: list[str],
    title: str | None = None,
    footer_left: str | None = None,
    footer_right: str | None = None,
    paper_format: str | None = None,
    dpi: int = 300,
    background: str | None = None,
    font_color: str | None = None,
    line_style: str | None = None,
    line_color: str | None = None,
    point_style: str | None = None,
    point_color: str | None = None,
    show_borders: bool = False,
    merge_bidirectional_routes: bool = False,
    hidden_labels: list[str] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Render the final poster PNG (with labels) for the route, in order.

    paper_format: POSTER_50X70, POSTER_70X50, POSTER_60X100, POSTER_100X60, POSTCARD or empty (auto size).
    line_style: dashed | dotted | solid. point_style: circle | star | ...
    output_path: optional extra copy of the PNG (e.g. ~/Desktop/poster.png).
    """
    if paper_format and paper_format.strip().upper() not in PAPER_FORMATS:
        raise ValueError(f"Unknown paper_format {paper_format!r}; use one of {', '.join(PAPER_FORMATS)} or leave empty.")
    payload = {
        "cities": cities, "title": title, "footer_left": footer_left, "footer_right": footer_right,
        "paper_format": paper_format, "dpi": dpi, "background": background, "font_color": font_color,
        "line_style": line_style, "line_color": line_color, "point_style": point_style,
        "point_color": point_color, "show_borders": show_borders,
        "merge_bidirectional_routes": merge_bidirectional_routes,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    with contextlib.redirect_stdout(sys.stderr):  # geocoder prints errors
        route, warnings, options, error = backend._prepare_generation(payload)
    if error is not None:
        raise ValueError(error[0])

    # stdout is the MCP stdio channel: route the generator's print() calls to stderr
    with backend.app.test_request_context(), contextlib.redirect_stdout(sys.stderr):  # url_for needs a request
        info = backend._create_map(
            route, options, label_overrides.load_overrides(), render_labels=True,
            output_filename=f"map_final_mcp_{backend.uuid4().hex}.png",
            hidden_labels=set(hidden_labels or []),
        )
    file = backend.MAP_STORAGE_DIR / Path(info["mapUrl"]).name
    result = {"file": str(file), "cities": [p["name"] for p in route], "warnings": warnings,
              "paper": info.get("paper_label"), "preview": _ensure_preview_server(), "site": _encode_link(payload)}
    if output_path:
        dest = Path(output_path).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, dest)
        result["copy"] = str(dest)
    return result


@server.tool()
def move_label(city: str, dx: float, dy: float) -> dict[str, dict[str, float]]:
    """Shift a city's label by dx/dy (map degrees, adds to the current offset). Re-run generate_poster after."""
    return label_overrides.update_override(city, dx, dy)


@server.tool()
def reset_labels(city: str | None = None) -> dict[str, dict[str, float]]:
    """Reset one city's label offset, or all of them when city is empty."""
    return label_overrides.reset_override(city)


@server.tool()
def list_labels() -> dict[str, dict[str, float]]:
    """Current label offsets per city."""
    return label_overrides.load_overrides()


if __name__ == "__main__":
    server.run()
