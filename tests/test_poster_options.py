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
    props = mg.font_properties("Montserrat")
    assert props.get_file() is None and "Montserrat" in props.get_family()


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


def test_vercelignore_keeps_logo_pngs():
    # .vercelignore drops *.png; without this exception the corner logo silently disappears on Vercel
    assert "!logos/*.png" in (ROOT / ".vercelignore").read_text().splitlines()


def test_rockwell_bundled_heavy_for_titles_and_in_form():
    assert Path(mg.font_properties("Rockwell").get_file()).name == "Rockwell.ttf"
    assert Path(mg.title_font_properties("Rockwell").get_file()).name == "RockwellBold.ttf"
    html = (ROOT / "templates" / "index.html").read_text()
    assert html.count('value="Rockwell"') == 4  # labels, title, subtitle, footer


def test_footer_signature_is_small():
    assert mg.SIGNATURE_BOX[2] <= 0.012


def test_bracketed_hint_geocodes_but_is_not_printed(monkeypatch):
    queries = []

    class Recorder:
        def get_coordinates(self, city):
            queries.append(city)
            return (56.5, -94.2)
    monkeypatch.setattr(backend, "_geocoder", Recorder())
    route, warnings = backend._build_route(["Bird [Manitoba]", "Gillam"])
    assert queries == ["Bird Manitoba", "Gillam"]
    assert [p["name"] for p in route] == ["Bird", "Gillam"]


def test_private_mounties_font_stays_out_of_the_public_site():
    assert "fonts/private/" in (ROOT / ".gitignore").read_text()
    assert "fonts/private/" in (ROOT / ".vercelignore").read_text()
    assert 'value="Mounties"' not in (ROOT / "templates" / "index.html").read_text()
    assert not (ROOT / "static" / "fonts" / "Mounties.ttf").exists()


def test_missing_private_font_falls_back_instead_of_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr(mg, "FONT_DIR", tmp_path)
    assert mg.font_properties("Mounties").get_file() is None


@pytest.mark.skipif(not (ROOT / "fonts" / "private" / "Mounties.ttf").exists(), reason="private font only on the owner's Mac")
def test_private_mounties_font_covers_the_poster_text():
    from matplotlib import ft2font
    assert Path(mg.font_properties("Mounties", bold=True).get_file()).name == "Mounties.ttf"
    face = ft2font.FT2Font(str(ROOT / "fonts" / "private" / "Mounties.ttf"))
    for text in ("CHURCHILL", "Thompson", "Paweł Sofia Mikołaj", "8–14 listopada 2026"):
        assert all(face.get_char_index(ord(c)) for c in text if c != " "), text


def test_coordinate_hint_skips_geocoder(monkeypatch):
    class Boom:
        def get_coordinates(self, city):
            raise AssertionError("geocoder must not be called for pinned coordinates")
    monkeypatch.setattr(backend, "_geocoder", Boom())
    route, warnings = backend._build_route(["The Pas [53.825 -101.241]"])
    assert route == [{"name": "The Pas", "latitude": 53.825, "longitude": -101.241}] and warnings == []


def test_corner_logo_keeps_a_proportional_margin(tmp_path):
    out = tmp_path / "m.png"
    gen = mg.PosterMapGenerator(dpi=150, signature_enabled=True, signature_path=str(ROOT / "logos" / "via_yellow_full.png"))
    info = gen.generate_map(ROUTE[:2], str(out))
    w, h = Image.open(out).size
    b = info["signature"]["box"]
    assert w - (b["x"] + b["width"]) >= 0.035 * w   # clear of the right edge
    assert h - (b["y"] + b["height"]) >= 0.025 * h  # clear of the bottom edge


def test_title_and_label_sizes_are_adjustable(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(title_text="CHURCHILL", title_font_size=170, label_font_size=40, dpi=20)
    gen.generate_map(ROUTE[:2], str(tmp_path / "m.png"))
    fig = plt.gcf()
    title = [t for t in fig.texts if t.get_text() == "CHURCHILL"][0]
    label = [t for t in fig.axes[0].texts if t.get_text() == "Gillam"][0]
    assert title.get_fontsize() == 170 and label.get_fontsize() == 40


def test_sizes_from_form_reach_generator(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "title_font_size": "150", "label_font_size": "30"})
    assert options["title_font_size"] == 150.0 and options["label_font_size"] == 30.0
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "title_font_size": "x"})
    assert "title_font_size" not in options


