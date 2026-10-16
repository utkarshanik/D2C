"""
Module 2: POST /generate

Receives a screenshot, validates it, and streams the generated code back as
Server-Sent Events (SSE). The route stays thin: validation + streaming only.
The real work happens in services/llm.py.

SSE events (each is one line: `data: {json}` followed by a blank line):
  {"type": "meta",   "width": 1280, "height": 720}   image size (the renderer needs it later)
  {"type": "status", "message": "..."}               progress text for the UI
  {"type": "chunk",  "delta": "..."}                 raw tokens as they arrive (live typing)
  {"type": "code",   "code": "<html>..."}            cleaned final code
  {"type": "score",  "round": 1, "score": 0.91}     SSIM match with the original (module 5)
  {"type": "done"}
  {"type": "error",  "message": "..."}
"""
import io
import json
import logging

# fastapi: APIRouter groups routes; UploadFile/File/Form read a multipart upload;
# HTTPException returns a proper HTTP error BEFORE streaming starts;
# StreamingResponse keeps the connection open and sends our generator's output.
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

# pillow: verify the upload really is an image, and read its size and true format.
# We don't trust the filename or the client's content-type header.
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.prompts.html_tailwind import SYSTEM_PROMPT, USER_PROMPT
from app.services.llm import generate_from_image
from app.services.postprocess import extract_html
from app.services.refine import refine_events

# Note: reading the upload needs the `python-multipart` package installed.
# FastAPI imports it behind the scenes; without it, this route fails at startup.

log = logging.getLogger(__name__)
router = APIRouter()

MAX_BYTES = 5 * 1024 * 1024  # 5 MB upload cap protects your server and your free quota
FORMAT_TO_MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def sse(payload: dict) -> str:
    """Format one SSE event. The blank line at the end is what ends the event."""
    return f"data: {json.dumps(payload)}\n\n"


def inspect_image(data: bytes) -> tuple[int, int, str]:
    """Return (width, height, mime) or raise HTTPException(400)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()  # fully decode so truncated or corrupt files fail here, not later
            mime = FORMAT_TO_MIME.get(img.format or "")
            if mime is None:
                raise HTTPException(400, "Unsupported image type. Use PNG, JPEG or WEBP.")
            return img.width, img.height, mime
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "File is not a valid image.")


@router.post("/generate")
async def generate(image: UploadFile = File(...), hint: str = Form("")):
    # Read at most MAX_BYTES + 1 so an oversized upload is detected without loading it all.
    data = await image.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image is too large (max 5 MB).")

    width, height, mime = inspect_image(data)
    prompt = USER_PROMPT + (f" Extra instructions: {hint.strip()}" if hint.strip() else "")

    async def event_stream():
        try:
            yield sse({"type": "meta", "width": width, "height": height})
            yield sse({"type": "status", "message": "Generating code..."})

            parts: list[str] = []
            async for delta in generate_from_image(data, mime, prompt, SYSTEM_PROMPT):
                parts.append(delta)
                yield sse({"type": "chunk", "delta": delta})

            first_draft = extract_html("".join(parts))
            yield sse({"type": "code", "code": first_draft})

            # Module 5: compare the render with the original and fix differences.
            # Failures here must not lose the first draft the user already has.
            if settings.REFINE_ROUNDS > 0:
                try:
                    async for evt in refine_events(data, mime, width, height, first_draft, hint.strip()):
                        yield sse(evt)
                except Exception:
                    log.exception("Refinement failed")
                    yield sse({"type": "status", "message": "Refinement skipped, showing the first draft."})

            yield sse({"type": "done"})
        except Exception:
            # Log the real error on the server; send a safe message to the browser.
            log.exception("Generation failed")
            yield sse({"type": "error", "message": "Generation failed. Please try again."})
        # If the browser disconnects, Starlette cancels this generator, which stops the
        # model call too, so we don't keep spending free-tier quota on an abandoned request.

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # no proxy buffering
    )