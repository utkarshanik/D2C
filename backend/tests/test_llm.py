import asyncio

import litellm

from app.config import settings
from app.services import llm


def test_extract_code_strips_fence():
    text = "```html\n<div>hi</div>\n```"
    assert llm.extract_code(text) == "<div>hi</div>"


def test_falls_back_when_primary_is_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "MAX_RETRIES", 0)  # no waiting in tests

    async def fake_stream(model, messages):
        if model == settings.PRIMARY_MODEL:
            raise litellm.RateLimitError("quota", llm_provider="gemini", model=model)
        yield "from-fallback"

    monkeypatch.setattr(llm, "_stream_once", fake_stream)

    async def collect():
        return "".join([d async for d in llm.stream_code([])])

    assert asyncio.run(collect()) == "from-fallback"