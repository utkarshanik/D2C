"""
Module 2: POST /generate

Receives a screenshot, validates it, and streams the generated code back as
Server-Sent Events (SSE). The route stays thin: validation + streaming only.
The real work happens in services/llm.py.

SSE events (each is one line: `data: {json}` followed by a blank line):
  {"type": "meta",   "width": 1280, "height": 720, "project_id": "<id>"}
  {"type": "status", "message": "..."}               progress text for the UI
  {"type": "chunk",  "delta": "..."}                 raw tokens as they arrive (live typing)
  {"type": "code",   "code": "<html>..."}            cleaned final code
  {"type": "done"}
  {"type": "error",  "message": "..."}
"""
import asyncio
import json
import logging

# fastapi: APIRouter groups routes; UploadFile/File/Form read a multipart upload;
# HTTPException returns a proper HTTP error BEFORE streaming starts;
# StreamingResponse keeps the connection open and sends our generator's output.
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.services.images import MAX_BYTES, inspect_image
from app.services.llm import generate_from_image
from app.services.postprocess import extract_code
from app.services.preprocess import preprocess_image
from app.services.projects import add_version, create_project, delete_project
from app.targets import Target, UnknownTarget, get_target

# Note: reading the upload needs the `python-multipart` package installed.
# FastAPI imports it behind the scenes; without it, this route fails at startup.

log = logging.getLogger(__name__)
router = APIRouter()


def sse(payload: dict) -> str:
    """Format one SSE event. The blank line at the end is what ends the event."""
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/generate")
async def generate(
    image: UploadFile = File(...),
    hint: str = Form(""),
    target: str = Form(""),
):
    # Read at most MAX_BYTES + 1 so an oversized upload is detected without loading it all.
    data = await image.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image is too large (max 5 MB).")

    width, height, mime = inspect_image(data)
    try:
        chosen = get_target(target)
    except UnknownTarget:
        raise HTTPException(400, "Unknown target. Use html_tailwind or react_mui.")
    return stream_generation(data, width, height, mime, hint, chosen)


def stream_generation(
    data: bytes,
    width: int,
    height: int,
    mime: str,
    hint: str,
    chosen: Target,
) -> StreamingResponse:
    """Stream one first draft from image bytes. Shared by the screenshot and Figma routes."""

    async def event_stream():
        # Created before any tokens so a failed or abandoned run can be removed again.
        project_id = None
        saved = False
        try:
            project_id = await asyncio.to_thread(
                create_project, data, mime, width, height, hint, chosen.id
            )
            yield sse({
                "type": "meta",
                "width": width,
                "height": height,
                "project_id": project_id,
                "target": chosen.id,
            })
            yield sse({"type": "status", "message": "Analyzing colors and text..."})

            measurements = await preprocess_image(data)
            prompt = chosen.build_user_prompt(
                width=measurements.width,
                height=measurements.height,
                palette=measurements.palette,
                ocr_text=measurements.ocr_text,
                hint=hint,
            )
            log.info("Generate prompt:\n%s", prompt)

            yield sse({"type": "status", "message": "Generating code..."})

            parts: list[str] = []
            async for delta in generate_from_image(data, mime, prompt, chosen.system_prompt):
                parts.append(delta)
                yield sse({"type": "chunk", "delta": delta})

            code = extract_code("".join(parts))
            if code.strip():
                await asyncio.to_thread(add_version, project_id, code, hint)
                saved = True
            yield sse({"type": "code", "code": code})
            yield sse({"type": "done"})
        except Exception:
            # Log the real error on the server; send a safe message to the browser.
            log.exception("Generation failed")
            yield sse({"type": "error", "message": "Generation failed. Please try again."})
        finally:
            if project_id and not saved:
                await asyncio.to_thread(delete_project, project_id)
        # If the browser disconnects, Starlette cancels this generator, which stops the
        # model call too, so we don't keep spending free-tier quota on an abandoned request.

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # no proxy buffering
    )