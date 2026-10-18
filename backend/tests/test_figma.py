"""Figma preview and generate-from-figma. Figma itself is mocked, so no quota is used."""
import io
import json
import os
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.routes import generate as generate_route
from app.services import figma as figma_service
from app.services.figma import BAD_LINK, NO_NODE, parse_figma_url
from app.services.preprocess import PaletteColor, PreprocessResult

client = TestClient(app)

FRAME_URL = "https://www.figma.com/design/Abcd1234/Home?node-id=10-20"


def png_bytes(size=(80, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return buf.getvalue()


def events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def install_figma(monkeypatch, handler):
    original = figma_service.build_client

    def build():
        return original(httpx.MockTransport(handler))

    monkeypatch.setattr(figma_service, "build_client", build)


@pytest.fixture(autouse=True)
def figma_token(monkeypatch):
    monkeypatch.setattr(settings, "FIGMA_ACCESS_TOKEN", "test-token")


@pytest.fixture
def figma_http(monkeypatch):
    """A Figma that renders one PNG and names the frame Login."""
    calls: list[httpx.Request] = []
    image = png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.startswith("/v1/images/"):
            node = request.url.params.get("ids")
            return httpx.Response(
                200,
                json={"err": None, "images": {node: "https://s3-alpha.figma.com/frame.png"}},
            )
        if path.endswith("/nodes"):
            node = request.url.params.get("ids")
            return httpx.Response(200, json={"nodes": {node: {"document": {"name": "Login"}}}})
        if request.url.host == "s3-alpha.figma.com":
            return httpx.Response(200, content=image)
        return httpx.Response(404, json={"err": "unexpected"})

    install_figma(monkeypatch, handler)
    return calls


# ---- URL parsing ------------------------------------------------------------

def test_parse_design_link_converts_hyphen_node_id():
    assert parse_figma_url(FRAME_URL) == ("Abcd1234", "10:20")


def test_parse_accepts_encoded_colon_and_branch_key():
    encoded = "https://www.figma.com/file/Abcd1234/Home?node-id=10%3A20"
    branch = "https://www.figma.com/design/Abcd1234/branch/BranchKey99/Home?node-id=10-20"
    assert parse_figma_url(encoded) == ("Abcd1234", "10:20")
    assert parse_figma_url(branch) == ("BranchKey99", "10:20")


@pytest.mark.parametrize("url", [
    "",
    "not a url",
    "https://example.com/design/Abcd1234/Home?node-id=10-20",
    "https://www.figma.com/community/file/Abcd1234/Home?node-id=10-20",
])
def test_parse_rejects_a_bad_link(url):
    with pytest.raises(figma_service.FigmaLinkError, match=BAD_LINK):
        parse_figma_url(url)


def test_parse_rejects_a_link_with_no_frame():
    with pytest.raises(figma_service.FigmaLinkError, match=NO_NODE):
        parse_figma_url("https://www.figma.com/design/Abcd1234/Home")


# ---- POST /figma/preview ----------------------------------------------------

def test_preview_returns_size_name_and_image(figma_http):
    response = client.post("/figma/preview", json={"figma_url": FRAME_URL})

    assert response.status_code == 200
    body = response.json()
    assert len(body["preview_id"]) == 32
    assert body["width"] == 80
    assert body["height"] == 40
    assert body["name"] == "Login"

    image = client.get(f"/figma/preview/{body['preview_id']}/image")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content == png_bytes()

    api_calls = [call for call in figma_http if call.url.host == "api.figma.com"]
    assert api_calls
    assert all(call.headers["x-figma-token"] == "test-token" for call in api_calls)
    download = next(call for call in figma_http if call.url.host == "s3-alpha.figma.com")
    assert "x-figma-token" not in download.headers


def test_branch_link_is_rendered_with_the_branch_key(figma_http):
    url = "https://www.figma.com/design/Abcd1234/branch/BranchKey99/Home?node-id=10-20"
    response = client.post("/figma/preview", json={"figma_url": url})

    assert response.status_code == 200
    rendered = next(call for call in figma_http if call.url.path.startswith("/v1/images/"))
    assert rendered.url.path == "/v1/images/BranchKey99"


def test_preview_rejects_a_bad_link():
    response = client.post("/figma/preview", json={"figma_url": "https://example.com/design"})
    assert response.status_code == 400
    assert response.json()["detail"] == BAD_LINK


def test_preview_rejects_a_missing_frame():
    response = client.post(
        "/figma/preview",
        json={"figma_url": "https://www.figma.com/design/Abcd1234/Home"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == NO_NODE


def test_preview_reports_no_access(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"status": 403, "err": "nope"})

    install_figma(monkeypatch, handler)
    response = client.post("/figma/preview", json={"figma_url": FRAME_URL})
    assert response.status_code == 403
    assert response.json()["detail"] == figma_service.NO_ACCESS


def test_preview_rejects_a_render_from_an_unknown_host(monkeypatch):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.path.startswith("/v1/images/"):
            return httpx.Response(200, json={"images": {"10:20": "https://evil.example/secret.png"}})
        return httpx.Response(200, json={"nodes": {}})

    install_figma(monkeypatch, handler)
    response = client.post("/figma/preview", json={"figma_url": FRAME_URL})
    assert response.status_code == 400
    assert response.json()["detail"] == figma_service.RENDER_FAILED
    assert "evil.example" not in seen


def test_preview_rejects_an_oversized_render(monkeypatch, figma_http):
    monkeypatch.setattr(figma_service, "MAX_BYTES", 10)
    response = client.post("/figma/preview", json={"figma_url": FRAME_URL})
    assert response.status_code == 413


def test_preview_rejects_bytes_that_are_not_an_image(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/v1/images/"):
            return httpx.Response(200, json={"images": {"10:20": "https://s3-alpha.figma.com/frame.png"}})
        if request.url.host == "s3-alpha.figma.com":
            return httpx.Response(200, content=b"not an image")
        return httpx.Response(200, json={"nodes": {}})

    install_figma(monkeypatch, handler)
    response = client.post("/figma/preview", json={"figma_url": FRAME_URL})
    assert response.status_code == 400
    assert response.json()["detail"] == figma_service.RENDER_FAILED


def test_preview_without_a_token_does_not_call_figma(monkeypatch):
    monkeypatch.setattr(settings, "FIGMA_ACCESS_TOKEN", "")
    called = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.host)
        return httpx.Response(500)

    install_figma(monkeypatch, handler)
    response = client.post("/figma/preview", json={"figma_url": FRAME_URL})
    assert response.status_code == 400
    assert response.json()["detail"] == figma_service.NOT_CONFIGURED
    assert called == []


def test_missing_preview_image_is_not_found():
    response = client.get("/figma/preview/" + ("a" * 32) + "/image")
    assert response.status_code == 404


def test_new_preview_deletes_ones_older_than_30_minutes(figma_http):
    first = client.post("/figma/preview", json={"figma_url": FRAME_URL}).json()["preview_id"]
    fresh = client.post("/figma/preview", json={"figma_url": FRAME_URL}).json()["preview_id"]
    root = Path(settings.DATA_DIR) / "figma-previews"
    old = time.time() - 31 * 60
    os.utime(root / first, (old, old))

    second = client.post("/figma/preview", json={"figma_url": FRAME_URL}).json()["preview_id"]

    assert not (root / first).exists()
    assert (root / fresh).is_dir()
    assert (root / second).is_dir()


# ---- POST /generate-from-figma ----------------------------------------------

@pytest.fixture
def fake_preprocessing(monkeypatch):
    async def fake(image_bytes):
        with Image.open(io.BytesIO(image_bytes)) as image:
            return PreprocessResult(
                width=image.width,
                height=image.height,
                palette=(PaletteColor("#FFFFFF", 100.0),),
                ocr_text="",
            )

    monkeypatch.setattr(generate_route, "preprocess_image", fake)


def test_generate_from_figma_uses_the_approved_image(monkeypatch, figma_http, fake_preprocessing):
    seen = {}

    async def fake(image_bytes, mime, prompt, system_prompt):
        seen["bytes"] = image_bytes
        seen["prompt"] = prompt
        yield "```html\n<p>hi</p>\n```"

    monkeypatch.setattr(generate_route, "generate_from_image", fake)
    preview = client.post("/figma/preview", json={"figma_url": FRAME_URL}).json()
    calls_after_preview = len(figma_http)

    response = client.post(
        "/generate-from-figma",
        data={"preview_id": preview["preview_id"], "hint": "dark theme", "target": "html_tailwind"},
    )

    assert response.status_code == 200
    evts = events(response)
    assert evts[0]["type"] == "meta"
    assert evts[0]["width"] == 80
    assert evts[0]["height"] == 40
    assert len(evts[0]["project_id"]) == 32
    assert {"type": "code", "code": "<p>hi</p>"} in evts
    assert evts[-1] == {"type": "done"}
    assert seen["bytes"] == png_bytes()
    assert "dark theme" in seen["prompt"]
    assert len(figma_http) == calls_after_preview

    stored = client.get(f"/projects/{evts[0]['project_id']}/image")
    assert stored.content == png_bytes()


def test_generate_from_an_unknown_preview_is_not_found():
    response = client.post("/generate-from-figma", data={"preview_id": "a" * 32})
    assert response.status_code == 404


def test_generate_from_figma_rejects_an_unknown_target(figma_http, fake_preprocessing):
    preview = client.post("/figma/preview", json={"figma_url": FRAME_URL}).json()
    response = client.post(
        "/generate-from-figma",
        data={"preview_id": preview["preview_id"], "target": "nope"},
    )
    assert response.status_code == 400
