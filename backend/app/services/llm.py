import asyncio
import base64
import logging
from typing import AsyncIterator

import litellm

from app.config import settings

log = logging.getLogger(__name__)

# litellm turns every provider's errors into these common types, so one
# except clause covers Gemini quota errors, Ollama being down, timeouts, etc.
RETRYABLE = (
    litellm.RateLimitError,          # 429: free-tier quota hit
    litellm.ServiceUnavailableError, # 503: provider overloaded
    litellm.Timeout,
    litellm.APIConnectionError,      # e.g. Ollama not running
)


def to_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    # base64 (stdlib): the request body is JSON text, so image bytes must be
    # encoded as text to travel inside it.
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"


def build_messages(system_prompt: str, user_text: str, images: list[tuple[bytes, str]]) -> list[dict]:
    """Build one chat request: system rules + user text + one or more (bytes, mime) images."""
    content = [{"type": "text", "text": user_text}]
    for img, mime in images:
        content.append({"type": "image_url", "image_url": {"url": to_data_url(img, mime)}})
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]


def _model_kwargs(model: str) -> dict:
    kwargs = {"model": model}
    # pydantic-settings loads .env into `settings`, not into os.environ,
    # so we hand the Gemini key to litellm explicitly.
    if model.startswith("gemini/"):
        kwargs["api_key"] = settings.GEMINI_API_KEY
    return kwargs


async def _stream_once(model: str, messages: list[dict]) -> AsyncIterator[str]:
    # litellm.acompletion: the async call that works for any provider.
    # stream=True returns chunks as the model writes them (needed for real time).
    response = await litellm.acompletion(**_model_kwargs(model), messages=messages, stream=True)
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def stream_code(messages: list[dict]) -> AsyncIterator[str]:
    """Stream text from the primary model, retrying, then falling back.

    Failover is only safe before the first token is yielded. If a stream dies
    midway, switching models would splice two different answers together,
    so in that case the error is raised instead.
    """
    for model in (settings.PRIMARY_MODEL, settings.FALLBACK_MODEL):
        for attempt in range(settings.MAX_RETRIES + 1):
            started = False
            try:
                async for delta in _stream_once(model, messages):
                    started = True
                    yield delta
                return
            except RETRYABLE as exc:
                if started:
                    raise
                log.warning("%s failed (attempt %d): %s", model, attempt + 1, exc)
                if attempt < settings.MAX_RETRIES:
                    await asyncio.sleep(2**attempt)  # backoff: 1s, 2s, 4s...
        log.warning("Giving up on %s, trying next model", model)
    raise RuntimeError("All models failed")


async def generate_from_image(
    image_bytes: bytes, mime: str, prompt: str, system_prompt: str
) -> AsyncIterator[str]:
    """What the /generate route calls: one screenshot in, streamed text out."""
    messages = build_messages(system_prompt, prompt, [(image_bytes, mime)])
    async for delta in stream_code(messages):
        yield delta


async def generate_code(system_prompt: str, user_text: str, images: list[tuple[bytes, str]]) -> str:
    """Non-streaming wrapper for callers that need the whole answer (the refine loop later)."""
    messages = build_messages(system_prompt, user_text, images)
    return "".join([delta async for delta in stream_code(messages)])