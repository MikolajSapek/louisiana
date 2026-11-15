import base64
import json

import pytest

import backend
import mcp_server

COORDS = {"Winnipeg": (49.9, -97.14), "Thompson": (55.74, -97.86)}


class FakeGeocoder:
    def get_coordinates(self, city):
        return COORDS.get(city)


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(backend, "_geocoder", FakeGeocoder())
    monkeypatch.setattr(mcp_server, "_place_name", lambda lat, lon: f"place@{lat},{lon}")
    monkeypatch.setattr(mcp_server, "_open_browser", lambda url: None)  # no real browser in tests


def _decode(url):
    token = url.split("#p=", 1)[1]
    return json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode())


def test_check_cities_reports_found_and_missing():
    result = mcp_server.check_cities(["Winnipeg", "Nowhere"])
    assert result[0] == {"city": "Winnipeg", "found": True, "lat": 49.9, "lon": -97.14, "place": "place@49.9,-97.14"}
    assert result[1] == {"city": "Nowhere", "found": False}


def test_site_link_roundtrips_project_with_polish_chars():
    url = mcp_server.site_link(["Kraków", "Bird Manitoba"], title="Zażółć")
    assert url.startswith("https://louisiana.vercel.app/#p=")
    assert _decode(url) == {"cities": "Kraków\nBird Manitoba", "title": "Zażółć", "paper_format": "POSTER_50X70"}


def test_site_link_defaults_to_portrait_poster():
    assert _decode(mcp_server.site_link(["Winnipeg"]))["paper_format"] == "POSTER_50X70"


def test_site_link_rejects_unknown_paper_format():
    with pytest.raises(ValueError):
        mcp_server.site_link(["Winnipeg"], paper_format="A3")


def test_site_link_opens_browser_by_default(monkeypatch):
    opened = []
    monkeypatch.setattr(mcp_server, "_open_browser", opened.append)
    url = mcp_server.site_link(["Winnipeg"])
    assert opened == [url]


def test_site_link_can_skip_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(mcp_server, "_open_browser", opened.append)
    mcp_server.site_link(["Winnipeg"], open_in_browser=False)
    assert opened == []


def test_check_cities_uses_bracket_hint_for_lookup():
    COORDS["Thompson Manitoba"] = (55.74, -97.86)
    assert mcp_server.check_cities(["Thompson [Manitoba]"])[0]["found"] is True


def test_site_link_pins_coordinates_so_the_site_skips_geocoding():
    url = mcp_server.site_link(["Winnipeg", "Thompson [Manitoba]", "Nowhere"])
    COORDS["Thompson Manitoba"] = (55.74, -97.86)
    url = mcp_server.site_link(["Winnipeg", "Thompson [Manitoba]", "Nowhere"])
    assert _decode(url)["cities"] == "Winnipeg [49.9 -97.14]\nThompson [55.74 -97.86]\nNowhere"


def test_site_link_can_leave_geocoding_to_the_site():
    url = mcp_server.site_link(["Winnipeg"], pin_coordinates=False)
    assert _decode(url)["cities"] == "Winnipeg"


def test_site_link_local_targets_the_local_site(monkeypatch):
    started = []
    monkeypatch.setattr(mcp_server, "_ensure_local_site", lambda: started.append(1) or "http://127.0.0.1:5056/")
    url = mcp_server.site_link(["Winnipeg"], local=True, pin_coordinates=False)
    assert url.startswith("http://127.0.0.1:5056/#p=") and started == [1]
