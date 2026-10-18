"""Turn a Figma frame link into a temporary image, without calling Figma again later.

Preview downloads the render once. Generate reads that file from disk, so the code
matches the image the user approved and a second render does not spend Figma quota.
"""
import asyncio
import json
import logging
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import httpx

from app.config import settings
from app.services.images import MAX_BYTES

log = logging.getLogger(__name__)

# Same shape as a project id: 32 lowercase hex chars, so a preview id cannot be a path.
_ID = re.compile(r"^[0-9a-f]{32}$")
_FILE_KEY = re.compile(r"^[A-Za-z0-9]{1,128}$")
_NODE_ID = re.compile(r"^\d+:\d+$")
_IMAGE_FILE = re.compile(r"^image\.(png|jpg|webp)$")
_KINDS = {"design", "file", "proto", "board", "slides"}
_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

TTL_SECONDS = 30 * 60

BAD_LINK = "That is not a Figma design link."
NO_NODE = "The link has no frame. In Figma, select a frame and copy the link to that frame."
NO_ACCESS = "No access to that Figma file."
NOT_CONFIGURED = "Figma access is not set up on the server."
TOO_LARGE = "Image is too large (max 5 MB)."
RENDER_FAILED = "Figma could not render that frame."
BUSY = "Figma is busy. Try again in a moment."
GENERIC = "Could not load a preview from Figma. Try again."


class FigmaLinkError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class FigmaRequestError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class StoredPreview:
    preview_id: str
    image: bytes
    mime: str
    width: int
    height: int
    name: str


def parse_figma_url(raw: str) -> tuple[str, str]:
    """Return (file_key, node_id) or raise FigmaLinkError with a safe message.

    Figma copies links like /design/<fileKey>/Name?node-id=1-2. The API wants the
    colon form 1:2. A branch link's branch key is the file key the API accepts.
    """
    text = (raw or "").strip()
    if not text or len(text) > 2048 or any(ord(ch) < 32 for ch in text):
        raise FigmaLinkError(BAD_LINK)
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in {"figma.com", "www.figma.com"}:
        raise FigmaLinkError(BAD_LINK)

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] not in _KINDS:
        raise FigmaLinkError(BAD_LINK)
    file_key = parts[3] if len(parts) >= 4 and parts[2] == "branch" else parts[1]
    if not _FILE_KEY.fullmatch(file_key):
        raise FigmaLinkError(BAD_LINK)

    values = parse_qs(parsed.query, keep_blank_values=True).get("node-id") or []
    if not values or not values[0].strip():
        raise FigmaLinkError(NO_NODE)
    # The link uses a hyphen where the API uses a colon: "12-34" -> "12:34".
    node_id = unquote(values[0].strip()).split(",")[0].strip().replace("-", ":")
    if not _NODE_ID.fullmatch(node_id):
        raise FigmaLinkError(NO_NODE)
    return file_key, node_id


def _allowed_host(host: str | None) -> bool:
    if not host:
        return False
    name = host.lower().rstrip(".")
    if name == "figma.com" or name.endswith(".figma.com"):
        return True
    return name.endswith(".amazonaws.com") and "figma" in name


async def _guard_request(request: httpx.Request) -> None:
    # The image URL comes from Figma's JSON. Refuse anything that is not Figma's own host.
    if request.url.scheme != "https" or not _allowed_host(request.url.host):
        raise FigmaRequestError(RENDER_FAILED, 400)


def build_client(transport: httpx.BaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        event_hooks={"request": [_guard_request]},
    )


def _clean_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(ch for ch in value if ch >= " " and ch != "\x7f").strip()
    return cleaned[:200]


def _name_from_body(body: object, node_id: str) -> str:
    if not isinstance(body, dict):
        return ""
    nodes = body.get("nodes")
    if not isinstance(nodes, dict):
        return ""
    node = nodes.get(node_id)
    if not isinstance(node, dict):
        return ""
    document = node.get("document")
    if not isinstance(document, dict):
        return ""
    return _clean_name(document.get("name"))


async def _read_json(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    params: dict[str, str],
) -> tuple[int, object]:
    try:
        res = await client.get(
            f"https://api.figma.com{path}",
            params=params,
            headers={"X-Figma-Token": token},
        )
    except httpx.HTTPError:
        log.warning("Figma request failed")
        raise FigmaRequestError(GENERIC, 502)
    try:
        body = res.json()
    except ValueError:
        body = None
    return res.status_code, body


def _raise_for_api_status(status: int) -> None:
    if status in (401, 403, 404):
        raise FigmaRequestError(NO_ACCESS, 403)
    if status == 429:
        raise FigmaRequestError(BUSY, 429)
    if status != 200:
        raise FigmaRequestError(RENDER_FAILED, 400)


