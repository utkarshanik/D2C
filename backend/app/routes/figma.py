"""Figma link preview, then generate from the image the user approved.

POST /figma/preview                  render a frame and store it for a short time
GET  /figma/preview/{id}/image       the rendered frame
POST /generate-from-figma            same SSE flow as /generate, no second Figma call
"""
import asyncio
import logging

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.routes.generate import stream_generation
from app.services.figma import (
    FigmaLinkError,
    FigmaRequestError,
    RENDER_FAILED,
    load_preview,
    parse_figma_url,
    render_frame,
    save_preview,
)
from app.services.images import inspect_image
from app.targets import UnknownTarget, get_target

log = logging.getLogger(__name__)
router = APIRouter()


class PreviewRequest(BaseModel):
    figma_url: str


@router.post("/figma/preview")
async def create_preview(body: PreviewRequest):
    try:
        file_key, node_id = parse_figma_url(body.figma_url)
    except FigmaLinkError as err:
        raise HTTPException(400, err.message)

    try:
        image, name = await render_frame(file_key, node_id)
    except FigmaRequestError as err:
        raise HTTPException(err.status_code, err.message)
    except Exception:
        log.exception("Figma preview failed")
        raise HTTPException(502, "Could not load a preview from Figma. Try again.")

    try:
        width, height, mime = inspect_image(image)
    except HTTPException:
        raise HTTPException(400, RENDER_FAILED)

    try:
        preview_id = await asyncio.to_thread(save_preview, image, mime, width, height, name)
    except OSError:
        log.exception("Could not store Figma preview")
        raise HTTPException(502, "Could not load a preview from Figma. Try again.")

    return {"preview_id": preview_id, "width": width, "height": height, "name": name}


@router.get("/figma/preview/{preview_id}/image")
def preview_image(preview_id: str):
    found = load_preview(preview_id)
    if found is None:
        raise HTTPException(404, "Preview not found.")
    return Response(content=found.image, media_type=found.mime, headers={"Cache-Control": "no-store"})


@router.post("/generate-from-figma")
async def generate_from_figma(
    preview_id: str = Form(...),
    hint: str = Form(""),
    target: str = Form(""),
):
    found = await asyncio.to_thread(load_preview, preview_id)
    if found is None:
        raise HTTPException(404, "That preview expired. Preview the link again.")
    try:
        chosen = get_target(target)
    except UnknownTarget:
        raise HTTPException(400, "Unknown target. Use html_tailwind or react_mui.")
    # The image on disk is the one the user already saw. Do not call Figma here.
    return stream_generation(found.image, found.width, found.height, found.mime, hint, chosen)
