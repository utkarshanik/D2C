"""Module 5: refine, one step per button click.

The user decides when to refine, so one call = at most one model call.

Two modes, depending on whether the user typed an instruction:
  * no instruction: "match the original". Render the current code, score it
    (SSIM) against the original, and if it is not close enough ask the model to
    fix the differences. Keep the fix only if it scores higher.
  * with instruction: "apply my change". The user wants a deliberate change, so
    similarity to the original cannot judge the result. Apply it and return it;
    the frontend keeps the previous version so the user can undo.
"""
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

# numpy: pixel data as arrays, which is the form scikit-image works on.
import numpy as np

# pillow: open the two PNG/JPEG byte strings and flatten them to grayscale.
from PIL import Image

# scikit-image: structural_similarity gives the SSIM score (1.0 = identical).
from skimage.metrics import structural_similarity

from app.config import settings
from app.prompts.html_tailwind import SYSTEM_PROMPT
from app.prompts.refine import EDIT_PROMPT, MATCH_PROMPT
from app.services.llm import generate_code
from app.services.postprocess import extract_html
from app.services.renderer import RenderError, render_html

log = logging.getLogger(__name__)

_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class _Dump:
    """Optional debug output. When REFINE_DEBUG_DIR is set, every file the loop
    sends to or receives from the model is saved in debug/<timestamp>/ so you can
    open the images and read the prompt and reply. Off (a no-op) by default,
    because it stores your screenshots on disk.
    """

    def __init__(self, base: str):
        self.dir = None
        if base:
            self.dir = Path(base) / datetime.now().strftime("%Y%m%d-%H%M%S")
            self.dir.mkdir(parents=True, exist_ok=True)
            log.info("Refine debug files: %s", self.dir.resolve())

    def save(self, name: str, content: bytes | str) -> None:
        if self.dir is None:
            return
        path = self.dir / name
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)


def _to_gray(data: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGBA")
        # Transparent pixels would turn black in grayscale; put them on white,
        # which is what a browser shows behind a transparent image.
        white = Image.new("RGBA", img.size, "white")
        return np.asarray(Image.alpha_composite(white, img).convert("L"))


def ssim_score(original: bytes, render: bytes) -> float:
    """SSIM between two images of the SAME size. 1.0 means identical."""
    a, b = _to_gray(original), _to_gray(render)
    if a.shape != b.shape:
        # SSIM compares pixel by pixel, so different sizes cannot be scored.
        raise ValueError(f"Image sizes differ: {a.shape[::-1]} vs {b.shape[::-1]}")
    win = min(7, a.shape[0], a.shape[1])  # SSIM looks at small windows; keep it valid for tiny images
    if win % 2 == 0:
        win -= 1
    if win < 3:
        return 1.0 if np.array_equal(a, b) else 0.0
    return float(structural_similarity(a, b, win_size=win, data_range=255))


async def refine_step(
    original: bytes, mime: str, width: int, height: int, code: str, instruction: str = ""
) -> AsyncIterator[dict]:
    """Yield SSE-ready event dicts: status, score (match mode only) and code (when changed)."""
    instruction = instruction.strip()
    dump = _Dump(settings.REFINE_DEBUG_DIR)
    dump.save(f"original.{_EXT.get(mime, 'img')}", original)
    dump.save("current.html", code)

    yield {"type": "status", "message": "Rendering the current version..."}
    try:
        render = await render_html(code, width, height)
    except RenderError:
        yield {"type": "status", "message": "Could not render the current version, so nothing was changed."}
        return
    dump.save("current_render.png", render)

    best_score = None
    if not instruction:
        best_score = ssim_score(original, render)
        yield {"type": "score", "round": 0, "score": round(best_score, 3)}
        if best_score >= settings.REFINE_TARGET_SCORE:
            yield {"type": "status", "message": "Already close to the original, nothing to fix."}
            return
        prompt = MATCH_PROMPT.format(code=code)
        yield {"type": "status", "message": "Asking the model to fix the differences..."}
    else:
        prompt = EDIT_PROMPT.format(code=code, instruction=instruction)
        yield {"type": "status", "message": "Applying your change..."}

    # Image 1 = original, image 2 = current render (the order both prompts describe).
    images = [(original, mime), (render, "image/png")]
    log.info(
        "Refine (%s): sending %d images (%s), prompt %d chars%s",
        "match" if not instruction else "edit", len(images),
        ", ".join(f"{len(b)} bytes {m}" for b, m in images), len(prompt),
        f", current score {best_score:.3f}" if best_score is not None else "",
    )
    dump.save(f"sent_image1_original.{_EXT.get(mime, 'img')}", original)
    dump.save("sent_image2_render.png", render)
    dump.save("prompt.txt", f"SYSTEM:\n{SYSTEM_PROMPT}\n\nUSER:\n{prompt}")

    reply = await generate_code(SYSTEM_PROMPT, prompt, images)
    dump.save("reply.txt", reply)  # the raw reply, before the fence is stripped
    candidate = extract_html(reply)
    dump.save("candidate.html", candidate)
    if not candidate.strip():
        yield {"type": "status", "message": "The model returned no code, so nothing was changed."}
        return

    if instruction:
        yield {"type": "code", "code": candidate}
        return

    try:
        cand_render = await render_html(candidate, width, height)
    except RenderError:
        yield {"type": "status", "message": "The fix could not be rendered, so it was discarded."}
        return
    dump.save("candidate_render.png", cand_render)
    cand_score = ssim_score(original, cand_render)
    yield {"type": "score", "round": 1, "score": round(cand_score, 3)}
    if cand_score > best_score:
        yield {"type": "code", "code": candidate}
    else:
        yield {"type": "status", "message": "No improvement, keeping the current version."}