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
    show_borders: bool | None = None,
    merge_bidirectional_routes: bool | None = None,
    open_in_browser: bool = True,
) -> str:
    """Open this project on louisiana.vercel.app: the form is filled in and the site draws the poster.

    paper_format: POSTER_50X70 (portrait, default), POSTER_70X50, POSTER_60X100, POSTER_100X60, POSTCARD.
    font (city labels) / text_font (title, footers) / subtitle_font: Helvetica, Helvetica Regular, Superclarendon, Rockwell, Euphemia UCAS
      (bundled, same everywhere) or Arial, Futura, Avenir, Montserrat, Baskerville, Garamond, Roboto.
    subtitle: second title line, e.g. the name in Inuktitut syllabics (use subtitle_font 'Euphemia UCAS').
    line_style: solid | dashed | dotted | dashdot | dot. line_outline_color: dark edge under the line (rail-map look).
    point_edge_color: ring around city dots. curve_strength: 0 = straight legs (rail-map look), empty = default arcs. repeated_legs: 'double' draws a leg ridden twice as two parallel lines.
    corner_logo (bottom-right): via_yellow, via_yellow_full, via_cream, via_dark, via_dark_full.
    footer_left: text in the bottom-left corner (newline = stacked lines). footer_signature: 'mikolaj' draws
      the owner's signature stroke under it.
    Colours as #RRGGBB. Opens the browser unless open_in_browser is false; returns the link.
    """
    if paper_format and paper_format.strip().upper() not in PAPER_FORMATS:
        raise ValueError(f"Unknown paper_format {paper_format!r}; use one of {', '.join(PAPER_FORMATS)}.")
    url = _encode_link({
        "cities": cities, "title": title, "subtitle": subtitle, "footer_left": footer_left,
        "footer_right": footer_right, "paper_format": paper_format, "dpi": dpi, "background": background,
        "font": font, "font_color": font_color, "text_font": text_font, "subtitle_font": subtitle_font,
        "line_style": line_style, "line_color": line_color, "line_outline_color": line_outline_color,
        "line_width": line_width, "point_size": point_size,
        "point_style": point_style, "point_color": point_color, "point_edge_color": point_edge_color,
        "repeated_legs": repeated_legs, "curve_strength": curve_strength, "corner_logo": corner_logo, "footer_signature": footer_signature, "show_borders": show_borders,
        "merge_bidirectional_routes": merge_bidirectional_routes,
    })
    if open_in_browser:
        _open_browser(url)
    return url


if __name__ == "__main__":
    server.run()