async def _image_url(client: httpx.AsyncClient, token: str, file_key: str, node_id: str) -> str:
    status, body = await _read_json(
        client,
        f"/v1/images/{file_key}",
        token,
        {"ids": node_id, "format": "png", "scale": "1"},
    )
    _raise_for_api_status(status)
    if not isinstance(body, dict) or body.get("err"):
        raise FigmaRequestError(RENDER_FAILED, 400)
    images = body.get("images")
    url = images.get(node_id) if isinstance(images, dict) else None
    if not isinstance(url, str) or not url:
        raise FigmaRequestError(RENDER_FAILED, 400)
    return url


async def _frame_name(client: httpx.AsyncClient, token: str, file_key: str, node_id: str) -> str:
    """Best-effort frame title. A failure here still leaves the rendered image usable."""
    try:
        status, body = await _read_json(
            client,
            f"/v1/files/{file_key}/nodes",
            token,
            {"ids": node_id},
        )
    except FigmaRequestError:
        return ""
    if status != 200:
        return ""
    return _name_from_body(body, node_id)


async def _download(client: httpx.AsyncClient, url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not _allowed_host(parsed.hostname):
        raise FigmaRequestError(RENDER_FAILED, 400)
    try:
        async with client.stream("GET", url) as res:
            if res.status_code != 200:
                raise FigmaRequestError(RENDER_FAILED, 400)
            declared = res.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > MAX_BYTES:
                raise FigmaRequestError(TOO_LARGE, 413)
            chunks: list[bytes] = []
            total = 0
            async for chunk in res.aiter_bytes():
                total += len(chunk)
                if total > MAX_BYTES:
                    raise FigmaRequestError(TOO_LARGE, 413)
                chunks.append(chunk)
    except FigmaRequestError:
        raise
    except httpx.HTTPError:
        log.warning("Figma image download failed")
        raise FigmaRequestError(GENERIC, 502)
    return b"".join(chunks)


async def render_frame(file_key: str, node_id: str) -> tuple[bytes, str]:
    """Ask Figma to render one frame. Returns (png bytes, frame name)."""
    token = settings.FIGMA_ACCESS_TOKEN.strip()
    if not token:
        raise FigmaRequestError(NOT_CONFIGURED, 400)

    async with build_client() as client:
        url, name = await asyncio.gather(
            _image_url(client, token, file_key, node_id),
            _frame_name(client, token, file_key, node_id),
        )
        image = await _download(client, url)
    return image, name


def _previews_root() -> Path:
    root = (Path(settings.DATA_DIR).resolve() / "figma-previews").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _preview_dir(preview_id: str) -> Path:
    if not _ID.fullmatch(preview_id):
        raise ValueError(preview_id)
    root = _previews_root()
    path = (root / preview_id).resolve()
    if path.parent != root:
        raise ValueError(preview_id)
    return path


def purge_expired_previews(max_age_seconds: int = TTL_SECONDS) -> None:
    """Delete previews nobody confirmed. Called when a new preview is saved."""
    root = _previews_root()
    cutoff = time.time() - max_age_seconds
    for child in root.iterdir():
        if not child.is_dir() or not _ID.fullmatch(child.name):
            continue
        try:
            expired = child.stat().st_mtime < cutoff
        except OSError:
            continue
        if expired:
            shutil.rmtree(child, ignore_errors=True)


def save_preview(image: bytes, mime: str, width: int, height: int, name: str) -> str:
    purge_expired_previews()
    preview_id = uuid4().hex
    folder = _preview_dir(preview_id)
    folder.mkdir(parents=True, exist_ok=False)
    file_name = f"image.{_EXT.get(mime, 'png')}"
    (folder / file_name).write_bytes(image)
    meta = {"width": width, "height": height, "mime": mime, "name": name, "file": file_name}
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return preview_id


def load_preview(preview_id: str) -> StoredPreview | None:
    if not _ID.fullmatch(preview_id):
        return None
    try:
        folder = _preview_dir(preview_id)
    except ValueError:
        return None
    if not folder.is_dir():
        return None
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict):
        return None
    file_name = meta.get("file")
    mime = meta.get("mime")
    width = meta.get("width")
    height = meta.get("height")
    if not isinstance(file_name, str) or not _IMAGE_FILE.fullmatch(file_name):
        return None
    if mime not in _EXT or not isinstance(width, int) or not isinstance(height, int):
        return None
    image_path = (folder / file_name).resolve()
    if image_path.parent != folder or not image_path.is_file():
        return None
    try:
        data = image_path.read_bytes()
    except OSError:
        return None
    return StoredPreview(
        preview_id=preview_id,
        image=data,
        mime=mime,
        width=width,
        height=height,
        name=_clean_name(meta.get("name")),
    )
