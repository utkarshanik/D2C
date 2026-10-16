import asyncio
import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.routes import generate as route
from app.services import refine
from app.services.renderer import RenderError

rng = np.random.default_rng(0)
NOISE = rng.integers(0, 256, (40, 60), dtype=np.uint8)


def png(arr) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


ORIGINAL = png(NOISE)
WORSE = png(255 - NOISE)                 # inverted, a very poor match
# A middling match (SSIM about 0.67, below the 0.95 target) so the loop has work to do.
MID = png((0.5 * NOISE + 0.5 * rng.integers(0, 256, NOISE.shape)).astype(np.uint8))
# A small brightness shift still scores about 0.98, which counts as close enough.
NEAR_PERFECT = png(np.clip(NOISE.astype(int) + 30, 0, 255).astype(np.uint8))


def collect(**kw):
    async def run():
        return [e async for e in refine.refine_events(ORIGINAL, "image/png", 60, 40, "<p>draft</p>", **kw)]

    return asyncio.run(run())


# ---- ssim_score -------------------------------------------------------------

def test_identical_images_score_one():
    assert refine.ssim_score(ORIGINAL, ORIGINAL) == pytest.approx(1.0)


def test_different_images_score_lower():
    assert refine.ssim_score(ORIGINAL, WORSE) < 0.5


def test_size_mismatch_raises():
    with pytest.raises(ValueError):
        refine.ssim_score(ORIGINAL, png(NOISE[:20]))


# ---- the loop ---------------------------------------------------------------

@pytest.fixture
def two_rounds(monkeypatch):
    monkeypatch.setattr(settings, "REFINE_ROUNDS", 2)
    monkeypatch.setattr(settings, "REFINE_TARGET_SCORE", 0.95)


def test_stops_without_calling_model_when_already_good(monkeypatch, two_rounds):
    async def render(html, w, h):
        return ORIGINAL

    async def model(*a, **k):
        raise AssertionError("model must not be called")

    monkeypatch.setattr(refine, "render_html", render)
    monkeypatch.setattr(refine, "generate_code", model)
    types = [e["type"] for e in collect()]
    assert "code" not in types and types.count("score") == 1


def test_keeps_an_improved_version(monkeypatch, two_rounds):
    async def render(html, w, h):
        return ORIGINAL if "GOOD" in html else MID

    async def model(system, prompt, images):
        return "```html\n<p>GOOD</p>\n```"

    monkeypatch.setattr(refine, "render_html", render)
    monkeypatch.setattr(refine, "generate_code", model)
    events = collect()
    assert {"type": "code", "code": "<p>GOOD</p>"} in events


def test_worse_fix_is_discarded_and_loop_stops(monkeypatch, two_rounds):
    calls = []

    async def render(html, w, h):
        return WORSE if "BAD" in html else MID

    async def model(system, prompt, images):
        calls.append(1)
        return "```html\n<p>BAD</p>\n```"

    monkeypatch.setattr(refine, "render_html", render)
    monkeypatch.setattr(refine, "generate_code", model)
    events = collect()
    assert not any(e["type"] == "code" for e in events)
    assert len(calls) == 1  # did not keep asking after a worse result


def test_hint_reaches_the_refine_prompt(monkeypatch, two_rounds):
    seen = {}

    async def render(html, w, h):
        return MID

    async def model(system, prompt, images):
        seen["prompt"], seen["n_images"] = prompt, len(images)
        return "```html\n<p>x</p>\n```"

    monkeypatch.setattr(refine, "render_html", render)
    monkeypatch.setattr(refine, "generate_code", model)
    collect(hint="light theme")
    assert "light theme" in seen["prompt"] and seen["n_images"] == 2


def test_render_failure_skips_refinement(monkeypatch, two_rounds):
    async def render(html, w, h):
        raise RenderError("nope")

    monkeypatch.setattr(refine, "render_html", render)
    events = collect()
    assert [e["type"] for e in events] == ["status", "status"]


# ---- wired into /generate ---------------------------------------------------

def _post(monkeypatch, refine_fake):
    async def draft(image_bytes, mime, prompt, system_prompt):
        yield "```html\n<p>draft</p>\n```"

    monkeypatch.setattr(settings, "REFINE_ROUNDS", 1)
    monkeypatch.setattr(route, "generate_from_image", draft)
    monkeypatch.setattr(route, "refine_events", refine_fake)
    r = TestClient(app).post("/generate", files={"image": ("a.png", ORIGINAL, "image/png")})
    return [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith("data: ")]


def test_route_streams_refine_events_before_done(monkeypatch):
    async def fake(*a, **k):
        yield {"type": "score", "round": 0, "score": 0.5}
        yield {"type": "code", "code": "<p>better</p>"}

    evts = _post(monkeypatch, fake)
    assert evts[-1] == {"type": "done"}
    assert {"type": "code", "code": "<p>better</p>"} in evts


def test_refine_crash_keeps_first_draft(monkeypatch):
    async def fake(*a, **k):
        raise RuntimeError("boom")
        yield

    evts = _post(monkeypatch, fake)
    assert {"type": "code", "code": "<p>draft</p>"} in evts
    assert evts[-1] == {"type": "done"}
    assert not any(e["type"] == "error" for e in evts)


def test_near_perfect_draft_is_left_alone(monkeypatch, two_rounds):
    async def render(html, w, h):
        return NEAR_PERFECT

    async def model(*a, **k):
        raise AssertionError("model must not be called")

    monkeypatch.setattr(refine, "render_html", render)
    monkeypatch.setattr(refine, "generate_code", model)
    assert not any(e["type"] == "code" for e in collect())