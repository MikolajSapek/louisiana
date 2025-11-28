from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_from_directory, url_for

from geocoder import Geocoder
from map_generator import MapGenerator, PosterMapGenerator, LandscapePosterMapGenerator, LargePosterMapGenerator, LandscapeLargePosterMapGenerator
from label_overrides import load_overrides, update_override, reset_override, set_override

BASE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "static"
LOCAL_MAPS_DIR = STATIC_DIR / "maps"
LOCAL_MAPS_DIR.mkdir(parents=True, exist_ok=True)

TMP_DIR = Path(os.environ.get("TMPDIR") or "/tmp")
IS_VERCEL = os.environ.get("VERCEL") == "1"
MAP_STORAGE_DIR = LOCAL_MAPS_DIR if not IS_VERCEL else (TMP_DIR / "maps")
MAP_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(BASE_DIR / "templates"))

geocoder = Geocoder()


def _normalize_cities(cities_raw: Any) -> List[str]:
    if isinstance(cities_raw, list):
        values = cities_raw
    elif isinstance(cities_raw, str):
        separators = [",", "\n", "\r"]
        for sep in separators:
            cities_raw = cities_raw.replace(sep, "\n")
        values = cities_raw.split("\n")
    else:
        values = []

    normalized = [value.strip() for value in values if value and value.strip()]
    return normalized


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "t", "yes", "y", "tak"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _build_route(cities: List[str]) -> tuple[List[Dict[str, Any]], List[str]]:
    route: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for city in cities:
        coords = geocoder.get_coordinates(city)
        if coords:
            lat, lon = coords
            route.append({
                "name": city,
                "latitude": lat,
                "longitude": lon,
            })
        else:
            warnings.append(f"Nie udało się pobrać współrzędnych dla '{city}'. Pomijam punkt.")
    return route, warnings


@app.route("/")
def index() -> str:
    paper_formats = [
        {"id": "", "label": "Automatycznie"},
        {"id": "POSTCARD", "label": "Pocztówka 10 × 15 cm (4 × 6 cali)"},
        {"id": PosterMapGenerator.FORMAT_ID, "label": "Plakat 50 × 70 cm (pionowy)"},
        {"id": LandscapePosterMapGenerator.FORMAT_ID, "label": "Plakat 70 × 50 cm (poziomy)"},
        {"id": LargePosterMapGenerator.FORMAT_ID, "label": "Plakat 60 × 100 cm (pionowy)"},
        {"id": LandscapeLargePosterMapGenerator.FORMAT_ID, "label": "Plakat 100 × 60 cm (poziomy)"},
    ]
    return render_template("index.html", paper_formats=paper_formats)


@app.route("/maps/<path:filename>")
def serve_map(filename: str):
    """Serwuje wygenerowane mapy zarówno lokalnie, jak i na Vercel."""
    return send_from_directory(str(MAP_STORAGE_DIR), filename, mimetype="image/png")


@app.post("/api/generate")
def generate_map() -> Any:
    if request.is_json:
        payload: Dict[str, Any] = request.get_json(force=True) or {}
    else:
        payload = request.form.to_dict(flat=True)

    route, warnings, options, error_response = _prepare_generation(payload)
    if error_response is not None:
        message, status = error_response
        return jsonify({"success": False, "error": message}), status

    preview_filename = f"map_preview_{uuid4().hex}.png"
    map_info = _create_map(
        route,
        options,
        overrides=load_overrides(),
        render_labels=False,
        output_filename=preview_filename,
    )

    response = {
        "success": True,
        "warnings": warnings,
        "cities": [item["name"] for item in route],
        "map": map_info,
    }
    return jsonify(response), 201


@app.post("/api/labels/nudge")
def nudge_label() -> Any:
    return jsonify({"success": False, "error": "Edycja etykiet wyłączona."}), 410


