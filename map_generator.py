"""
Moduł generowania minimalistycznej mapy z trasą.
"""
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure matplotlib cache directory for Vercel (must be before importing matplotlib)
if os.environ.get("VERCEL") == "1":
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import requests
from matplotlib.collections import PolyCollection
from PIL import Image
try:
    from adjustText import adjust_text  # type: ignore
    _ADJUST_TEXT_AVAILABLE = True
except Exception:
    _ADJUST_TEXT_AVAILABLE = False


BASE_DIR = Path(__file__).resolve().parent


class MapGenerator:
    """Generuje minimalistyczną mapę z połączeniami między miejscami."""

    MM_PER_INCH = 25.4
    PAPER_FORMATS: Dict[str, Dict[str, Any]] = {
        "A4": {
            "label": "A4 (210 × 297 mm)",
            "width_mm": 210.0,
            "height_mm": 297.0,
        },
        "A3": {
            "label": "A3 (297 × 420 mm)",
            "width_mm": 297.0,
            "height_mm": 420.0,
        },
        "POSTER_50X70": {
            "label": "Plakat 50 × 70 cm",
            "width_mm": 500.0,
            "height_mm": 700.0,
        },
        "POSTER_70X50": {
            "label": "Plakat 70 × 50 cm",
            "width_mm": 700.0,
            "height_mm": 500.0,
        },
        "POSTER_60X100": {
            "label": "Plakat 60 × 100 cm",
            "width_mm": 600.0,
            "height_mm": 1000.0,
        },
        "POSTER_100X60": {
            "label": "Plakat 100 × 60 cm",
            "width_mm": 1000.0,
            "height_mm": 600.0,
        },
        "SQUARE": {
            "label": "Kwadrat 1 : 1 (50 × 50 cm)",
            "width_mm": 500.0,
            "height_mm": 500.0,
        },
        "RECTANGLE_3X2": {
            "label": "Prostokąt 3 : 2 (60 × 40 cm)",
            "width_mm": 600.0,
            "height_mm": 400.0,
        },
        "POSTCARD": {
            "label": "Pocztówka 10 × 15 cm (4 × 6 cali)",
            "width_mm": 100.0,
            "height_mm": 150.0,
        },
    }

    def __init__(
        self,
        figsize: Tuple[int, int] = (12, 8),
        min_margin_deg: float = 1.0,
        max_margin_factor: float = 0.15,
        background_color: str = "#0a3dbb",
        font_family: str = "Helvetica",
        font_color: str = "#ffffff",
        curve_strength: float = 0.25,
        show_borders: bool = False,
        border_edgecolor: str = "#c2c2c2",
        border_linewidth: float = 0.6,
        border_alpha: float = 0.6,
        paper_format: Optional[str] = None,
        dpi: int = 300,
        line_style: str = "dashed",
        line_color: str = "#f2f4ff",
        line_width: Optional[float] = None,
        point_style: str = "circle",
        point_color: str = "#f2f4ff",
        point_size: Optional[float] = None,
        title_text: Optional[str] = None,
        footer_left_text: Optional[str] = None,
        footer_right_text: Optional[str] = None,
        footer_font_size: Optional[float] = None,
        text_font_family: Optional[str] = None,
        signature_enabled: bool = False,
        signature_path: Optional[str] = None,
        signature_position: str = "bottom_right",
        signature_scale: Optional[float] = None,
        merge_bidirectional_routes: bool = False,
        lock_paper_orientation: bool = False,
    ):
        self.figsize = figsize
        self.min_margin_deg = min_margin_deg
        self.max_margin_factor = max_margin_factor
        self.background_color = background_color
        self.font_family = font_family
        self.font_color = font_color
        self.curve_strength = curve_strength
        self.show_borders = show_borders
        self.border_edgecolor = border_edgecolor
        self.border_linewidth = border_linewidth
        self.border_alpha = border_alpha
        self.paper_format = paper_format.upper() if paper_format else None
        self.dpi = dpi
        self.margin_factor = max_margin_factor
        self.line_style = line_style
        self.line_color = line_color
        self.line_width = line_width
        self.point_style = point_style
        self.point_color = point_color
        self.point_size = point_size
        self.title_text = title_text
        self.footer_left_text = footer_left_text
        self.footer_right_text = footer_right_text
        self.footer_font_size = footer_font_size
        self.text_font_family = text_font_family
        self.signature_enabled = bool(signature_enabled)
        if signature_path:
            self.signature_path = Path(signature_path).resolve()
        else:
            default_sig = BASE_DIR / "static" / "signature" / "signature.png"
            self.signature_path = default_sig if default_sig.exists() else None
        pos_normalized = (signature_position or "bottom_right").lower()
        self.signature_position = pos_normalized
        default_scale = 0.18
        scale_value = signature_scale if signature_scale is not None else default_scale
        self.signature_scale = max(0.02, min(scale_value, 0.5))
        self.signature_margin_fraction = 0.06
        self.merge_bidirectional_routes = bool(merge_bidirectional_routes)
        self.lock_paper_orientation = bool(lock_paper_orientation)

        self._border_shapes_cache: Optional[List[np.ndarray]] = None
        self._border_error: Optional[Exception] = None

    @classmethod
    def available_paper_formats(cls) -> List[Dict[str, str]]:
        """Zwraca listę dostępnych formatów papieru wraz z etykietami."""
        return [
            {"id": key, "label": spec.get("label", key)}
            for key, spec in cls.PAPER_FORMATS.items()
        ]
    
    def generate_map(
        self,
        route: List[Dict],
        output_file: Optional[str] = None,
        label_overrides: Optional[Dict[str, Dict[str, float]]] = None,
        render_labels: bool = True,
        hidden_labels: Optional[set] = None,
    ) -> Dict[str, Any]:
        """
        Generuje mapę na podstawie trasy.
        
        Args:
            route: Lista słowników z kluczami 'name', 'latitude', 'longitude'
            output_file: Opcjonalna ścieżka do zapisania mapy (jeśli None, wyświetla)
            hidden_labels: Zbiór nazw miast do ukrycia
        """
        # Filtruj miasta z poprawnymi współrzędnymi
        valid_cities = [
            city for city in route 
            if city.get("latitude") is not None and city.get("longitude") is not None
        ]
        
        if len(valid_cities) < 1:
            print("Brak miast z poprawnymi współrzędnymi do wyświetlenia.")
            return
        
        # Wyciągnij współrzędne
        lats = [city["latitude"] for city in valid_cities]
        lons = [city["longitude"] for city in valid_cities]
        names = [city["name"] for city in valid_cities]
        
        # Oblicz zakresy i marginesy, aby zdecydować o orientacji papieru
        lat_span = max(lats) - min(lats) if len(lats) > 1 else 0.0
        lon_span = max(lons) - min(lons) if len(lons) > 1 else 0.0

        # Add margins around the route to make room for labels
        # Dla pocztówek zmniejsz minimalny margines, aby uzyskać większy zoom
        min_margin = self.min_margin_deg * 0.5 if self.paper_format == "POSTCARD" else self.min_margin_deg
        margin_lat = max(min_margin, lat_span * self._margin_factor_lat(lat_span))
        margin_lon = max(min_margin, lon_span * self._margin_factor_lon(lon_span))

        lat_min = min(lats) - margin_lat
        lat_max = max(lats) + margin_lat
        lon_min = min(lons) - margin_lon
        lon_max = max(lons) + margin_lon

        # Dobierz rozmiar figury (format papieru lub domyślne)
        figsize = self.figsize
        if self.paper_format:
            paper_spec = self.PAPER_FORMATS.get(self.paper_format)
            if paper_spec:
                width_mm = float(paper_spec.get("width_mm", 0.0))
                height_mm = float(paper_spec.get("height_mm", 0.0))
                if width_mm > 0.0 and height_mm > 0.0:
                    width_in = width_mm / self.MM_PER_INCH
                    height_in = height_mm / self.MM_PER_INCH
                    if (not self.lock_paper_orientation) and lon_span > lat_span and width_in < height_in:
                        width_in, height_in = height_in, width_in
                    elif (not self.lock_paper_orientation) and lon_span < lat_span and width_in > height_in:
                        width_in, height_in = height_in, width_in
                    figsize = (width_in, height_in)
            else:
                print(
                    f"⚠ Nieznany format papieru '{self.paper_format}'. "
                    "Używam domyślnego rozmiaru."
                )

        # Utwórz figurę
        fig, ax = plt.subplots(figsize=figsize, dpi=self.dpi)
        fig.patch.set_facecolor(self.background_color)
        ax.set_facecolor(self.background_color)
        ax.set_aspect('equal', adjustable='box')
        
        # Rysuj połączenia między kolejnymi miastami jako delikatnie zakrzywione linie
        if len(valid_cities) > 1:
            segment_keys = [
                (names[i], names[i + 1], i) for i in range(len(valid_cities) - 1)
            ]
            if self.merge_bidirectional_routes:
                occurrence_tracker = defaultdict(int)
            else:
                occurrence_tracker = defaultdict(int)
                pair_counts = Counter((key[0], key[1]) for key in segment_keys)

            for idx, (start_name, end_name, i) in enumerate(segment_keys):
                if self.merge_bidirectional_routes:
                    canonical = tuple(sorted((start_name, end_name)))
                    occurrence_idx = occurrence_tracker[canonical]
                    occurrence_tracker[canonical] += 1
                    if occurrence_idx > 0:
                        continue
                    total_occurrences = 1
                else:
                    occurrence_idx = occurrence_tracker[(start_name, end_name)]
                    occurrence_tracker[(start_name, end_name)] += 1
                    total_occurrences = pair_counts[(start_name, end_name)]

                curve = self._build_curve(
                    (lons[i], lats[i]),
                    (lons[i + 1], lats[i + 1]),
                    occurrence_idx=occurrence_idx,
                    total_occurrences=total_occurrences,
                )
                base_linewidth = (
                    self.line_width
                    if self.line_width is not None
                    else (2.2 if total_occurrences == 1 else 1.6)
                )
                linestyle, marker_line = self._resolve_line_style(self.line_style)
                line_kwargs = {
                    "color": self.line_color,
                    "alpha": 0.85,
                    "label": "Trasa" if idx == 0 else None,
                }

                if marker_line:
                    # Użyj markevery jako ułamka, aby zapewnić równomierne rozmieszczenie markerów
                    # niezależnie od długości linii. Mniejsza wartość = gęstsze rozmieszczenie.
                    markevery_value = 0.01  # Gęste rozmieszczenie - marker co 1% długości linii
                    line_kwargs.update(
                        {
                            "linestyle": "None",
                            "marker": marker_line,
                            "markersize": self.line_width or 5.0,
                            "markerfacecolor": self.line_color,
                            "markeredgecolor": self.line_color,
                            "markeredgewidth": 0.0,
                            "markevery": markevery_value,  # Równomierne rozmieszczenie niezależnie od długości
                        }
                    )
                else:
                    line_kwargs.update(
                        {
                            "linestyle": linestyle,
                            "linewidth": base_linewidth,
                        }
                    )

                ax.plot(
                    curve[:, 0],
                    curve[:, 1],
                    **line_kwargs,
                )
        
        # Rysuj punkty miast
        ax.scatter(
            lons,
            lats,
            c=self.point_color,
            edgecolors='none',
            s=self.point_size or 50,
            marker=self._resolve_point_marker(self.point_style),
            zorder=5,
            label='Miasta'
        )
        
        hidden_labels_set = hidden_labels or set()
        unique_cities: List[Dict] = []
        seen_names: set[str] = set()
        for city in route:
            city_name = city.get("name", "")
            # Skip hidden labels
            if city_name in hidden_labels_set:
                continue
            if city_name not in seen_names:
                seen_names.add(city_name)
                unique_cities.append(city)

        # Calculate a small vertical offset based ONLY on latitude span so that
        # long poziome trasy nie powodują „odjechania” etykiet w pionie.
        lon_span_raw = max(lons) - min(lons) if len(lons) > 1 else 0.0
        lat_span_raw = max(lats) - min(lats) if len(lats) > 1 else 0.0
        # Minimalny offset: ok. 0.1% wysokości mapy – etykiety bardzo blisko punktów.
        label_offset_y = lat_span_raw * 0.001
        if label_offset_y == 0.0:
            label_offset_y = 0.001  # fallback dla pojedynczego punktu
        
        texts: List[plt.Text] = []
        for city in unique_cities:
            lon, lat = city["longitude"], city["latitude"]
            ov = (label_overrides or {}).get(city["name"]) if label_overrides else None
            if ov is None:
                # No override: place label very close above point
                target_x = lon
                target_y = lat + label_offset_y
            else:
                # Override exists: apply dx/dy offset
                target_x = lon + float(ov.get("dx", 0.0))
                target_y = lat + float(ov.get("dy", 0.0))

            # Don't clamp - let labels be positioned naturally, even if slightly outside bounds
            # The map margins should be sufficient to keep labels visible

            label_font_pt = self._label_font_size_pt()
            
            # Użyj czcionki z fallbackiem na DejaVu Sans dla polskich znaków
            # DejaVu Sans ma pełne wsparcie dla Unicode i polskich znaków diakrytycznych
            # Zawsze używaj DejaVu Sans dla etykiet miast, aby uniknąć problemów z polskimi znakami
            font_family_with_fallback = "DejaVu Sans"
            
            text = ax.text(
                target_x,
                target_y,
                city["name"],
                ha="center",
                va="bottom",
                fontsize=label_font_pt,
                fontfamily=font_family_with_fallback,
                color=self.font_color,
                zorder=8,
                clip_on=False,  # Don't clip labels - allow them to be visible
                bbox=None,  # Wyłącz bbox - nie chcemy prostokątów przy etykietach
            )
            # Upewnij się, że nie ma żadnego tła ani ramki
            text.set_bbox(None)
            text.set_visible(render_labels)
            texts.append(text)

        # Jeśli potrzebujemy bardziej zaawansowanego układania podpisów, można
        # ponownie włączyć adjust_text, ale teraz zostawiamy podstawowy offset,
        # żeby napisy pozostały blisko swoich punktów.

        # Usuń opisy osi i siatki, aby zachować minimalistyczny wygląd.
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        
        # Remove spines (black frame around axes) - we don't want this
        for spine in ax.spines.values():
            spine.set_visible(False)

        legend = ax.get_legend()
        if legend:
            legend.remove()
        
        # Dostosuj zakres osi tak, by objąć całą trasę z marginesem
        if self.show_borders:
            self._draw_country_borders(ax)

        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        
        # Remove all margins so axes fill the entire figure BEFORE calculating bbox
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        axes_left, axes_bottom, axes_width, axes_height = self._axes_box()
        ax.set_position([axes_left, axes_bottom, axes_width, axes_height])
        
        # Add poster texts (title and footers) if provided
        self._render_text_overlays(ax)

        # Build placed label metadata from current text positions (with overrides applied)
        # Do this AFTER setting margins to zero so bbox is accurate
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        fig_width_px, fig_height_px = fig.canvas.get_width_height()
        
        # Get axes bounding box in figure pixel coordinates
        axes_bbox = ax.get_window_extent(renderer=renderer)

        lon_span = max(lon_max - lon_min, 1e-9)
        lat_span = max(lat_max - lat_min, 1e-9)
        placed_labels = []
        for text, city in zip(texts, unique_cities):
            pos_x, pos_y = text.get_position()
            # Convert data coordinates (lon/lat) to axes relative (0..1)
            x_rel = float(np.clip((pos_x - lon_min) / lon_span, 0.0, 1.0))
            y_rel = float(np.clip((pos_y - lat_min) / lat_span, 0.0, 1.0))
            placed_labels.append({
                "name": city["name"],
                "x_rel": x_rel,
                "y_rel": y_rel,
                "anchor_lon": float(city["longitude"]),
                "anchor_lat": float(city["latitude"]),
                "locked": (label_overrides or {}).get(city["name"]) is not None,
                "dx": float(pos_x - city["longitude"]),
                "dy": float(pos_y - city["latitude"]),
            })
        
        signature_meta: Optional[Dict[str, Any]] = None
        # Zapisz lub wyświetl
        if output_file:
            # Save without bbox_inches='tight' to avoid white margins
            plt.savefig(output_file, dpi=self.dpi, pad_inches=0, facecolor=self.background_color, edgecolor='none')
            signature_meta = self._apply_signature(output_file)
            print(f"Mapa zapisana do: {output_file}")
        else:
            plt.show()
        
        plt.close()
 
        label_font_px = float(self._label_font_size_pt() * self.dpi / 72.0)
 
        map_info: Dict[str, Any] = {
            "labels": placed_labels,
            "figure": {
                "width_px": int(fig_width_px),
                "height_px": int(fig_height_px),
            },
            "axes": {
                "x0": float(axes_bbox.x0),
                "y0": float(axes_bbox.y0),
                "x1": float(axes_bbox.x1),
                "y1": float(axes_bbox.y1),
                "width": float(axes_bbox.width),
                "height": float(axes_bbox.height),
            },
            "bounds": {
                "lon_min": float(lon_min),
                "lon_max": float(lon_max),
                "lat_min": float(lat_min),
                "lat_max": float(lat_max),
            },
            "style": {
                "font_family": self.font_family,
                "font_color": self.font_color,
                "label_font_size_pt": float(self._label_font_size_pt()),
                "label_font_size_px": label_font_px,
                "background_color": self.background_color,
            },
        }
        if signature_meta:
            map_info["signature"] = signature_meta
            warning = signature_meta.get("warning")
            if warning:
                map_info.setdefault("warnings", []).append(warning)

        return map_info

    def _label_font_size_pt(self) -> float:
        # Dla pocztówek użyj mniejszej czcionki
        if self.paper_format == "POSTCARD":
            return 8.0  # Mniejsza czcionka dla pocztówek (10x15 cm)
        return 11.0

    def _margin_factor_lat(self, lat_span: float) -> float:
        # Dla pocztówek zmniejsz marginesy geograficzne (większy zoom)
        if self.paper_format == "POSTCARD":
            return self.margin_factor * 0.5  # 50% mniejsze marginesy = większy zoom
        return self.margin_factor

    def _margin_factor_lon(self, lon_span: float) -> float:
        # Dla pocztówek zmniejsz marginesy geograficzne (większy zoom)
        if self.paper_format == "POSTCARD":
            return self.margin_factor * 0.5  # 50% mniejsze marginesy = większy zoom
        return self.margin_factor
 
    def _axes_box(self) -> Tuple[float, float, float, float]:
        # Dla pocztówek zwiększ obszar mapy (zmniejsz marginesy wizualne)
        if self.paper_format == "POSTCARD":
            # Mapa zajmuje więcej miejsca - mniejsze marginesy wizualne
            return (0.05, 0.10, 0.90, 0.80)  # Zwiększony obszar mapy
        return (0.0, 0.0, 1.0, 1.0)
 
    def _apply_signature(self, output_file: str) -> Optional[Dict[str, Any]]:
        if not self.signature_enabled or not self.signature_path:
            return None

        sig_path = self.signature_path
        if not sig_path.exists():
            return {
                "enabled": False,
                "warning": f"Nie znaleziono pliku podpisu: {sig_path}",
            }

        try:
            base_image = Image.open(output_file).convert("RGBA")
        except Exception as exc:  # pragma: no cover - ochronnie
            return {
                "enabled": False,
                "warning": f"Nie udało się otworzyć pliku mapy do podpisu: {exc}",
            }

        try:
            signature_image = Image.open(sig_path).convert("RGBA")
        except Exception as exc:  # pragma: no cover
            base_image.close()
            return {
                "enabled": False,
                "warning": f"Nie udało się wczytać podpisu ({sig_path.name}): {exc}",
            }

        base_width, base_height = base_image.size
        scale = self.signature_scale
        target_width = max(1, int(round(base_width * scale)))
        aspect_ratio = signature_image.height / signature_image.width if signature_image.width else 1.0
        target_height = max(1, int(round(target_width * aspect_ratio)))

        resized_signature = signature_image.resize((target_width, target_height), Image.LANCZOS)
        
        # Dla pozycji w rogu użyj minimalnego marginesu, aby podpis był w samym rogu
        corner_margin = 10  # Minimalny margines w pikselach dla rogów (10px)
        corner_margin_right = 5  # Mniejszy margines po prawej stronie - podpis bardziej w prawo
        margin_x = int(round(base_width * self.signature_margin_fraction))
        margin_y = int(round(base_height * self.signature_margin_fraction))

        position = self.signature_position
        
        # Sprawdź czy pozycja jest w rogu (zawiera "left" lub "right" oraz "top" lub "bottom")
        is_corner = ("left" in position or "right" in position) and ("top" in position or "bottom" in position)
        
        if "top" in position:
            # Dla górnych rogów użyj minimalnego marginesu
            dest_y = corner_margin if is_corner else margin_y
        else:
            # Dla dolnych rogów użyj minimalnego marginesu, aby podpis był w samym rogu
            # Przesuń trochę do góry - zwiększ margines od dołu
            bottom_offset = corner_margin + 30 if is_corner else int(round(base_height * 0.03)) + 30
            dest_y = base_height - target_height - bottom_offset if is_corner else base_height - target_height - bottom_offset
            dest_y = max(0, dest_y)

        if "left" in position:
            # Dla lewych rogów użyj minimalnego marginesu
            dest_x = corner_margin if is_corner else margin_x
        elif "center" in position:
            # Przesuń trochę do środka - dokładnie na środek
            dest_x = (base_width - target_width) // 2
        else:  # "right" domyślnie
            # Dla prawych rogów przesuń trochę do środka (w lewo)
            # Zamiast być w samym rogu, przesuń w stronę środka
            offset_from_right = corner_margin_right + 50 if is_corner else margin_x + 50
            dest_x = base_width - target_width - offset_from_right if is_corner else base_width - target_width - offset_from_right

        base_image.alpha_composite(resized_signature, dest=(dest_x, dest_y))
        base_image.convert("RGB").save(output_file, format="PNG")

        base_image.close()
        signature_image.close()

        return {
            "enabled": True,
            "path": str(sig_path),
            "position": position,
            "scale": scale,
            "box": {
                "x": dest_x,
                "y": dest_y,
                "width": target_width,
                "height": target_height,
            },
        }

    def _build_curve(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        occurrence_idx: int = 0,
        total_occurrences: int = 1,
    ) -> np.ndarray:
        """
        Buduje punkty na krzywej Béziera drugiego stopnia między dwoma miastami.
        """
        start_vec = np.array(start, dtype=float)
        end_vec = np.array(end, dtype=float)
        direction = end_vec - start_vec

        if np.allclose(direction, 0):
            return np.vstack([start_vec, end_vec])

        mid_point = (start_vec + end_vec) / 2.0
        perpendicular = np.array([-direction[1], direction[0]], dtype=float)
        norm = np.linalg.norm(perpendicular)
        if norm != 0:
            perpendicular /= norm
        base_offset = self.curve_strength * np.linalg.norm(direction)
        if total_occurrences > 1:
            offset_step = 0.18 * base_offset
            offset_multiplier = (
                occurrence_idx - (total_occurrences - 1) / 2
            )
            base_offset += offset_multiplier * offset_step
        control_point = mid_point + perpendicular * base_offset

        t_values = np.linspace(0, 1, 50)
        curve_points = (
            (1 - t_values)[:, None] ** 2 * start_vec
            + 2 * (1 - t_values)[:, None] * t_values[:, None] * control_point
            + t_values[:, None] ** 2 * end_vec
        )
        return curve_points

    @staticmethod
    def _resolve_line_style(style: str) -> Tuple[str, Optional[str]]:
        normalized = (style or "").lower()
        mapping = {
            "solid": ("-", None),
            "dashed": ("--", None),
            "dotted": (":", None),  # Styl linii kropkowanej matplotlib - równomierne rozmieszczenie niezależnie od długości
            "dashdot": ("-.", None),
            "dot": ("None", "o"),
            "dots": ("None", "o"),
            "points": ("None", "."),
        }
        return mapping.get(normalized, ("--", None))

    @staticmethod
    def _resolve_point_marker(style: str) -> str:
        normalized = (style or "").lower().strip()
        mapping = {
            "circle": "o",
            "square": "s",
            "triangle": "^",
            "diamond": "D",
            "cross": "X",
            "star": "*",
        }
        # Zawsze zwracaj kółko jako domyślne, nawet jeśli styl nie jest rozpoznany
        return mapping.get(normalized, "o")

    def _render_text_overlays(self, ax: plt.Axes) -> None:
        """Umieszcza napisy tytułu i podpisów dolnych."""
        font_family = self.text_font_family or self.font_family
        font_color = self.font_color

        if self.title_text:
            ax.text(
                0.5,
                0.97,
                self.title_text,
                ha='center',
                va='top',
                fontsize=26,
                fontfamily=font_family,
                color=font_color,
                fontweight='bold',
                transform=ax.transAxes,
            )

        # Dla pocztówek przesuń napisy bardziej na boki i niżej
        if self.paper_format == "POSTCARD":
            footer_x_left = 0.0  # Bardziej na lewo - przy samej krawędzi
            footer_x_right = 1.0  # Bardziej na prawo - przy samej krawędzi
            footer_y = 0.02  # Niżej (z 0.05)
        else:
            footer_x_left = 0.02
            footer_x_right = 0.98
            footer_y = 0.05

        footer_font_size = self.footer_font_size if self.footer_font_size is not None else 14
        
        if self.footer_left_text:
            self._render_footer_text(
                ax,
                self.footer_left_text,
                footer_x_left,
                footer_y,
                self._detect_footer_layout(self.footer_left_text),
                'left',
                font_family,
                font_color,
                footer_font_size,
                ax.transAxes,
            )

        if self.footer_right_text:
            self._render_footer_text(
                ax,
                self.footer_right_text,
                footer_x_right,
                footer_y,
                self._detect_footer_layout(self.footer_right_text),
                'right',
                font_family,
                font_color,
                footer_font_size,
                ax.transAxes,
            )

    def _detect_footer_layout(self, text: Optional[str]) -> str:
        """Wykrywa układ stopki na podstawie zawartości tekstu. Enter = pionowy, spacja = poziomy."""
        if not text:
            return "horizontal"
        # Jeśli tekst zawiera znak nowej linii (\n), to układ pionowy
        if '\n' in text:
            return "vertical"
        return "horizontal"

    def _render_footer_text(
        self,
        ax,
        text: str,
        x: float,
        y: float,
        layout: str,
        ha: str,
        font_family: str,
        font_color: str,
        font_size: float,
        transform=None,
    ):
        """Renderuje tekst stopki z obsługą układu poziomego i pionowego (dla ax.text)."""
        if layout == "vertical":
            # Dla układu pionowego, używamy jednego wywołania z linespacing dla lepszego formatowania
            # Zwiększamy rozmiar czcionki dla układu pionowego (o 20%)
            vertical_font_size = font_size * 1.2
            # Renderujemy cały tekst z parametrem linespacing dla lepszych odstępów między liniami
            ax.text(
                x,
                y,
                text,
                ha=ha,
                va='bottom',
                fontsize=vertical_font_size,
                fontfamily=font_family,
                color=font_color,
                transform=transform or ax.transAxes,
                linespacing=1.6,  # Zwiększa odstęp między liniami dla lepszej czytelności
            )
        else:
            # Dla układu poziomego, renderujemy tekst normalnie
            ax.text(
                x,
                y,
                text,
                ha=ha,
                va='bottom',
                fontsize=font_size,
                fontfamily=font_family,
                color=font_color,
                transform=transform or ax.transAxes,
            )

    def _render_footer_text_fig(
        self,
        fig,
        text: str,
        x: float,
        y: float,
        layout: str,
        ha: str,
        font_family: str,
        font_color: str,
        font_size: float,
    ):
        """Renderuje tekst stopki z obsługą układu poziomego i pionowego (dla fig.text)."""
        if layout == "vertical":
            # Dla układu pionowego, używamy jednego wywołania z linespacing dla lepszego formatowania
            # Zwiększamy rozmiar czcionki dla układu pionowego (o 20%)
            vertical_font_size = font_size * 1.2
            # Renderujemy cały tekst z parametrem linespacing dla lepszych odstępów między liniami
            fig.text(
                x,
                y,
                text,
                ha=ha,
                va='bottom',
                fontsize=vertical_font_size,
                fontfamily=font_family,
                color=font_color,
                linespacing=1.6,  # Zwiększa odstęp między liniami dla lepszej czytelności
            )
        else:
            # Dla układu poziomego, renderujemy tekst normalnie
            fig.text(
                x,
                y,
                text,
                ha=ha,
                va='bottom',
                fontsize=font_size,
                fontfamily=font_family,
                color=font_color,
            )

    @staticmethod
    def _closest_point_on_segment(
        point: np.ndarray,
        seg_start: np.ndarray,
        seg_end: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """Zwraca punkt na odcinku najbliższy do zadanego punktu oraz odległość."""
        seg_vec = seg_end - seg_start
        seg_len_sq = np.dot(seg_vec, seg_vec)
        if seg_len_sq == 0:
            projection = seg_start
        else:
            t = np.dot(point - seg_start, seg_vec) / seg_len_sq
            t = np.clip(t, 0.0, 1.0)
            projection = seg_start + t * seg_vec
        distance = np.linalg.norm(point - projection)
        return projection, distance

    @staticmethod
    def _cardinal_direction(from_city: Dict, to_city: Dict) -> Optional[str]:
        if from_city is None or to_city is None:
            return None
        dx = to_city["longitude"] - from_city["longitude"]
        dy = to_city["latitude"] - from_city["latitude"]
        if np.allclose([dx, dy], 0.0):
            return None
        if abs(dx) >= abs(dy):
            return "E" if dx > 0 else "W"
        return "N" if dy > 0 else "S"

    def _choose_label_direction(
        self,
        prev_city: Optional[Dict],
        current_city: Dict,
        next_city: Optional[Dict],
    ) -> np.ndarray:
        prev_dir = self._cardinal_direction(prev_city, current_city)
        next_dir = self._cardinal_direction(current_city, next_city)

        cardinal_vectors = {
            "N": np.array([0.0, 1.0]),
            "S": np.array([0.0, -1.0]),
            "E": np.array([1.0, 0.0]),
            "W": np.array([-1.0, 0.0]),
        }

        preferred_order = ["N", "E", "S", "W"]

        def opposite(direction: str) -> str:
            return {"N": "S", "S": "N", "E": "W", "W": "E"}[direction]

        forbidden = set()
        if prev_dir:
            forbidden.add(prev_dir)
        if next_dir:
            forbidden.add(next_dir)
        allowed = [d for d in preferred_order if d not in forbidden]

        if prev_dir and next_dir:
            opp_prev = opposite(prev_dir)
            opp_next = opposite(next_dir)
            priority = [opp_prev, opp_next] + allowed
        elif prev_dir or next_dir:
            base_dir = prev_dir or next_dir
            priority = [opposite(base_dir)] + allowed
        else:
            priority = preferred_order

        for direction in priority:
            vec = cardinal_vectors.get(direction)
            if vec is not None:
                return vec

        return np.array([0.0, 1.0])

    def _get_neighbor_vectors(self, name: str, cities: List[Dict]) -> List[np.ndarray]:
        indices = [idx for idx, city in enumerate(cities) if city["name"] == name]
        if not indices:
            return []

        idx = indices[0]
        current = np.array([cities[idx]["longitude"], cities[idx]["latitude"]], dtype=float)
        vectors: List[np.ndarray] = []

        if idx > 0:
            prev = np.array([cities[idx - 1]["longitude"], cities[idx - 1]["latitude"]], dtype=float)
            vec = current - prev
            if np.linalg.norm(vec) > 0:
                vectors.append(vec / np.linalg.norm(vec))

        if idx < len(cities) - 1:
            nxt = np.array([cities[idx + 1]["longitude"], cities[idx + 1]["latitude"]], dtype=float)
            vec = nxt - current
            if np.linalg.norm(vec) > 0:
                vectors.append(vec / np.linalg.norm(vec))

        return vectors

    @staticmethod
    def _initial_label_direction(neighbour_vectors: List[np.ndarray]) -> np.ndarray:
        if not neighbour_vectors:
            return np.array([0.0, 1.0])

        direction = np.zeros(2, dtype=float)
        for vec in neighbour_vectors:
            direction += -vec

        if np.linalg.norm(direction) == 0:
            return np.array([0.0, 1.0])
        return direction / np.linalg.norm(direction)

    @staticmethod
    def _get_neighbors(name: str, cities: List[Dict]) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Zwraca poprzednie i następne wystąpienie miasta w trasie."""
        indices = [idx for idx, city in enumerate(cities) if city["name"] == name]
        if not indices:
            return None, None

        first_idx = indices[0]
        prev_city = None
        for idx in range(first_idx - 1, -1, -1):
            if cities[idx]["name"] != name:
                prev_city = cities[idx]
                break

        next_city = None
        for idx in range(first_idx + 1, len(cities)):
            if cities[idx]["name"] != name:
                next_city = cities[idx]
                break

        return prev_city, next_city

    def _draw_country_borders(self, ax: plt.Axes) -> None:
        """
        Rysuje granice państw jako delikatne kontury.
        """
        shapes = self._get_border_shapes()
        if not shapes:
            if self._border_error:
                print(
                    "⚠ Nie udało się wczytać granic państw: "
                    f"{self._border_error}"
                )
            return

        collection = PolyCollection(
            shapes,
            facecolor='none',
            edgecolor=self.border_edgecolor,
            linewidth=self.border_linewidth,
            alpha=self.border_alpha,
            zorder=1,
        )
        ax.add_collection(collection)

    def _get_border_shapes(self) -> List[np.ndarray]:
        """
        Pobiera i buforuje współrzędne granic państw z Natural Earth.
        """
        if self._border_shapes_cache is not None:
            return self._border_shapes_cache

        url = (
            "https://raw.githubusercontent.com/nvkelso/"
            "natural-earth-vector/master/geojson/"
            "ne_110m_admin_0_countries.geojson"
        )

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            shapes: List[np.ndarray] = []
            for feature in data.get("features", []):
                geometry = feature.get("geometry")
                if not geometry:
                    continue
                geom_type = geometry.get("type")
                coords = geometry.get("coordinates")
                if not coords:
                    continue
                if geom_type == "Polygon":
                    shapes.extend(self._polygon_to_paths(coords))
                elif geom_type == "MultiPolygon":
                    for polygon in coords:
                        shapes.extend(self._polygon_to_paths(polygon))

            self._border_shapes_cache = shapes
            return shapes

        except Exception as exc:
            self._border_error = exc
            self._border_shapes_cache = []
            return []

    @staticmethod
    def _polygon_to_paths(rings: List[List[List[float]]]) -> List[np.ndarray]:
        """
        Konwertuje współrzędne pierścieni poligonu GeoJSON na tablice NumPy.
        """
        if not rings:
            return []
        outer_ring = np.array(rings[0], dtype=float)
        if outer_ring.ndim != 2 or outer_ring.shape[1] != 2:
            return []
        return [outer_ring]

    def _place_labels_with_collision_avoidance(
        self,
        texts: List[plt.Text],
        unique_cities: List[Dict],
        route_cities: List[Dict],
        ax: plt.Axes,
        min_line_distance_px: float = 32.0,
        min_label_distance_px: float = 30.0,
        max_iterations: int = 180,
        max_anchor_distance_px: float = 140.0,
        label_overrides: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[Dict[str, Any]]:
        if not texts or not unique_cities:
            return []

        overrides = label_overrides or {}

        figure = ax.figure
        canvas = figure.canvas
        if not hasattr(canvas, "get_renderer"):
            canvas.draw()
        renderer = canvas.get_renderer()

        segments = [
            (
                np.array([route_cities[i]["longitude"], route_cities[i]["latitude"]], dtype=float),
                np.array([route_cities[i + 1]["longitude"], route_cities[i + 1]["latitude"]], dtype=float),
            )
            for i in range(len(route_cities) - 1)
        ] if len(route_cities) > 1 else []

        def data_to_px(point: np.ndarray) -> np.ndarray:
            return ax.transData.transform(point)

        def px_to_data(point_px: np.ndarray) -> np.ndarray:
            return ax.transData.inverted().transform(point_px)

        label_entries: List[Dict] = []
        for text, city in zip(texts, unique_cities):
            anchor = np.array([city["longitude"], city["latitude"]], dtype=float)
            override = overrides.get(city["name"])
            if override:
                position_data = np.array([
                    anchor[0] + override.get("dx", 0.0),
                    anchor[1] + override.get("dy", 0.0),
                ], dtype=float)
                locked = True
            else:
                position_data = np.array(text.get_position(), dtype=float)
                locked = False

            anchor_px = data_to_px(anchor)
            position_px = data_to_px(position_data)
            bbox = text.get_window_extent(renderer=renderer)
            label_entries.append({
                "text": text,
                "anchor_data": anchor,
                "anchor_px": anchor_px,
                "position_px": position_px,
                "half_width_px": max(bbox.width / 2.0, 20.0),
                "half_height_px": max(bbox.height / 2.0, 12.0),
                "locked": locked,
            })

        def label_bbox(entry: Dict) -> Tuple[float, float, float, float]:
            center = entry["position_px"]
            return (
                center[0] - entry["half_width_px"],
                center[0] + entry["half_width_px"],
                center[1] - entry["half_height_px"],
                center[1] + entry["half_height_px"],
            )

        for _ in range(max_iterations):
            moved = False
            for entry in label_entries:
                if entry.get("locked"):
                    continue

                pos_px = entry["position_px"]
                shift = np.zeros(2, dtype=float)

                for seg_start, seg_end in segments:
                    start_px = data_to_px(seg_start)
                    end_px = data_to_px(seg_end)
                    projection, distance = self._closest_point_on_segment_px(pos_px, start_px, end_px)
                    if distance < min_line_distance_px:
                        direction = pos_px - projection
                        if np.allclose(direction, 0.0):
                            seg_vec = end_px - start_px
                            direction = np.array([-seg_vec[1], seg_vec[0]], dtype=float)
                        if np.allclose(direction, 0.0):
                            direction = np.array([0.0, 1.0])
                        direction /= np.linalg.norm(direction)
                        shift += direction * (min_line_distance_px - distance + 1.0)

                entry_box = label_bbox(entry)
                for other in label_entries:
                    if other is entry:
                        continue
                    other_box = label_bbox(other)
                    if self._boxes_overlap(entry_box, other_box, padding=min_label_distance_px):
                        delta = pos_px - other["position_px"]
                        if np.allclose(delta, 0.0):
                            delta = np.array([0.0, 1.0])
                        delta /= np.linalg.norm(delta)
                        shift += delta * (min_label_distance_px / 2)

                shift += (pos_px - entry["anchor_px"]) * -0.03

                if np.linalg.norm(shift) > 0.4:
                    new_pos = pos_px + shift
                    if np.linalg.norm(new_pos - entry["anchor_px"]) > max_anchor_distance_px:
                        new_pos = entry["anchor_px"] + (new_pos - entry["anchor_px"]) * (
                            max_anchor_distance_px / np.linalg.norm(new_pos - entry["anchor_px"])
                        )
                    entry["position_px"] = new_pos
                    moved = True

            if not moved:
                break

        for entry in label_entries:
            if entry.get("locked"):
                entry["final_position_data"] = px_to_data(entry["position_px"])
                continue
            pos_data = px_to_data(entry["position_px"])
            entry["text"].set_position(pos_data)
            entry["final_position_data"] = pos_data

        result: List[Dict[str, Any]] = []
        for entry, city in zip(label_entries, unique_cities):
            result.append({
                "name": entry["text"].get_text(),
                "anchor_data": entry["anchor_data"],
                "position_data": entry["final_position_data"],
                "anchor_px": entry["anchor_px"],
                "position_px": entry["position_px"],
                "locked": entry.get("locked", False),
            })

        return result

    @staticmethod
    def _closest_point_on_segment_px(
        point_px: np.ndarray,
        seg_start_px: np.ndarray,
        seg_end_px: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        seg_vec = seg_end_px - seg_start_px
        seg_len_sq = np.dot(seg_vec, seg_vec)
        if seg_len_sq == 0:
            projection = seg_start_px
        else:
            t = np.dot(point_px - seg_start_px, seg_vec) / seg_len_sq
            t = np.clip(t, 0.0, 1.0)
            projection = seg_start_px + t * seg_vec
        distance = np.linalg.norm(point_px - projection)
        return projection, distance

    @staticmethod
    def _boxes_overlap(
        box_a: Tuple[float, float, float, float],
        box_b: Tuple[float, float, float, float],
        padding: float,
    ) -> bool:
        ax0, ax1, ay0, ay1 = box_a
        bx0, bx1, by0, by1 = box_b
        return not (
            ax1 + padding < bx0 - padding
            or ax0 - padding > bx1 + padding
            or ay1 + padding < by0 - padding
            or ay0 - padding > by1 + padding
        )




class PosterMapGenerator(MapGenerator):
    FORMAT_ID = "POSTER_50X70"
    LABEL_FONT_PT = 28.0
    TITLE_FONT_PT = 112.0
    FOOTER_FONT_PT = 36.0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs = dict(kwargs)
        spec = self.PAPER_FORMATS.get(self.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 500.0))
        height_mm = float(spec.get("height_mm", 700.0))
        width_in = width_mm / self.MM_PER_INCH
        height_in = height_mm / self.MM_PER_INCH
        kwargs.setdefault("figsize", (width_in, height_in))
        kwargs.setdefault("paper_format", self.FORMAT_ID)
        kwargs.setdefault("min_margin_deg", 0.03)
        kwargs.setdefault("max_margin_factor", 0.06)
        kwargs.setdefault("curve_strength", 0.32)
        kwargs.setdefault("lock_paper_orientation", True)
        super().__init__(*args, **kwargs)
        self.poster_margin_vertical = 0.05
        self.poster_margin_horizontal = 0.08

    def _label_font_size_pt(self) -> float:
        return self.LABEL_FONT_PT

    @classmethod
    def paper_metadata(cls, dpi: int) -> Dict[str, Any]:
        spec = MapGenerator.PAPER_FORMATS.get(cls.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 500.0))
        height_mm = float(spec.get("height_mm", 700.0))
        return {
            "format": cls.FORMAT_ID,
            "label": spec.get("label", "Plakat 50 × 70 cm"),
            "orientation": "portrait",
            "dpi": int(dpi),
            "width_mm": width_mm,
            "height_mm": height_mm,
        }

    def _margin_factor_lat(self, lat_span: float) -> float:
        return self.poster_margin_vertical

    def _margin_factor_lon(self, lon_span: float) -> float:
        return self.poster_margin_horizontal

    def _axes_box(self) -> Tuple[float, float, float, float]:
        return (0.08, 0.17, 0.84, 0.66)

    def _render_text_overlays(self, ax: plt.Axes) -> None:
        fig = ax.figure
        font_family = self.text_font_family or self.font_family
        font_color = self.font_color

        if self.title_text:
            fig.text(
                0.5,
                0.965,
                self.title_text,
                ha='center',
                va='top',
                fontsize=self.TITLE_FONT_PT,
                fontfamily=font_family,
                color=font_color,
                fontweight='bold',
            )

        footer_font_size = self.footer_font_size if self.footer_font_size is not None else self.FOOTER_FONT_PT

        if self.footer_left_text:
            self._render_footer_text_fig(
                fig,
                self.footer_left_text,
                0.08,
                0.06,
                self._detect_footer_layout(self.footer_left_text),
                'left',
                font_family,
                font_color,
                footer_font_size,
            )

        if self.footer_right_text:
            self._render_footer_text_fig(
                fig,
                self.footer_right_text,
                0.92,
                0.06,
                self._detect_footer_layout(self.footer_right_text),
                'right',
                font_family,
                font_color,
                footer_font_size,
            )

    def generate_map(
        self,
        route: List[Dict],
        output_file: Optional[str] = None,
        label_overrides: Optional[Dict[str, Dict[str, float]]] = None,
        render_labels: bool = True,
        hidden_labels: Optional[set] = None,
    ) -> Dict[str, Any]:
        map_info = super().generate_map(
            route,
            output_file=output_file,
            label_overrides=label_overrides,
            render_labels=render_labels,
            hidden_labels=hidden_labels,
        )
        style = map_info.setdefault("style", {})
        style["title_font_size_pt"] = self.TITLE_FONT_PT
        style["footer_font_size_pt"] = self.FOOTER_FONT_PT
        return map_info




class LandscapePosterMapGenerator(MapGenerator):
    FORMAT_ID = "POSTER_70X50"
    LABEL_FONT_PT = 26.0
    TITLE_FONT_PT = 96.0
    FOOTER_FONT_PT = 32.0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs = dict(kwargs)
        spec = self.PAPER_FORMATS.get(self.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 700.0))
        height_mm = float(spec.get("height_mm", 500.0))
        width_in = width_mm / self.MM_PER_INCH
        height_in = height_mm / self.MM_PER_INCH
        kwargs.setdefault("figsize", (width_in, height_in))
        kwargs.setdefault("paper_format", self.FORMAT_ID)
        kwargs.setdefault("min_margin_deg", 0.03)
        kwargs.setdefault("max_margin_factor", 0.055)
        kwargs.setdefault("curve_strength", 0.30)
        kwargs.setdefault("lock_paper_orientation", True)
        super().__init__(*args, **kwargs)
        self.poster_margin_vertical = 0.05
        self.poster_margin_horizontal = 0.06

    def _label_font_size_pt(self) -> float:
        return self.LABEL_FONT_PT

    @classmethod
    def paper_metadata(cls, dpi: int) -> Dict[str, Any]:
        spec = MapGenerator.PAPER_FORMATS.get(cls.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 700.0))
        height_mm = float(spec.get("height_mm", 500.0))
        return {
            "format": cls.FORMAT_ID,
            "label": spec.get("label", "Plakat 70 × 50 cm"),
            "orientation": "landscape",
            "dpi": int(dpi),
            "width_mm": width_mm,
            "height_mm": height_mm,
        }

    def _margin_factor_lat(self, lat_span: float) -> float:
        return self.poster_margin_vertical

    def _margin_factor_lon(self, lon_span: float) -> float:
        return self.poster_margin_horizontal

    def _axes_box(self) -> Tuple[float, float, float, float]:
        return (0.10, 0.20, 0.80, 0.60)

    def _render_text_overlays(self, ax: plt.Axes) -> None:
        fig = ax.figure
        font_family = self.text_font_family or self.font_family
        font_color = self.font_color

        if self.title_text:
            fig.text(
                0.5,
                0.93,
                self.title_text,
                ha='center',
                va='top',
                fontsize=self.TITLE_FONT_PT,
                fontfamily=font_family,
                color=font_color,
                fontweight='bold',
            )

        footer_font_size = self.footer_font_size if self.footer_font_size is not None else self.FOOTER_FONT_PT

        if self.footer_left_text:
            self._render_footer_text_fig(
                fig,
                self.footer_left_text,
                0.10,
                0.08,
                self._detect_footer_layout(self.footer_left_text),
                'left',
                font_family,
                font_color,
                footer_font_size,
            )

        if self.footer_right_text:
            self._render_footer_text_fig(
                fig,
                self.footer_right_text,
                0.90,
                0.08,
                self._detect_footer_layout(self.footer_right_text),
                'right',
                font_family,
                font_color,
                footer_font_size,
            )

    def generate_map(
        self,
        route: List[Dict],
        output_file: Optional[str] = None,
        label_overrides: Optional[Dict[str, Dict[str, float]]] = None,
        render_labels: bool = True,
        hidden_labels: Optional[set] = None,
    ) -> Dict[str, Any]:
        map_info = super().generate_map(
            route,
            output_file=output_file,
            label_overrides=label_overrides,
            render_labels=render_labels,
            hidden_labels=hidden_labels,
        )
        style = map_info.setdefault("style", {})
        style["title_font_size_pt"] = self.TITLE_FONT_PT
        style["footer_font_size_pt"] = self.FOOTER_FONT_PT
        return map_info


class LargePosterMapGenerator(MapGenerator):
    FORMAT_ID = "POSTER_60X100"
    LABEL_FONT_PT = 32.0
    TITLE_FONT_PT = 140.0
    FOOTER_FONT_PT = 44.0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs = dict(kwargs)
        spec = self.PAPER_FORMATS.get(self.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 600.0))
        height_mm = float(spec.get("height_mm", 1000.0))
        width_in = width_mm / self.MM_PER_INCH
        height_in = height_mm / self.MM_PER_INCH
        kwargs.setdefault("figsize", (width_in, height_in))
        kwargs.setdefault("paper_format", self.FORMAT_ID)
        kwargs.setdefault("min_margin_deg", 0.03)
        kwargs.setdefault("max_margin_factor", 0.06)
        kwargs.setdefault("curve_strength", 0.32)
        kwargs.setdefault("lock_paper_orientation", True)
        super().__init__(*args, **kwargs)
        self.poster_margin_vertical = 0.05
        self.poster_margin_horizontal = 0.08

    def _label_font_size_pt(self) -> float:
        return self.LABEL_FONT_PT

    @classmethod
    def paper_metadata(cls, dpi: int) -> Dict[str, Any]:
        spec = MapGenerator.PAPER_FORMATS.get(cls.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 600.0))
        height_mm = float(spec.get("height_mm", 1000.0))
        return {
            "format": cls.FORMAT_ID,
            "label": spec.get("label", "Plakat 60 × 100 cm"),
            "orientation": "portrait",
            "dpi": int(dpi),
            "width_mm": width_mm,
            "height_mm": height_mm,
        }

    def _margin_factor_lat(self, lat_span: float) -> float:
        return self.poster_margin_vertical

    def _margin_factor_lon(self, lon_span: float) -> float:
        return self.poster_margin_horizontal

    def _axes_box(self) -> Tuple[float, float, float, float]:
        return (0.08, 0.17, 0.84, 0.66)

    def _render_text_overlays(self, ax: plt.Axes) -> None:
        fig = ax.figure
        font_family = self.text_font_family or self.font_family
        font_color = self.font_color

        if self.title_text:
            fig.text(
                0.5,
                0.965,
                self.title_text,
                ha='center',
                va='top',
                fontsize=self.TITLE_FONT_PT,
                fontfamily=font_family,
                color=font_color,
                fontweight='bold',
            )

        footer_font_size = self.footer_font_size if self.footer_font_size is not None else self.FOOTER_FONT_PT

        if self.footer_left_text:
            self._render_footer_text_fig(
                fig,
                self.footer_left_text,
                0.08,
                0.06,
                self._detect_footer_layout(self.footer_left_text),
                'left',
                font_family,
                font_color,
                footer_font_size,
            )

        if self.footer_right_text:
            self._render_footer_text_fig(
                fig,
                self.footer_right_text,
                0.92,
                0.06,
                self._detect_footer_layout(self.footer_right_text),
                'right',
                font_family,
                font_color,
                footer_font_size,
            )

    def generate_map(
        self,
        route: List[Dict],
        output_file: Optional[str] = None,
        label_overrides: Optional[Dict[str, Dict[str, float]]] = None,
        render_labels: bool = True,
        hidden_labels: Optional[set] = None,
    ) -> Dict[str, Any]:
        map_info = super().generate_map(
            route,
            output_file=output_file,
            label_overrides=label_overrides,
            render_labels=render_labels,
            hidden_labels=hidden_labels,
        )
        style = map_info.setdefault("style", {})
        style["title_font_size_pt"] = self.TITLE_FONT_PT
        style["footer_font_size_pt"] = self.FOOTER_FONT_PT
        return map_info


class LandscapeLargePosterMapGenerator(MapGenerator):
    FORMAT_ID = "POSTER_100X60"
    LABEL_FONT_PT = 30.0
    TITLE_FONT_PT = 120.0
    FOOTER_FONT_PT = 40.0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs = dict(kwargs)
        spec = self.PAPER_FORMATS.get(self.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 1000.0))
        height_mm = float(spec.get("height_mm", 600.0))
        width_in = width_mm / self.MM_PER_INCH
        height_in = height_mm / self.MM_PER_INCH
        kwargs.setdefault("figsize", (width_in, height_in))
        kwargs.setdefault("paper_format", self.FORMAT_ID)
        kwargs.setdefault("min_margin_deg", 0.03)
        kwargs.setdefault("max_margin_factor", 0.055)
        kwargs.setdefault("curve_strength", 0.30)
        kwargs.setdefault("lock_paper_orientation", True)
        super().__init__(*args, **kwargs)
        self.poster_margin_vertical = 0.05
        self.poster_margin_horizontal = 0.06

    def _label_font_size_pt(self) -> float:
        return self.LABEL_FONT_PT

    @classmethod
    def paper_metadata(cls, dpi: int) -> Dict[str, Any]:
        spec = MapGenerator.PAPER_FORMATS.get(cls.FORMAT_ID, {})
        width_mm = float(spec.get("width_mm", 1000.0))
        height_mm = float(spec.get("height_mm", 600.0))
        return {
            "format": cls.FORMAT_ID,
            "label": spec.get("label", "Plakat 100 × 60 cm"),
            "orientation": "landscape",
            "dpi": int(dpi),
            "width_mm": width_mm,
            "height_mm": height_mm,
        }

    def _margin_factor_lat(self, lat_span: float) -> float:
        return self.poster_margin_vertical

    def _margin_factor_lon(self, lon_span: float) -> float:
        return self.poster_margin_horizontal

    def _axes_box(self) -> Tuple[float, float, float, float]:
        return (0.10, 0.20, 0.80, 0.60)

    def _render_text_overlays(self, ax: plt.Axes) -> None:
        fig = ax.figure
        font_family = self.text_font_family or self.font_family
        font_color = self.font_color

        if self.title_text:
            fig.text(
                0.5,
                0.93,
                self.title_text,
                ha='center',
                va='top',
                fontsize=self.TITLE_FONT_PT,
                fontfamily=font_family,
                color=font_color,
                fontweight='bold',
            )

        footer_font_size = self.footer_font_size if self.footer_font_size is not None else self.FOOTER_FONT_PT

        if self.footer_left_text:
            self._render_footer_text_fig(
                fig,
                self.footer_left_text,
                0.10,
                0.08,
                self._detect_footer_layout(self.footer_left_text),
                'left',
                font_family,
                font_color,
                footer_font_size,
            )

        if self.footer_right_text:
            self._render_footer_text_fig(
                fig,
                self.footer_right_text,
                0.90,
                0.08,
                self._detect_footer_layout(self.footer_right_text),
                'right',
                font_family,
                font_color,
                footer_font_size,
            )

    def generate_map(
        self,
        route: List[Dict],
        output_file: Optional[str] = None,
        label_overrides: Optional[Dict[str, Dict[str, float]]] = None,
        render_labels: bool = True,
        hidden_labels: Optional[set] = None,
    ) -> Dict[str, Any]:
        map_info = super().generate_map(
            route,
            output_file=output_file,
            label_overrides=label_overrides,
            render_labels=render_labels,
            hidden_labels=hidden_labels,
        )
        style = map_info.setdefault("style", {})
        style["title_font_size_pt"] = self.TITLE_FONT_PT
        style["footer_font_size_pt"] = self.FOOTER_FONT_PT
        return map_info
