"""POST /render: a test route for module 4. Send HTML + size, get a PNG back.

Module 5 calls render_html() directly, so this route is for checking the
renderer by hand (e.g. from /docs) and can be removed later.
"""
# fastapi: Form reads form fields; ge/le make FastAPI reject bad sizes with a 422
# before our code runs. Response returns raw bytes with a content type.
from fastapi import APIRouter, Form, HTTPException, Response

from app.services.react_harness import build_preview_html
from app.services.renderer import MAX_DIM, RenderError, render_html

router = APIRouter()

MAX_HTML_BYTES = 500_000  # generated pages are small; this stops abuse


@router.post("/render")
async def render(
    html: str = Form(...),
    width: int = Form(..., ge=1, le=MAX_DIM),
    height: int = Form(..., ge=1, le=MAX_DIM),
):
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise HTTPException(status_code=413, detail="HTML is too large")
    try:
        png = await render_html(html, width, height)
    except RenderError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return Response(content=png, media_type="image/png")


@router.post("/preview-html")
def preview_html(code: str = Form(...)):
    """Turn a React component into one HTML page the preview iframe can show.

    Sandpack's remote bundler was staying on "Starting" and leaving a blank
    frame. This is the same page the screenshot step already builds.
    """
    if not code.strip():
        raise HTTPException(status_code=400, detail="There is no code to preview.")
    if len(code.encode("utf-8")) > MAX_HTML_BYTES:
        raise HTTPException(status_code=413, detail="Code is too large to preview.")
    return Response(content=build_preview_html(code), media_type="text/html")