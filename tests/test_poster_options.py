"""Poster options used by the Churchill design: fonts, subtitle, rail-style line, double line, corner logo."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest
from PIL import Image

import backend
import map_generator as mg
import mcp_server

ROOT = Path(__file__).resolve().parent.parent

ROUTE = [  # Thompson -> Churchill -> Thompson: every leg ridden twice
    {"name": "Thompson", "latitude": 55.74, "longitude": -97.86},
    {"name": "Gillam", "latitude": 56.35, "longitude": -94.71},
    {"name": "Churchill", "latitude": 58.77, "longitude": -94.17},
    {"name": "Gillam", "latitude": 56.35, "longitude": -94.71},
    {"name": "Thompson", "latitude": 55.74, "longitude": -97.86},
]


@pytest.fixture
def keep_figure(monkeypatch):
    """generate_map closes its figure; keep it so the test can inspect what was drawn."""
    monkeypatch.setattr(mg.plt, "close", lambda *a, **k: None)
    yield
    plt.close("all")


def test_font_properties_bundled_fonts_resolve_to_repo_files():
    assert Path(mg.font_properties("Helvetica", bold=True).get_file()) == ROOT / "fonts" / "HelveticaBold.ttf"
    assert Path(mg.font_properties("Helvetica").get_file()) == ROOT / "fonts" / "Helvetica.ttf"
    assert Path(mg.font_properties("Superclarendon", bold=True).get_file()) == ROOT / "fonts" / "SuperclarendonBlack.ttf"
    assert Path(mg.font_properties("Euphemia UCAS").get_file()) == ROOT / "fonts" / "EuphemiaUCAS.ttf"


def test_font_properties_unknown_font_uses_family_name():
    props = mg.font_properties("Futura")
    assert props.get_file() is None and "Futura" in props.get_family()


def test_poster_title_and_subtitle_use_chosen_fonts():
    gen = mg.PosterMapGenerator(title_text="CHURCHILL", text_font_family="Superclarendon",
                                subtitle_text="ᑯᒡᔪᐊᖅ", subtitle_font_family="Euphemia UCAS")
    fig, ax = plt.subplots()
    gen._render_text_overlays(ax)
    texts = {t.get_text(): t for t in fig.texts}
    assert Path(texts["CHURCHILL"].get_fontproperties().get_file()).name == "SuperclarendonBlack.ttf"
    sub = texts["ᑯᒡᔪᐊᖅ"]
    assert Path(sub.get_fontproperties().get_file()).name == "EuphemiaUCASBold.ttf"
    assert sub.get_position()[1] < texts["CHURCHILL"].get_position()[1]
    plt.close(fig)


def test_city_labels_use_chosen_font(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(font_family="Helvetica", dpi=20)
    gen.generate_map(ROUTE, str(tmp_path / "m.png"))
    labels = [t for t in plt.gcf().axes[0].texts if t.get_text() == "Gillam"]
    assert Path(labels[0].get_fontproperties().get_file()).name == "HelveticaBold.ttf"


def _route_lines(fig):
    return [l for l in fig.axes[0].get_lines() if len(l.get_xdata()) > 2]


def test_line_outline_draws_edge_under_route(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(line_style="solid", line_color="#FFC72C", line_outline_color="#101511", dpi=20)
    gen.generate_map(ROUTE[:3], str(tmp_path / "m.png"))
    lines = _route_lines(plt.gcf())
    edges = [l for l in lines if matplotlib.colors.to_hex(l.get_color()) == "#101511"]
    cores = [l for l in lines if matplotlib.colors.to_hex(l.get_color()) == "#ffc72c"]
    assert len(edges) == len(cores) == 2
    assert edges[0].get_linewidth() > cores[0].get_linewidth()
    assert edges[0].get_zorder() < cores[0].get_zorder()


def test_repeated_legs_double_draws_parallel_lines(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(line_style="solid", repeated_legs="double", dpi=20)
    gen.generate_map(ROUTE, str(tmp_path / "m.png"))
    lines = _route_lines(plt.gcf())
    assert len(lines) == 4  # 2 legs x 2 trips
    thompson_x = -97.86
    pair = [l for l in lines if np.isclose(min(l.get_xdata()[0], l.get_xdata()[-1]), thompson_x, atol=0.2)]
    assert len(pair) == 2  # Thompson-Gillam there and back
    a, b = (np.c_[l.get_xdata(), l.get_ydata()] for l in pair)
    gaps = np.linalg.norm(a - b, axis=1)
    assert gaps.min() > 0 and gaps.max() / gaps.min() < 1.5  # parallel, not a lens that meets at the cities


def test_poster_is_portrait(tmp_path):
    out = tmp_path / "m.png"
    mg.PosterMapGenerator(dpi=10).generate_map(ROUTE, str(out))
    w, h = Image.open(out).size
    assert h > w


def test_corner_logo_preset_enables_signature():
    _, _, options, error = backend._prepare_generation({"cities": ["Winnipeg"], "corner_logo": "via_yellow_full"})
    assert error is None
    assert options["signature_enabled"] is True
    assert Path(options["signature_path"]) == ROOT / "logos" / "via_yellow_full.png"


def test_corner_logo_unknown_preset_is_ignored():
    _, _, options, _ = backend._prepare_generation({"cities": ["Winnipeg"], "corner_logo": "../../etc/passwd"})
    assert not options["signature_enabled"]


@pytest.fixture
def fake_geocoder(monkeypatch):
    class Fake:
        def get_coordinates(self, city):
            return (55.0, -97.0)
    monkeypatch.setattr(backend, "_geocoder", Fake())


def test_site_link_options_survive_round_trip_to_generator(fake_geocoder, monkeypatch):
    import base64, json
    monkeypatch.setattr(mcp_server, "_open_browser", lambda url: None)
    url = mcp_server.site_link(
        ["Winnipeg", "Churchill"], title="CHURCHILL", subtitle="ᑯᒡᔪᐊᖅ", paper_format="POSTER_50X70",
        font="Helvetica", text_font="Superclarendon", subtitle_font="Euphemia UCAS",
        line_style="solid", line_color="#FFC72C", line_outline_color="#101511",
        point_color="#FFFFFF", point_edge_color="#101511", repeated_legs="double", corner_logo="via_yellow",
        background="#22382C",
    )
    token = url.split("#p=", 1)[1]
    payload = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    _, _, options, error = backend._prepare_generation(payload)
    assert error is None
    expected = {"subtitle_text": "ᑯᒡᔪᐊᖅ", "font_family": "Helvetica", "text_font_family": "Superclarendon",
                "subtitle_font_family": "Euphemia UCAS", "line_outline_color": "#101511",
                "point_edge_color": "#101511", "repeated_legs": "double", "signature_enabled": True}
    assert {k: options[k] for k in expected} == expected


def test_form_has_option_for_every_value_mcp_sends():
    html = (ROOT / "templates" / "index.html").read_text()
    for value in ("Superclarendon", "Euphemia UCAS", "double", "via_yellow", "via_yellow_full",
                  "via_cream", "via_dark", "via_dark_full"):
        assert f'value="{value}"' in html, value
    for name in ("subtitle", "subtitle_font", "line_outline_color", "point_edge_color", "repeated_legs", "corner_logo"):
        assert f'name="{name}"' in html, name


def test_curve_strength_zero_draws_straight_legs(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(line_style="solid", curve_strength=0.0, dpi=20)
    gen.generate_map(ROUTE[:2], str(tmp_path / "m.png"))
    line = _route_lines(plt.gcf())[0]
    xy = np.c_[line.get_xdata(), line.get_ydata()]
    chord = xy[-1] - xy[0]
    rel = xy - xy[0]
    cross = np.abs(chord[0] * rel[:, 1] - chord[1] * rel[:, 0]) / np.linalg.norm(chord)
    assert cross.max() < 1e-9


def test_curve_strength_from_form_reaches_generator(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "curve_strength": "0.1"})
    assert options["curve_strength"] == 0.1
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "curve_strength": "junk"})
    assert "curve_strength" not in options


@pytest.mark.parametrize("font_file", sorted(p.name for p in (ROOT / "fonts").glob("*.ttf") if "Euphemia" not in p.name))
def test_bundled_latin_fonts_have_polish_glyphs(font_file):
    from matplotlib import ft2font
    face = ft2font.FT2Font(str(ROOT / "fonts" / font_file))
    missing = [c for c in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ" if face.get_char_index(ord(c)) == 0]
    assert not missing, missing


def test_euphemia_has_inuktitut_syllabics():
    from matplotlib import ft2font
    face = ft2font.FT2Font(str(ROOT / "fonts" / "EuphemiaUCASBold.ttf"))
    assert all(face.get_char_index(ord(c)) for c in "ᑯᒡᔪᐊᖅᑰ")


def test_default_title_keeps_regular_weight_heavy_only_for_display_font():
    fig, ax = plt.subplots()
    mg.PosterMapGenerator(title_text="Plain", text_font_family="Helvetica")._render_text_overlays(ax)
    mg.PosterMapGenerator(title_text="Heavy", text_font_family="Superclarendon")._render_text_overlays(ax)
    files = {t.get_text(): Path(t.get_fontproperties().get_file()).name for t in fig.texts}
    assert files == {"Plain": "Helvetica.ttf", "Heavy": "SuperclarendonBlack.ttf"}
    plt.close(fig)


def test_helvetica_regular_choice_keeps_regular_face_for_labels():
    assert Path(mg.font_properties("Helvetica Regular", bold=True).get_file()).name == "Helvetica.ttf"
    html = (ROOT / "templates" / "index.html").read_text()
    assert 'value="Helvetica Regular"' in html


def test_footer_signature_draws_mikolaj_stroke_bottom_left(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(footer_signature="mikolaj", font_color="#FFFFFF", dpi=20)
    gen.generate_map(ROUTE[:2], str(tmp_path / "m.png"))
    fig = plt.gcf()
    sig = [a for a in fig.artists if a.get_gid() == "footer-signature"]
    assert len(sig) == 1
    xs, ys = sig[0].get_xdata(), sig[0].get_ydata()
    assert len(xs) == 17  # every vertex of the site's SVG path
    assert max(xs) < 0.5 and max(ys) < 0.1  # bottom-left corner, figure coordinates
    assert matplotlib.colors.to_hex(sig[0].get_color()) == "#ffffff"


def test_footer_signature_unknown_id_draws_nothing(tmp_path, keep_figure):
    mg.PosterMapGenerator(footer_signature="nobody", dpi=20).generate_map(ROUTE[:2], str(tmp_path / "m.png"))
    assert not [a for a in plt.gcf().artists if a.get_gid() == "footer-signature"]


def test_footer_signature_reaches_generator_and_form(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "footer_signature": "mikolaj"})
    assert options["footer_signature"] == "mikolaj"
    assert 'name="footer_signature"' in (ROOT / "templates" / "index.html").read_text()


def test_server_assets_live_outside_static():
    # Vercel serves static/ from its CDN; files the server reads must ship with the function (regression: logo vanished)
    assert "static" not in backend.LOGO_DIR.relative_to(ROOT).parts
    assert "static" not in mg.FONT_DIR.relative_to(ROOT).parts
    assert backend.LOGO_PRESETS == {"via_yellow", "via_yellow_full", "via_cream", "via_dark", "via_dark_full"}
