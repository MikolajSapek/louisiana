"""MCP server: send route posters from the terminal (Claude Code) to louisiana.vercel.app.

The site draws the poster; MCP only checks city names and opens the project on the site
(form filled in, poster generated, labels draggable there).

Run: .venv/bin/python mcp_server.py   (stdio transport)
Register: claude mcp add louisiana -s user -- <repo>/.venv/bin/python <repo>/mcp_server.py
"""
from __future__ import annotations

import base64
import contextlib
import json
import sys
import webbrowser
from typing import Any

from mcp.server.mcpserver import MCPServer

import backend

SITE_URL = "https://louisiana.vercel.app/"
LOCAL_PORT = 5056
LOCAL_URL = f"http://127.0.0.1:{LOCAL_PORT}/"
REPO_DIR = __import__("pathlib").Path(__file__).parent.resolve()
PAPER_FORMATS = ("POSTER_50X70", "POSTER_70X50", "POSTER_60X100", "POSTER_100X60", "POSTCARD")

server = MCPServer(
    name="louisiana",
    instructions=(
        "Route poster generator at louisiana.vercel.app. Use site_link to open a project on the site; "
        "never render posters locally. Cities are labelled exactly as typed. No commas inside a city name; "
        "add a region in square brackets when a name is ambiguous: 'Bird [Manitoba]' is found in Manitoba but labelled "
        "'Bird'. Run check_cities first "
        "for unusual names. A leg ridden twice shows as a double line only if the return trip lists the same "
        "stops in reverse order (repeated_legs='double')."
    ),
)


def _place_name(lat: float, lon: float) -> str:
    """Human-readable place for coordinates, so wrong matches are easy to spot."""
    try:
        location = backend.get_geocoder().geolocator.reverse((lat, lon), language="pl", zoom=10, timeout=10)
        return location.address if location else ""
    except Exception:  # network/geocoder failure must not break the check
        return ""


@server.tool()
def check_cities(cities: list[str]) -> list[dict[str, Any]]:
    """Geocode each city (same lookup as the site) and show where it lands."""
    geocoder = backend.get_geocoder()
    results: list[dict[str, Any]] = []
    for city in cities:
        with contextlib.redirect_stdout(sys.stderr):  # stdout is the MCP channel; geocoder prints errors
            coords = geocoder.get_coordinates(backend._split_label_hint(city)[1])
        if coords is None:
            results.append({"city": city, "found": False})
            continue
        lat, lon = coords
        results.append({"city": city, "found": True, "lat": lat, "lon": lon, "place": _place_name(lat, lon)})
    return results


def _pin(city: str) -> str:
    """'Thompson [Manitoba]' -> 'Thompson [55.74 -97.86]' using the same lookup as the site."""
    label, query = backend._split_label_hint(city)
    with contextlib.redirect_stdout(sys.stderr):  # stdout is the MCP channel; geocoder prints errors
        coords = backend.get_geocoder().get_coordinates(query)
    return f"{label} [{coords[0]:.6g} {coords[1]:.6g}]" if coords else city


def _ensure_local_site() -> str:
    """Start the local copy of the site (has the private fonts) in the background, once."""
    import socket
    import subprocess

    with socket.socket() as sock:
        sock.settimeout(0.3)
        if sock.connect_ex(("127.0.0.1", LOCAL_PORT)) != 0:
            log = open(REPO_DIR / "local_site.log", "ab")
            subprocess.Popen([sys.executable, "-m", "flask", "--app", "backend", "run", "--port", str(LOCAL_PORT)],
                             cwd=REPO_DIR, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    return LOCAL_URL


def _open_browser(url: str) -> None:
    """Open the project on the site so the user can adjust it by hand."""
    try:
        webbrowser.open(url)
    except Exception as exc:  # no browser must not fail the tool
        print(f"Could not open browser: {exc}", file=sys.stderr)


def _encode_link(project: dict[str, Any]) -> str:
    """Site URL that opens the project in the web form (static/app.js reads #p=). Keys are form field names."""
    data = {k: ("\n".join(v) if isinstance(v, list) else v) for k, v in project.items() if v is not None}
    token = base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False).encode()).decode().rstrip("=")
    return f"{SITE_URL}#p={token}"


