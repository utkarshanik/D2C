"""Save screenshots and generated code, and rebuild a follow-up prompt from that history."""
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import Project, Version
from app.db.session import init_db, session

_ID = re.compile(r"^[0-9a-f]{32}$")
_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class ProjectNotFound(LookupError):
    pass


class NoCodeToEdit(ValueError):
    pass


@dataclass(frozen=True)
class EditContext:
    image: bytes
    mime: str
    width: int
    height: int
    code: str
    instruction: str
    target: str


def compose_follow_up(prior: list[str], instruction: str) -> str:
    """Put earlier requests in front of the new one so the model keeps work already applied."""
    instruction = instruction.strip()
    earlier = [item.strip() for item in prior if item and item.strip()]
    if not instruction or not earlier:
        return instruction
    lines = "\n".join(f"{index}. {text}" for index, text in enumerate(earlier, start=1))
    return (
        "Earlier requests already applied to the current code. "
        "Keep their results unless the new request changes them:\n"
        f"{lines}\n\n"
        f"New request:\n{instruction}"
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _data_root() -> Path:
    return Path(settings.DATA_DIR).resolve()


def _project_dir(project_id: str) -> Path:
    if not _ID.fullmatch(project_id):
        raise ProjectNotFound(project_id)
    root = (_data_root() / "projects").resolve()
    path = (root / project_id).resolve()
    if path.parent != root:
        raise ProjectNotFound(project_id)
    return path


def create_project(
    image: bytes,
    mime: str,
    width: int,
    height: int,
    hint: str,
    target: str = "html_tailwind",
) -> str:
    """Store the screenshot on disk and insert the project row. Returns the id."""
    init_db()
    project_id = uuid4().hex
    folder = _project_dir(project_id)
    folder.mkdir(parents=True, exist_ok=False)
    image_name = f"original.{_EXT.get(mime, 'img')}"
    (folder / image_name).write_bytes(image)
    try:
        with session() as db:
            db.add(Project(
                id=project_id,
                created_at=_utcnow(),
                width=width,
                height=height,
                mime=mime,
                image_name=image_name,
                hint=hint.strip(),
                target=target,
            ))
            db.commit()
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return project_id


def add_version(project_id: str, code: str, instruction: str) -> int:
    """Append the next version. Returns its number."""
    init_db()
    with session() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise ProjectNotFound(project_id)
        number = (db.scalar(
            select(Version.number)
            .where(Version.project_id == project_id)
            .order_by(Version.number.desc())
            .limit(1)
        ) or 0) + 1
        db.add(Version(
            project_id=project_id,
            number=number,
            created_at=_utcnow(),
            code=code,
            instruction=instruction.strip(),
        ))
        db.commit()
        return number


def delete_project(project_id: str) -> None:
    """Remove a project that never received code, including its screenshot."""
    if not _ID.fullmatch(project_id):
        return
    init_db()
    with session() as db:
        project = db.get(Project, project_id)
        if project is not None:
            db.delete(project)
            db.commit()
    folder = _data_root() / "projects" / project_id
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def _project_summary(project: Project) -> dict:
    return {
        "id": project.id,
        "created_at": project.created_at.isoformat(),
        "width": project.width,
        "height": project.height,
        "mime": project.mime,
        "hint": project.hint,
        "target": project.target,
        "version_count": len(project.versions),
    }


def _version_dict(version: Version) -> dict:
    return {
        "id": version.id,
        "number": version.number,
        "created_at": version.created_at.isoformat(),
        "code": version.code,
        "instruction": version.instruction,
    }


def list_projects() -> list[dict]:
    init_db()
    with session() as db:
        rows = db.scalars(
            select(Project)
            .options(selectinload(Project.versions))
            .order_by(Project.created_at.desc())
        ).all()
        return [_project_summary(project) for project in rows if project.versions]


def get_project(project_id: str) -> dict | None:
    if not _ID.fullmatch(project_id):
        return None
    init_db()
    with session() as db:
        project = db.scalar(
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.versions))
        )
        if project is None:
            return None
        body = _project_summary(project)
        body["versions"] = [_version_dict(version) for version in project.versions]
        return body


def read_image(project_id: str) -> tuple[bytes, str] | None:
    if not _ID.fullmatch(project_id):
        return None
    init_db()
    with session() as db:
        project = db.get(Project, project_id)
        if project is None:
            return None
        path = _project_dir(project_id) / project.image_name
        mime = project.mime
    if not path.is_file():
        return None
    return path.read_bytes(), mime


def prepare_edit(project_id: str, instruction: str, code: str) -> EditContext:
    """Load the stored screenshot and the version the follow-up should start from.

    `code` is the version currently on screen (after undo, that may not be the latest).
    Earlier instructions up to that version are included in the prompt.
    """
    if not _ID.fullmatch(project_id):
        raise ProjectNotFound(project_id)
    init_db()
    with session() as db:
        project = db.scalar(
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.versions))
        )
        if project is None:
            raise ProjectNotFound(project_id)
        if not project.versions:
            raise NoCodeToEdit(project_id)
        image_name = project.image_name
        mime = project.mime
        width = project.width
        height = project.height
        target = project.target or "html_tailwind"
        versions = list(project.versions)

    chosen = versions[-1]
    supplied = code.strip()
    if supplied:
        for version in reversed(versions):
            if version.code == supplied:
                chosen = version
                break
        else:
            chosen = None

    if chosen is None:
        base_code = supplied
        prior = [version.instruction for version in versions]
    else:
        base_code = chosen.code
        prior = [version.instruction for version in versions if version.number <= chosen.number]

    image_path = _project_dir(project_id) / image_name
    if not image_path.is_file():
        raise ProjectNotFound(project_id)
    return EditContext(
        image=image_path.read_bytes(),
        mime=mime,
        width=width,
        height=height,
        code=base_code,
        instruction=compose_follow_up(prior, instruction),
        target=target,
    )
