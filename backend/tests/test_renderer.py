import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services import renderer

RED_PAGE = "<body style='margin:0;background:#ff0000'></body>"


def _chromium_works() -> bool:
    try:
        renderer._render_sync("<p>x</p>", 50, 50)
        return True
    except Exception:
        return False


needs_chromium = pytest.mark.skipif(not _chromium_works(), reason="Chromium not installed")


def test_allowlist():
    assert renderer._is_allowed("https://cdn.tailwindcss.com/")
    assert renderer._is_allowed("data:image/png;base64,AAAA")
    assert not renderer._is_allowed("file:///etc/passwd")
    assert not renderer._is_allowed("http://localhost:8000/health")
    assert not renderer._is_allowed("http://169.254.169.254/latest/meta-data")


@needs_chromium
def test_png_has_requested_size_and_real_pixels():
    import asyncio

    png = asyncio.run(renderer.render_html(RED_PAGE, 300, 120))
    img = Image.open(io.BytesIO(png)).convert("RGB")
    assert img.size == (300, 120)
    assert img.getpixel((5, 5)) == (255, 0, 0)  # the page really was drawn


@needs_chromium
def test_route_returns_png():
    client = TestClient(app)
    res = client.post("/render", data={"html": RED_PAGE, "width": 200, "height": 80})
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(res.content)).size == (200, 80)


def test_route_rejects_bad_size():
    client = TestClient(app)
    res = client.post("/render", data={"html": "<p>x</p>", "width": 0, "height": 80})
    assert res.status_code == 422
    res = client.post("/render", data={"html": "<p>x</p>", "width": 99999, "height": 80})
    assert res.status_code == 422


@needs_chromium
def test_infinite_loop_page_times_out(monkeypatch):
    monkeypatch.setattr(renderer, "TIMEOUT_MS", 1500)
    import asyncio

    with pytest.raises(renderer.RenderError):
        asyncio.run(renderer.render_html("<script>while(true){}</script>", 100, 100))