@app.post("/api/labels/apply")
def apply_labels() -> Any:
    data = request.get_json(force=True) or {}
    labels = data.get("labels") or []
    payload = data.get("payload") or {}
    hidden_labels_raw = data.get("hidden_labels") or []
    hidden_labels_set = set(hidden_labels_raw) if isinstance(hidden_labels_raw, list) else set()

    route, warnings, options, error_response = _prepare_generation(payload)
    if error_response is not None:
        message, status = error_response
        return jsonify({"success": False, "error": message}), status

    overrides = load_overrides()
    try:
        for entry in labels:
            city = entry.get("city")
            if not city:
                continue
            # Save offsets relative to anchor
            dx = float(entry.get("dx", 0.0))
            dy = float(entry.get("dy", 0.0))
            overrides = set_override(city, dx, dy)

        if data.get("final"):
            final_filename = f"map_final_{uuid4().hex}.png"
            map_info = _create_map(
                route,
                options,
                overrides,
                render_labels=True,
                output_filename=final_filename,
                hidden_labels=hidden_labels_set,
            )
        else:
            preview_filename = f"map_preview_{uuid4().hex}.png"
            map_info = _create_map(
                route,
                options,
                overrides,
                render_labels=False,
                output_filename=preview_filename,
                hidden_labels=hidden_labels_set,
            )

            final_filename = f"map_final_{uuid4().hex}.png"
            final_map_info = _create_map(
                route,
                options,
                overrides,
                render_labels=True,
                output_filename=final_filename,
                hidden_labels=hidden_labels_set,
            )
            map_info["finalDownload"] = final_map_info
            for key in ("figure", "axes", "bounds", "style", "labels", "paper", "paper_format", "paper_label", "paper_orientation"):
                map_info[key] = final_map_info.get(key, map_info.get(key))
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Label apply failed")
        return jsonify({
            "success": False,
            "error": "Nie udało się zapisać etykiet (szczegóły w konsoli)."
        }), 500

    response = {
        "success": True,
        "warnings": warnings,
        "cities": [item["name"] for item in route],
        "map": map_info,
    }
    return jsonify(response), 200


def _prepare_generation(payload: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[str], Dict[str, Any], Optional[tuple[str, int]]]:
    cities = _normalize_cities(payload.get("cities", []))
    if not cities:
        return [], [], {}, ("Podaj co najmniej jedno miasto.", 400)

    background = payload.get("background") or None
    font_family = payload.get("font_family") or payload.get("font") or None
    font_color = payload.get("font_color") or None
    paper_format = payload.get("paper_format") or payload.get("paper") or None
    if isinstance(paper_format, str) and paper_format.strip():
        paper_format = paper_format.strip().upper()
    else:
        paper_format = None

    dpi_raw = payload.get("dpi")
    dpi_value: Optional[int] = None
    if dpi_raw not in (None, ""):
        try:
            dpi_value = int(dpi_raw)
        except (TypeError, ValueError):
            return [], [], {}, ("DPI musi być liczbą całkowitą.", 400)

    show_borders = _parse_bool(payload.get("show_borders") or payload.get("borders"))
    line_style = payload.get("line_style") or payload.get("lineStyle") or "dashed"
    line_color = payload.get("line_color") or payload.get("lineColor") or "#f2f4ff"
    point_style = payload.get("point_style") or payload.get("pointStyle") or "circle"
    point_color = payload.get("point_color") or payload.get("pointColor") or "#f2f4ff"

    line_width_raw = payload.get("line_width") or payload.get("lineWidth")
    line_width: Optional[float] = None
    if line_width_raw not in (None, ""):
        try:
            line_width = float(line_width_raw)
        except (TypeError, ValueError):
            return [], [], {}, ("Szerokość linii musi być liczbą.", 400)

    point_size_raw = payload.get("point_size") or payload.get("pointSize")
    point_size: Optional[float] = None
    if point_size_raw not in (None, ""):
        try:
            point_size = float(point_size_raw)
        except (TypeError, ValueError):
            return [], [], {}, ("Rozmiar punktów musi być liczbą.", 400)

    title_text = payload.get("title") or payload.get("title_text")
    footer_left_text = payload.get("footer_left") or payload.get("footerLeft")
    footer_right_text = payload.get("footer_right") or payload.get("footerRight")
    text_font = payload.get("text_font") or payload.get("textFont")

    signature_enabled = _parse_bool(payload.get("signature_enabled"))
    signature_path = payload.get("signature_path") or None
    if signature_enabled and not signature_path:
        signature_path = "static/signature/signature.png"
    signature_position_raw = payload.get("signature_position") or "bottom_right"
    signature_position = str(signature_position_raw).strip().lower() if signature_position_raw else "bottom_right"
    allowed_positions = {"bottom_right", "bottom_left", "top_right", "top_left", "bottom_center", "top_center"}
    if signature_position not in allowed_positions:
        signature_position = "bottom_right"
    signature_scale_raw = payload.get("signature_scale")
    signature_scale: Optional[float] = None
    if signature_scale_raw not in (None, ""):
        try:
            signature_scale_value = float(signature_scale_raw)
        except (TypeError, ValueError):
            return [], [], {}, ("Skala podpisu musi być liczbą.", 400)
        signature_scale_value = max(2.0, min(signature_scale_value, 50.0))
        signature_scale = signature_scale_value / 100.0

    merge_bidirectional_routes = _parse_bool(payload.get("merge_bidirectional_routes"))

    route, warnings = _build_route(cities)
    if not route:
        return [], [], {}, ("Brak miast z poprawnymi współrzędnymi.", 400)

    options = {
        "background_color": background or "#0a3dbb",
        "font_family": font_family or "Helvetica",
        "font_color": font_color or "#ffffff",
        "show_borders": show_borders,
        "paper_format": paper_format,
        "dpi": dpi_value or 300,
        "line_style": line_style,
        "line_color": line_color,
        "line_width": line_width,
        "point_style": point_style,
        "point_color": point_color,
        "point_size": point_size,
        "title_text": title_text,
        "footer_left_text": footer_left_text,
        "footer_right_text": footer_right_text,
        "text_font_family": text_font,
        "signature_enabled": signature_enabled,
        "signature_path": signature_path,
        "signature_position": signature_position,
        "signature_scale": signature_scale,
        "merge_bidirectional_routes": merge_bidirectional_routes,
    }

    return route, warnings, options, None


