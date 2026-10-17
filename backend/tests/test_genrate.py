"""
Offline tests for module 2. The model call is faked, so no API quota is used.
Run from backend/ with:  python -m pytest -q
"""
import io
import json

import pytest

# fastapi.testclient: calls the app in-process (no server needed). It is built on httpx.
from fastapi.testclient import TestClient

# pillow: build small real images for the upload tests.
from PIL import Image

from app.main import app
from app.routes import generate as route
from app.services.postprocess import extract_html
from app.services.preprocess import PaletteColor, PreprocessResult

client = TestClient(app)


def png_bytes(size=(40, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return buf.getvalue()


def events(response) -> list[dict]:
    """Parse the SSE body into a list of event dicts."""
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.fixture(autouse=True)
def fake_preprocessing(monkeypatch):
    async def fake(image_bytes):
        with Image.open(io.BytesIO(image_bytes)) as image:
            return PreprocessResult(
                width=image.width,
                height=image.height,
                palette=(PaletteColor("#FFFFFF", 100.0),),
                ocr_text="",
            )

    monkeypatch.setattr(route, "preprocess_image", fake)


def fake_llm(parts):
    async def fake(image_bytes, mime, prompt, system_prompt):
        for p in parts:
            yield p

    return fake


# ---- extract_html -----------------------------------------------------------

def test_extract_fenced_block():
    assert extract_html("Sure!\n```html\n<h1>Hi</h1>\n```\nDone.") == "<h1>Hi</h1>"


def test_extract_without_fence():
    assert extract_html("<h1>Hi</h1>") == "<h1>Hi</h1>"


def test_extract_truncated_fence():
    assert extract_html("```html\n<h1>Hi") == "<h1>Hi"


# ---- /generate --------------------------------------------------------------

def test_streams_meta_chunks_code_done(monkeypatch):
    monkeypatch.setattr(route, "generate_from_image", fake_llm(["```html\n<p>", "hi</p>\n```"]))
    r = client.post("/generate", files={"image": ("a.png", png_bytes((40, 20)), "image/png")})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    evts = events(r)
    assert evts[0]["type"] == "meta"
    assert evts[0]["width"] == 40
    assert evts[0]["height"] == 20
    assert len(evts[0]["project_id"]) == 32
    assert [e["delta"] for e in evts if e["type"] == "chunk"] == ["```html\n<p>", "hi</p>\n```"]
    assert {"type": "code", "code": "<p>hi</p>"} in evts
    assert evts[-1] == {"type": "done"}


def test_hint_is_added_to_prompt(monkeypatch):
    seen = {}

    async def fake(image_bytes, mime, prompt, system_prompt):
        seen["prompt"] = prompt
        yield "x"

    monkeypatch.setattr(route, "generate_from_image", fake)
    client.post(
        "/generate",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"hint": "dark theme"},
    )
    assert "dark theme" in seen["prompt"]


def test_preprocessing_facts_are_added_to_prompt(monkeypatch):
    seen = {}

    async def preprocess(_image_bytes):
        return PreprocessResult(
            width=320,
            height=180,
            palette=(
                PaletteColor("#112233", 70.0),
                PaletteColor("#ABCDEF", 30.0),
            ),
            ocr_text="Create account\nWelcome back",
        )

    async def fake(image_bytes, mime, prompt, system_prompt):
        seen["prompt"] = prompt
        yield "x"

    monkeypatch.setattr(route, "preprocess_image", preprocess)
    monkeypatch.setattr(route, "generate_from_image", fake)

    client.post("/generate", files={"image": ("a.png", png_bytes(), "image/png")})

    assert "320px × 180px" in seen["prompt"]
    assert "#112233 (70.00%)" in seen["prompt"]
    assert "#ABCDEF (30.00%)" in seen["prompt"]
    assert "Create account\nWelcome back" in seen["prompt"]


def test_rejects_non_image():
    r = client.post("/generate", files={"image": ("a.png", b"not an image", "image/png")})
    assert r.status_code == 400


def test_rejects_oversized(monkeypatch):
    monkeypatch.setattr(route, "MAX_BYTES", 10)
    r = client.post("/generate", files={"image": ("a.png", png_bytes(), "image/png")})
    assert r.status_code == 413


def test_llm_failure_becomes_error_event(monkeypatch):
    async def broken(image_bytes, mime, prompt, system_prompt):
        raise RuntimeError("boom")
        yield  # makes this an async generator

    monkeypatch.setattr(route, "generate_from_image", broken)
    r = client.post("/generate", files={"image": ("a.png", png_bytes(), "image/png")})

    assert r.status_code == 200  # the stream already started, so the error travels as an event
    last = events(r)[-1]
    assert last["type"] == "error"
    assert "boom" not in last["message"]  # internal details are not leaked to the browser