def test_private_indians_font_registered_but_not_on_site():
    assert mg.BUNDLED_FONTS["indians"][0].startswith("private/")
    assert 'value="Indians"' not in (ROOT / "templates" / "index.html").read_text()


def test_title_subtitle_and_label_colours_are_separate(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(title_text="CHURCHILL", subtitle_text="ᑯᒡᔪᐊᖅ", font_color="#ffffff",
                                title_color="#f2c21b", subtitle_color="#f4f1e8", label_color="#a8a39a", dpi=20)
    gen.generate_map(ROUTE[:2], str(tmp_path / "m.png"))
    fig = plt.gcf()
    colour = lambda t: matplotlib.colors.to_hex(t.get_color())
    texts = {t.get_text(): colour(t) for t in fig.texts}
    assert texts["CHURCHILL"] == "#f2c21b" and texts["ᑯᒡᔪᐊᖅ"] == "#f4f1e8"
    assert colour([t for t in fig.axes[0].texts if t.get_text() == "Gillam"][0]) == "#a8a39a"


def test_colours_fall_back_to_font_colour_and_reach_generator(fake_geocoder):
    gen = mg.PosterMapGenerator(font_color="#123456")
    assert gen.title_color == gen.subtitle_color == gen.label_color == "#123456"
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "title_color": "#F2C21B", "label_color": "nope"})
    assert options["title_color"] == "#F2C21B" and options["label_color"] is None


def test_footer_font_is_separate_from_title_font():
    gen = mg.PosterMapGenerator(title_text="CHURCHILL", text_font_family="Superclarendon", footer_font_family="Helvetica",
                                footer_left_text="Paweł Sofia Mikołaj")
    fig, ax = plt.subplots()
    gen._render_text_overlays(ax)
    files = {t.get_text(): Path(t.get_fontproperties().get_file()).name for t in fig.texts}
    assert files["CHURCHILL"] == "SuperclarendonBlack.ttf" and files["Paweł Sofia Mikołaj"] == "HelveticaBold.ttf"
    plt.close(fig)


def test_footer_font_reaches_generator(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "footer_font": "Helvetica"})
    assert options["footer_font_family"] == "Helvetica"


def test_private_north_railway_registered():
    assert mg.BUNDLED_FONTS["north railway"][0].startswith("private/")


def test_private_font_served_locally_but_never_on_vercel(monkeypatch, tmp_path):
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "X.ttf").write_bytes(b"font")
    monkeypatch.setattr(backend, "PRIVATE_FONT_DIR", tmp_path / "private")
    client = backend.app.test_client()
    monkeypatch.setattr(backend, "IS_VERCEL", False)
    assert client.get("/private-fonts/X.ttf").status_code == 200
    assert client.get("/private-fonts/../backend.py").status_code == 404
    monkeypatch.setattr(backend, "IS_VERCEL", True)
    assert client.get("/private-fonts/X.ttf").status_code == 404


def test_label_font_url_only_for_private_fonts_when_local(monkeypatch):
    monkeypatch.setattr(backend, "IS_VERCEL", False)
    with backend.app.test_request_context():
        assert backend._label_font_url("North Railway").endswith("/private-fonts/NorthRailway-DEMO.ttf")
        assert backend._label_font_url("Helvetica") is None
    monkeypatch.setattr(backend, "IS_VERCEL", True)
    with backend.app.test_request_context():
        assert backend._label_font_url("North Railway") is None


def test_poster_footer_aligns_with_corner_logo_margins():
    gen = mg.PosterMapGenerator(footer_left_text="Paweł Sofia Mikołaj\n8–14 listopada 2026")
    fig, ax = plt.subplots()
    gen._render_text_overlays(ax)
    footer = [t for t in fig.texts if t.get_text().startswith("Paweł")][0]
    x, y = footer.get_position()
    assert (x, y) == (0.04, 0.03)  # same margins as the corner logo: 4 % from the side, 3 % from the bottom
    assert footer.get_linespacing() <= 1.3
    plt.close(fig)


@pytest.mark.skipif(not (ROOT / "fonts" / "private" / "NorthRailwayPL.ttf").exists(), reason="private font only on the owner's Mac")
def test_north_railway_pl_covers_the_footer():
    from matplotlib import ft2font
    assert Path(mg.font_properties("North Railway PL").get_file()).name == "NorthRailwayPL.ttf"
    face = ft2font.FT2Font(str(ROOT / "fonts" / "private" / "NorthRailwayPL.ttf"))
    assert all(face.get_char_index(ord(c)) for c in "Paweł Sofia Mikołaj 8–14 listopada 2026" if c != " ")


