"""React + MUI target: prompt, TSX fence, and the screenshot harness."""
import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.prompts.react_mui import ALLOWED_COMPONENTS, MUI_VERSION
from app.prompts.refine import MATCH_PROMPT
from app.routes import generate as route
from app.services.postprocess import extract_code
from app.services.react_harness import HarnessError, build_preview_html, to_runnable_tsx
from app.services.preprocess import PaletteColor, PreprocessResult
from app.targets import UnknownTarget, get_target

client = TestClient(app)

COMPONENT = """import { Box, Button } from "@mui/material";

type Title = string;

export default function App() {
  const title: Title = "Hello";
  return <Box><Button>{title}</Button></Box>;
}
"""


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


def events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_extract_code_reads_a_tsx_fence():
    text = "Sure\n```tsx\nexport default function App() { return null }\n```\n"
    assert extract_code(text) == "export default function App() { return null }"


def test_prompt_pins_mui_and_lists_allowed_components():
    target = get_target("react_mui")
    assert MUI_VERSION in target.system_prompt
    assert "```tsx" in target.system_prompt
    assert "@mui/icons-material" in target.system_prompt
    for name in ("Box", "Button", "Typography", "TextField"):
        assert name in ALLOWED_COMPONENTS
        assert name in target.system_prompt
    assert "tailwindcss" not in target.system_prompt


def test_unknown_target_is_rejected():
    try:
        get_target("vue")
    except UnknownTarget:
        pass
    else:
        raise AssertionError("vue should not be a target")


def test_runnable_tsx_keeps_types_and_drops_imports():
    runnable = to_runnable_tsx(COMPONENT)
    assert "import " not in runnable
    assert "const { Box, Button } = MaterialUI;" in runnable
    assert "const title: Title = " in runnable
    assert runnable.strip().endswith("return App;")


def test_icon_import_becomes_an_error_page():
    page = build_preview_html('import Add from "@mui/icons-material/Add";\nexport default function App() { return null }\n')
    assert "not available" in page
    assert "window.__ready = true" in page


def test_bad_import_raises():
    try:
        to_runnable_tsx('import Add from "@mui/icons-material/Add";\nexport default function App() { return null }\n')
    except HarnessError as exc:
        assert "icons-material" in str(exc)
    else:
        raise AssertionError("icon import should be rejected")


def test_refine_prompt_asks_for_tsx():
    target = get_target("react_mui")
    text = MATCH_PROMPT.format(code="const x = 1", kind=target.kind, fence=target.fence)
    assert "```tsx" in text
    assert "React component" in text


def test_html_refine_prompt_still_asks_for_html():
    target = get_target("html_tailwind")
    text = MATCH_PROMPT.format(code="<p></p>", kind=target.kind, fence=target.fence)
    assert "```html" in text
    assert "corrected HTML" in text


def test_generate_react_target_uses_the_mui_prompt_and_saves_it(monkeypatch):
    async def preprocess(_image_bytes):
        return PreprocessResult(width=40, height=20, palette=(PaletteColor("#112233", 100.0),), ocr_text="Hello")

    seen = {}

    async def fake(image_bytes, mime, prompt, system_prompt):
        seen["prompt"] = prompt
        seen["system"] = system_prompt
        yield "```tsx\n" + COMPONENT + "\n```"

    monkeypatch.setattr(route, "preprocess_image", preprocess)
    monkeypatch.setattr(route, "generate_from_image", fake)

    response = client.post(
        "/generate",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"target": "react_mui", "hint": "compact"},
    )
    assert response.status_code == 200
    meta = events(response)[0]
    assert meta["target"] == "react_mui"
    assert MUI_VERSION in seen["system"]
    assert "tailwindcss" not in seen["system"]
    assert "#112233" in seen["prompt"]
    assert "compact" in seen["prompt"]

    detail = client.get(f"/projects/{meta['project_id']}").json()
    assert detail["target"] == "react_mui"
    assert "export default function App" in detail["versions"][0]["code"]


def test_generate_rejects_an_unknown_target():
    response = client.post(
        "/generate",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"target": "vue"},
    )
    assert response.status_code == 400
