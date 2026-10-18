"""Project and version history.

GET  /projects                  saved screenshots that have at least one version
GET  /projects/{id}             one project, including every version's code
GET  /projects/{id}/image       the original screenshot
POST /projects/{id}/edit        follow-up edit (SSE), using the stored image and history
"""
import asyncio
import logging

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.routes import generate as gen
from app.routes.refine import MAX_CODE_BYTES, MAX_INSTRUCTION_CHARS
from app.services import projects as store
from app.services.refine import refine_step

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/projects")
def list_projects():
    return store.list_projects()


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project


@router.get("/projects/{project_id}/image")
def project_image(project_id: str):
    found = store.read_image(project_id)
    if found is None:
        raise HTTPException(404, "Project not found.")
    data, mime = found
    return Response(content=data, media_type=mime)


@router.post("/projects/{project_id}/edit")
async def edit_project(
    project_id: str,
    instruction: str = Form(""),
    code: str = Form(""),
):
    instruction = instruction.strip()
    if len(instruction) > MAX_INSTRUCTION_CHARS:
        raise HTTPException(400, f"Instruction is too long (max {MAX_INSTRUCTION_CHARS} characters).")
    if code and len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise HTTPException(413, "Code is too large to refine.")

    try:
        ctx = await asyncio.to_thread(store.prepare_edit, project_id, instruction, code)
    except store.ProjectNotFound:
        raise HTTPException(404, "Project not found.")
    except store.NoCodeToEdit:
        raise HTTPException(400, "There is no code to refine yet.")

    async def event_stream():
        try:
            async for evt in refine_step(
                ctx.image, ctx.mime, ctx.width, ctx.height, ctx.code, ctx.instruction, target_id=ctx.target
            ):
                if (
                    evt.get("type") == "code"
                    and str(evt.get("code", "")).strip()
                    and evt["code"] != ctx.code
                ):
                    await asyncio.to_thread(store.add_version, project_id, evt["code"], instruction)
                yield gen.sse(evt)
            yield gen.sse({"type": "done"})
        except Exception:
            log.exception("Follow-up edit failed")
            yield gen.sse({"type": "error", "message": "Refinement failed. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
