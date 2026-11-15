from pathlib import Path

import pytest

import backend
import label_overrides
import mcp_server

COORDS = {
    "Winnipeg": (49.9, -97.14),
    "Thompson": (55.74, -97.86),
    "Churchill": (58.77, -94.17),
}


class FakeGeocoder:
    def get_coordinates(self, city):
        return COORDS.get(city)


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "_geocoder", FakeGeocoder())
    monkeypatch.setattr(backend, "MAP_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(label_overrides, "OVERRIDES_PATH", tmp_path / "overrides.json")
    monkeypatch.setattr(mcp_server, "_place_name", lambda lat, lon: f"place@{lat},{lon}")
    monkeypatch.setattr(mcp_server, "_ensure_preview_server", lambda: None)  # no real server in tests


def test_check_cities_reports_found_and_missing():
    result = mcp_server.check_cities(["Winnipeg", "Nowhere"])
    assert result[0] == {"city": "Winnipeg", "found": True, "lat": 49.9, "lon": -97.14, "place": "place@49.9,-97.14"}
    assert result[1] == {"city": "Nowhere", "found": False}


def test_generate_poster_writes_png_and_copies(tmp_path):
    out = tmp_path / "copy" / "poster.png"
    result = mcp_server.generate_poster(
        ["Winnipeg", "Thompson", "Churchill", "Nowhere"],
        title="Test", dpi=50, output_path=str(out),
    )
    assert Path(result["file"]).is_file()
    assert out.is_file() and out.read_bytes()[:4] == b"\x89PNG"
    assert result["cities"] == ["Winnipeg", "Thompson", "Churchill"]
    assert any("Nowhere" in w for w in result["warnings"])


def test_generate_poster_keeps_stdout_clean(capsys):
    # stdout is the MCP stdio channel; any print there corrupts the protocol
    mcp_server.generate_poster(["Winnipeg", "Thompson"], dpi=50)
    assert capsys.readouterr().out == ""


def test_generate_poster_rejects_unknown_paper_format():
    with pytest.raises(ValueError):
        mcp_server.generate_poster(["Winnipeg", "Thompson"], paper_format="A3")


def test_generate_poster_rejects_empty_route():
    with pytest.raises(ValueError):
        mcp_server.generate_poster(["Nowhere"])


def test_move_label_accumulates_and_reset_clears():
    mcp_server.move_label("Thompson", 0.5, -0.25)
    assert mcp_server.move_label("Thompson", 0.5, 0.0)["Thompson"] == {"dx": 1.0, "dy": -0.25}
    assert "Thompson" not in mcp_server.reset_labels("Thompson")


def test_preview_latest_returns_newest_mcp_poster(tmp_path):
    import os
    old = tmp_path / "map_final_mcp_old.png"
    new = tmp_path / "map_final_mcp_new.png"
    old.write_bytes(b"x"); new.write_bytes(b"y")
    os.utime(old, (1, 1))
    client = backend.app.test_client()
    data = client.get("/api/preview/latest").get_json()
    assert data["file"] == "map_final_mcp_new.png"
    assert data["url"].endswith("/maps/map_final_mcp_new.png")


def test_preview_latest_empty_when_no_posters():
    client = backend.app.test_client()
    assert client.get("/api/preview/latest").get_json() == {"file": None}


def test_preview_page_renders():
    resp = backend.app.test_client().get("/preview")
    assert resp.status_code == 200 and b"/api/preview/latest" in resp.data


def test_generate_poster_returns_preview_url(monkeypatch):
    monkeypatch.setattr(mcp_server, "_ensure_preview_server", lambda: "http://127.0.0.1:5055/preview")
    result = mcp_server.generate_poster(["Winnipeg", "Thompson"], dpi=50)
    assert result["preview"] == "http://127.0.0.1:5055/preview"


def _decode_site_link(url):
    import base64, json
    token = url.split("#p=", 1)[1]
    return json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode())


def test_site_link_roundtrips_project_with_polish_chars():
    url = mcp_server.site_link(["Kraków", "Bird Manitoba"], title="Zażółć", paper_format="POSTER_50X70")
    assert url.startswith("https://louisiana.vercel.app/#p=")
    assert _decode_site_link(url) == {
        "cities": "Kraków\nBird Manitoba", "title": "Zażółć", "paper_format": "POSTER_50X70",
    }


def test_generate_poster_returns_site_link():
    result = mcp_server.generate_poster(["Winnipeg", "Thompson"], title="T", dpi=50)
    assert _decode_site_link(result["site"])["cities"] == "Winnipeg\nThompson"
