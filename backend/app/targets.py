"""The two generation targets. Ids here must match frontend/src/targets.ts."""
from dataclasses import dataclass
from typing import Callable, Sequence

from app.prompts import html_tailwind, react_mui
from app.services.preprocess import PaletteColor


class UnknownTarget(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    id: str
    preview: str  # "html" or "react"
    kind: str  # words used in the refine prompt
    fence: str  # html or tsx
    system_prompt: str
    build_user_prompt: Callable[..., str]


def _html_prompt(width: int, height: int, palette: Sequence[PaletteColor], ocr_text: str, hint: str = "") -> str:
    return html_tailwind.build_user_prompt(width, height, palette, ocr_text, hint)


def _react_prompt(width: int, height: int, palette: Sequence[PaletteColor], ocr_text: str, hint: str = "") -> str:
    return react_mui.build_user_prompt(width, height, palette, ocr_text, hint)


HTML_TAILWIND = Target(
    id="html_tailwind",
    preview="html",
    kind="HTML",
    fence="html",
    system_prompt=html_tailwind.SYSTEM_PROMPT,
    build_user_prompt=_html_prompt,
)

REACT_MUI = Target(
    id="react_mui",
    preview="react",
    kind="React component",
    fence="tsx",
    system_prompt=react_mui.SYSTEM_PROMPT,
    build_user_prompt=_react_prompt,
)

_BY_ID = {HTML_TAILWIND.id: HTML_TAILWIND, REACT_MUI.id: REACT_MUI}


def get_target(name: str) -> Target:
    key = (name or "").strip() or HTML_TAILWIND.id
    try:
        return _BY_ID[key]
    except KeyError:
        raise UnknownTarget(key) from None