def _create_map(
    route: List[Dict[str, Any]],
    options: Dict[str, Any],
    overrides: Optional[Dict[str, Dict[str, float]]] = None,
    render_labels: bool = False,
    output_filename: Optional[str] = None,
    hidden_labels: Optional[set] = None,
) -> Dict[str, Any]:
    filename = output_filename or f"map_{uuid4().hex}.png"
    output_path = MAP_STORAGE_DIR / filename

    paper_format_raw = options.get("paper_format")
    paper_format = paper_format_raw.strip().upper() if isinstance(paper_format_raw, str) else None
    generator_kwargs = dict(options)
    signature_path_opt = generator_kwargs.get("signature_path")
    if signature_path_opt:
        sig_path = Path(signature_path_opt)
        if not sig_path.is_absolute():
            sig_path = (BASE_DIR / signature_path_opt).resolve()
        generator_kwargs["signature_path"] = str(sig_path)
    signature_scale_opt = generator_kwargs.get("signature_scale")
    if signature_scale_opt is None and generator_kwargs.get("signature_enabled"):
        generator_kwargs["signature_scale"] = None
    overrides_payload = overrides or {}
    dpi_value = int(options.get("dpi") or 300)

    if paper_format == PosterMapGenerator.FORMAT_ID:
        generator = PosterMapGenerator(**generator_kwargs)
        paper_meta = PosterMapGenerator.paper_metadata(dpi_value)
    elif paper_format == LandscapePosterMapGenerator.FORMAT_ID:
        generator = LandscapePosterMapGenerator(**generator_kwargs)
        paper_meta = LandscapePosterMapGenerator.paper_metadata(dpi_value)
    elif paper_format == LargePosterMapGenerator.FORMAT_ID:
        generator = LargePosterMapGenerator(**generator_kwargs)
        paper_meta = LargePosterMapGenerator.paper_metadata(dpi_value)
    elif paper_format == LandscapeLargePosterMapGenerator.FORMAT_ID:
        generator = LandscapeLargePosterMapGenerator(**generator_kwargs)
        paper_meta = LandscapeLargePosterMapGenerator.paper_metadata(dpi_value)
    elif paper_format == "POSTCARD":
        # Format pocztówki używa klasy bazowej MapGenerator z paper_format
        generator = MapGenerator(**generator_kwargs)
        spec = MapGenerator.PAPER_FORMATS.get("POSTCARD", {})
        paper_meta = {
            "format": "POSTCARD",
            "label": spec.get("label", "Pocztówka 10 × 15 cm"),
            "orientation": "portrait",
            "dpi": dpi_value,
            "width_mm": float(spec.get("width_mm", 100.0)),
            "height_mm": float(spec.get("height_mm", 150.0)),
        }
    else:
        generator_kwargs["paper_format"] = None
        generator = MapGenerator(**generator_kwargs)
        paper_meta = {
            "format": None,
            "label": "Automatycznie",
            "orientation": "auto",
            "dpi": dpi_value,
            "width_mm": None,
            "height_mm": None,
        }

    hidden_labels_set = hidden_labels or set()
    map_info = generator.generate_map(
        route,
        str(output_path),
        label_overrides=overrides_payload,
        render_labels=render_labels,
        hidden_labels=hidden_labels_set,
    )

    map_info["paper"] = paper_meta
    map_info["paper_format"] = paper_meta.get("format")
    map_info["paper_label"] = paper_meta.get("label")
    map_info["paper_orientation"] = paper_meta.get("orientation")
    map_info["mapUrl"] = url_for("serve_map", filename=filename)
    return map_info


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)
