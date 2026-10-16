"""Module 5: the refine loop.

draft code -> render it -> score it against the original -> if it is not close
enough, show the model BOTH images and ask for a fix -> render and score the fix
-> keep whichever version scores best. Stops early when it is good enough, when
a round brings no improvement, or after REFINE_ROUNDS rounds.

Each round costs one model call, and free tiers are limited, so the loop never
runs longer than it has to.
"""
import io
import logging
from typing import AsyncIterator

# numpy: pixel data as arrays, which is the form scikit-image works on.
import numpy as np

# pillow: open the two PNG/JPEG byte strings and flatten them to grayscale.
from PIL import Image

# scikit-image: structural_similarity gives the SSIM score (1.0 = identical).
from skimage.metrics import structural_similarity

from app.config import settings
from app.prompts.html_tailwind import SYSTEM_PROMPT
from app.prompts.refine import HINT_BLOCK, REFINE_PROMPT
from app.services.llm import generate_code
from app.services.postprocess import extract_html
from app.services.renderer import RenderError, render_html

log = logging.getLogger(__name__)


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


async def refine_events(
    original: bytes, mime: str, width: int, height: int, code: str, hint: str = ""
) -> AsyncIterator[dict]:
    """Yield SSE-ready event dicts: status, score and (only when improved) code."""
    rounds = settings.REFINE_ROUNDS
    target = settings.REFINE_TARGET_SCORE

    yield {"type": "status", "message": "Rendering the draft to compare it..."}
    try:
        render = await render_html(code, width, height)
    except RenderError:
        yield {"type": "status", "message": "Could not render the draft, so refinement was skipped."}
        return

    best_code, best_render = code, render
    best_score = ssim_score(original, render)
    yield {"type": "score", "round": 0, "score": round(best_score, 3)}

    for round_no in range(1, rounds + 1):
        if best_score >= target:
            yield {"type": "status", "message": "Close enough to the original."}
            break

        yield {"type": "status", "message": f"Refining ({round_no}/{rounds})..."}
        prompt = REFINE_PROMPT.format(
            code=best_code, hint_block=HINT_BLOCK.format(hint=hint) if hint else ""
        )
        # Image 1 = target, image 2 = current render (the order the prompt describes).
        reply = await generate_code(
            SYSTEM_PROMPT, prompt, [(original, mime), (best_render, "image/png")]
        )
        candidate = extract_html(reply)

        try:
            cand_render = await render_html(candidate, width, height)
        except RenderError:
            yield {"type": "status", "message": "The fix could not be rendered, so it was discarded."}
            break
        cand_score = ssim_score(original, cand_render)
        yield {"type": "score", "round": round_no, "score": round(cand_score, 3)}

        if cand_score > best_score:
            best_code, best_render, best_score = candidate, cand_render, cand_score
            yield {"type": "code", "code": best_code}
        else:
            # A "fix" that looks worse is thrown away, and we stop: asking again
            # with the same inputs would likely repeat the mistake and burn quota.
            yield {"type": "status", "message": "No improvement, keeping the previous version."}
            break