def test_footer_font_size_from_form_reaches_generator(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "footer_font_size": "50"})
    assert options["footer_font_size"] == 50.0


def test_legs_after_dashed_from_are_dashed_and_thinner(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(line_style="solid", line_outline_color="#101511", dashed_from=3, dpi=20)
    gen.generate_map(ROUTE, str(tmp_path / "m.png"))  # legs: 1-2, 2-3 solid; 3-4, 4-5 dashed (bus)
    lines = _route_lines(plt.gcf())
    solid = [l for l in lines if l.get_linestyle() == "-"]
    dashed = [l for l in lines if l.get_linestyle() == "--"]
    assert len(dashed) == 2  # bus legs, no outline under them
    assert len(solid) == 4  # 2 train legs x (outline + core)
    assert dashed[0].get_linewidth() < max(l.get_linewidth() for l in solid if matplotlib.colors.to_hex(l.get_color()) != "#101511")


def test_major_and_minor_labels_change_size_and_colour(tmp_path, keep_figure):
    gen = mg.PosterMapGenerator(label_font_size=30, title_color="#f2c318", label_color="#e8e9eb",
                                major_labels=["Churchill"], minor_labels=["Gillam"], dpi=20)
    gen.generate_map(ROUTE, str(tmp_path / "m.png"))
    texts = {t.get_text(): t for t in plt.gcf().axes[0].texts}
    assert texts["Churchill"].get_fontsize() > 30 and matplotlib.colors.to_hex(texts["Churchill"].get_color()) == "#f2c318"
    assert texts["Gillam"].get_fontsize() < 30
    assert texts["Thompson"].get_fontsize() == 30


def test_water_is_drawn_when_enabled(tmp_path, keep_figure, monkeypatch):
    square = [[(-100.0, 50.0), (-90.0, 50.0), (-90.0, 60.0), (-100.0, 60.0), (-100.0, 50.0)]]
    monkeypatch.setattr(mg.MapGenerator, "_get_water_paths", lambda self: [mg.rings_to_path(square)])
    gen = mg.PosterMapGenerator(show_water=True, water_color="#083a7a", dpi=20)
    gen.generate_map(ROUTE, str(tmp_path / "m.png"))
    patches = [p for p in plt.gcf().axes[0].patches if p.get_gid() == "water"]
    assert len(patches) == 1 and matplotlib.colors.to_hex(patches[0].get_facecolor()) == "#083a7a"


def test_new_map_options_reach_generator(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "dashed_from": "16", "show_water": "on",
                                                    "water_color": "#083A7A", "major_labels": "Churchill\nWinnipeg",
                                                    "minor_labels": "Bird, Ilford"})
    assert options["dashed_from"] == 16 and options["show_water"] is True and options["water_color"] == "#083A7A"
    assert options["major_labels"] == ["Churchill", "Winnipeg"] and options["minor_labels"] == ["Bird", "Ilford"]


def test_extra_points_widen_the_map_extent(tmp_path):
    base = mg.PosterMapGenerator(dpi=10).generate_map(ROUTE, str(tmp_path / "a.png"))["bounds"]
    wide = mg.PosterMapGenerator(dpi=10, include_points=[(58.8, -90.0)]).generate_map(ROUTE, str(tmp_path / "b.png"))["bounds"]
    assert wide["lon_max"] > -90.0 > base["lon_max"]


def test_include_points_from_form(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "include_points": "58.8 -90\nbad\n49.5 -101.2"})
    assert options["include_points"] == [(58.8, -90.0), (49.5, -101.2)]


def test_single_line_footer_sits_on_a_baseline_at_footer_y():
    gen = mg.PosterMapGenerator(footer_left_text="Paweł, Sofia & Mikołaj · 8–14 listopada 2026", footer_y=0.0342)
    fig, ax = plt.subplots()
    gen._render_text_overlays(ax)
    t = [t for t in fig.texts if t.get_text().startswith("Paweł")][0]
    assert t.get_position() == (0.04, 0.0342) and t.get_verticalalignment() == "baseline"
    plt.close(fig)


def test_footer_y_from_form(fake_geocoder):
    _, _, options, _ = backend._prepare_generation({"cities": ["A", "B"], "footer_y": "0.0342"})
    assert options["footer_y"] == 0.0342