@server.tool()
def site_link(
    cities: list[str],
    title: str | None = None,
    subtitle: str | None = None,
    footer_left: str | None = None,
    footer_right: str | None = None,
    paper_format: str | None = "POSTER_50X70",
    dpi: int | None = None,
    background: str | None = None,
    font: str | None = None,
    font_color: str | None = None,
    text_font: str | None = None,
    subtitle_font: str | None = None,
    line_style: str | None = None,
    line_color: str | None = None,
    line_outline_color: str | None = None,
    line_width: float | None = None,
    point_size: float | None = None,
    point_style: str | None = None,
    point_color: str | None = None,
    point_edge_color: str | None = None,
    repeated_legs: str | None = None,
    curve_strength: float | None = None,
    corner_logo: str | None = None,
    footer_signature: str | None = None,
    title_font_size: float | None = None,
    title_color: str | None = None,
    footer_font: str | None = None,
    footer_font_size: float | None = None,
    footer_y: float | None = None,
    footer_line_gap: float | None = None,
    footer_stroke: float | None = None,
    footer_align: str | None = None,
    dashed_from: int | None = None,
    show_water: bool | None = None,
    water_color: str | None = None,
    include_points: str | None = None,
    major_labels: list[str] | None = None,
    minor_labels: list[str] | None = None,
    subtitle_color: str | None = None,
    label_color: str | None = None,
    label_font_size: float | None = None,
    show_borders: bool | None = None,
    merge_bidirectional_routes: bool | None = None,
    open_in_browser: bool = True,
    pin_coordinates: bool = True,
    local: bool = False,
) -> str:
    """Open this project on louisiana.vercel.app: the form is filled in and the site draws the poster.

    paper_format: POSTER_50X70 (portrait, default), POSTER_70X50, POSTER_60X100, POSTER_100X60, POSTCARD.
    font (city labels) / text_font (title, footers) / subtitle_font: Helvetica, Helvetica Regular, Superclarendon, Rockwell, Euphemia UCAS (plus private local fonts such as Mounties)
      (bundled, same everywhere) or Arial, Futura, Avenir, Montserrat, Baskerville, Garamond, Roboto.
    subtitle: second title line, e.g. the name in Inuktitut syllabics (use subtitle_font 'Euphemia UCAS').
    line_style: solid | dashed | dotted | dashdot | dot. line_outline_color: dark edge under the line (rail-map look).
    point_edge_color: ring around city dots. curve_strength: 0 = straight legs (rail-map look), empty = default arcs. repeated_legs: 'double' draws a leg ridden twice as two parallel lines.
    corner_logo (bottom-right): via_yellow, via_yellow_full, via_cream, via_dark, via_dark_full.
    dashed_from: 1-based city index from which legs are dashed and thinner (e.g. where the bus starts).
    show_water: draw seas and lakes (Natural Earth 1:50m) a shade darker than the background (or water_color).
    include_points: extra "lat lon" lines the map must cover (e.g. "58.8 -90" to show Hudson Bay by Churchill).
    major_labels / minor_labels: place names drawn bigger in the title colour / smaller.
    footer_left: text in the bottom-left corner (newline = stacked lines). footer_signature: 'mikolaj' draws
      the owner's signature stroke under it.
    Colours as #RRGGBB. Opens the browser unless open_in_browser is false; returns the link.
    local: open the local copy of the site on this Mac (it has the private fonts: Mounties, Indians, North Railway)
      instead of louisiana.vercel.app; labels are draggable there too.
    pin_coordinates: look cities up here and send them as 'Name [lat lon]' so the site never geocodes
      (its shared server IP gets throttled and towns go missing). Unfound cities are sent as typed.
    """
    if pin_coordinates:
        cities = [_pin(city) for city in cities]
    if paper_format and paper_format.strip().upper() not in PAPER_FORMATS:
        raise ValueError(f"Unknown paper_format {paper_format!r}; use one of {', '.join(PAPER_FORMATS)}.")
    url = _encode_link({
        "cities": cities, "title": title, "subtitle": subtitle, "footer_left": footer_left,
        "footer_right": footer_right, "paper_format": paper_format, "dpi": dpi, "background": background,
        "font": font, "font_color": font_color, "text_font": text_font, "subtitle_font": subtitle_font,
        "line_style": line_style, "line_color": line_color, "line_outline_color": line_outline_color,
        "line_width": line_width, "point_size": point_size,
        "point_style": point_style, "point_color": point_color, "point_edge_color": point_edge_color,
        "repeated_legs": repeated_legs, "curve_strength": curve_strength, "corner_logo": corner_logo, "footer_signature": footer_signature,
        "title_font_size": title_font_size, "label_font_size": label_font_size,
        "title_color": title_color, "footer_font": footer_font, "footer_font_size": footer_font_size, "footer_y": footer_y, "footer_line_gap": footer_line_gap, "footer_stroke": footer_stroke, "footer_align": footer_align,
        "dashed_from": dashed_from, "show_water": show_water, "water_color": water_color, "include_points": include_points,
        "major_labels": major_labels, "minor_labels": minor_labels, "subtitle_color": subtitle_color, "label_color": label_color, "show_borders": show_borders,
        "merge_bidirectional_routes": merge_bidirectional_routes,
    })
    if local:
        url = url.replace(SITE_URL, _ensure_local_site(), 1)
    if open_in_browser:
        _open_browser(url)
    return url


if __name__ == "__main__":
    server.run()
