"""
Module 5: POST /refine

Called when the user clicks the Refine button. The browser sends the original
screenshot again plus the current code, so the server stays stateless.

SSE events: status, score (match mode only), code (only if something changed),
done, error. Same format as /generate.
"""
import logging

# fastapi: same building blocks as /generate (UploadFile/File/Form for the
# multipart body, HTTPException for errors before streaming, StreamingResponse).
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

# Reuse the upload checks and the SSE formatter from the generate route. We reach
# them through the module so a changed limit (or a test patch) applies here too.
from app.routes import generate as gen
from app.services.refine import refine_step

log = logging.getLogger(__name__)
router = APIRouter()

MAX_CODE_BYTES = 500_000  # generated pages are small; this stops abuse
MAX_INSTRUCTION_CHARS = 1000


@router.post("/refine")
async def refine(
    image: UploadFile = File(...),
    code: str = Form(...),
    instruction: str = Form(""),
):
    data = await image.read(gen.MAX_BYTES + 1)
    if len(data) > gen.MAX_BYTES:
        raise HTTPException(413, "Image is too large (max 5 MB).")
    width, height, mime = gen.inspect_image(data)

    if not code.strip():
        raise HTTPException(400, "There is no code to refine yet.")
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise HTTPException(413, "Code is too large to refine.")
    instruction = instruction.strip()
    if len(instruction) > MAX_INSTRUCTION_CHARS:
        raise HTTPException(400, f"Instruction is too long (max {MAX_INSTRUCTION_CHARS} characters).")

    async def event_stream():
        try:
            async for evt in refine_step(data, mime, width, height, code, instruction):
                yield gen.sse(evt)
            yield gen.sse({"type": "done"})
        except Exception:
            log.exception("Refine failed")
            yield gen.sse({"type": "error", "message": "Refinement failed. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )