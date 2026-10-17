"""Projects and versions are stored, and a follow-up edit reuses that history."""
import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routes import generate as route
from app.services import projects as store
from app.services.preprocess import PaletteColor, PreprocessResult

client = TestClient(app)


def png_bytes(size=(40, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, format="PNG")
    return buf.getvalue()


def events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def fake_preprocess(monkeypatch):
    async def fake(image_bytes):
        with Image.open(io.BytesIO(image_bytes)) as image:
            return PreprocessResult(
                width=image.width,
                height=image.height,
                palette=(PaletteColor("#FFFFFF", 100.0),),
                ocr_text="",
            )

    monkeypatch.setattr(route, "preprocess_image", fake)


def draft_llm(monkeypatch, parts):
    async def fake(image_bytes, mime, prompt, system_prompt):
        for part in parts:
            yield part

    monkeypatch.setattr(route, "generate_from_image", fake)


def test_compose_follow_up_keeps_a_plain_request_when_nothing_came_before():
    assert store.compose_follow_up([], "make the sidebar narrower") == "make the sidebar narrower"


def test_compose_follow_up_lists_earlier_requests():
    text = store.compose_follow_up(["dark theme"], "make the sidebar narrower")
    assert "dark theme" in text
    assert "make the sidebar narrower" in text
    assert text.index("dark theme") < text.index("make the sidebar narrower")


def test_generate_saves_project_version_and_image(monkeypatch):
    fake_preprocess(monkeypatch)
    draft_llm(monkeypatch, ["```html\n<p>draft</p>\n```"])
    image = png_bytes()

    response = client.post(
        "/generate",
        files={"image": ("a.png", image, "image/png")},
        data={"hint": "dark theme"},
    )
    assert response.status_code == 200
    project_id = events(response)[0]["project_id"]

    detail = client.get(f"/projects/{project_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["width"] == 40
    assert body["height"] == 20
    assert body["hint"] == "dark theme"
    assert body["versions"] == [
        {
            "id": body["versions"][0]["id"],
            "number": 1,
            "created_at": body["versions"][0]["created_at"],
            "code": "<p>draft</p>",
            "instruction": "dark theme",
        }
    ]

    listed = client.get("/projects").json()
    assert [item["id"] for item in listed] == [project_id]
    assert listed[0]["version_count"] == 1

    image_response = client.get(f"/projects/{project_id}/image")
    assert image_response.status_code == 200
    assert image_response.content == image
    assert image_response.headers["content-type"].startswith("image/png")


def test_failed_generation_does_not_keep_a_project(monkeypatch):
    fake_preprocess(monkeypatch)

    async def broken(image_bytes, mime, prompt, system_prompt):
        raise RuntimeError("boom")
        yield

    monkeypatch.setattr(route, "generate_from_image", broken)
    response = client.post("/generate", files={"image": ("a.png", png_bytes(), "image/png")})

    assert events(response)[-1]["type"] == "error"
    assert client.get("/projects").json() == []


def test_follow_up_uses_stored_image_and_earlier_requests(monkeypatch):
    fake_preprocess(monkeypatch)
    draft_llm(monkeypatch, ["```html\n<p>draft</p>\n```"])
    seen = {}

    async def fake_refine(original, mime, width, height, code, instruction=""):
        seen["image"] = original
        seen["code"] = code
        seen["instruction"] = instruction
        seen["size"] = (width, height)
        yield {"type": "code", "code": "<p>narrow</p>"}

    monkeypatch.setattr("app.routes.projects.refine_step", fake_refine)
    image = png_bytes((80, 30))
    created = client.post(
        "/generate",
        files={"image": ("a.png", image, "image/png")},
        data={"hint": "dark theme"},
    )
    project_id = events(created)[0]["project_id"]

    edited = client.post(
        f"/projects/{project_id}/edit",
        data={"instruction": "make the sidebar narrower", "code": "<p>draft</p>"},
    )
    edited_events = events(edited)
    assert {"type": "code", "code": "<p>narrow</p>"} in edited_events
    assert edited_events[-1] == {"type": "done"}
    assert seen["image"] == image
    assert seen["code"] == "<p>draft</p>"
    assert seen["size"] == (80, 30)
    assert "dark theme" in seen["instruction"]
    assert "make the sidebar narrower" in seen["instruction"]

    versions = client.get(f"/projects/{project_id}").json()["versions"]
    assert [version["code"] for version in versions] == ["<p>draft</p>", "<p>narrow</p>"]
    assert versions[1]["instruction"] == "make the sidebar narrower"
    assert client.get("/projects").json()[0]["version_count"] == 2


def test_follow_up_from_an_older_version_ignores_later_requests(monkeypatch):
    fake_preprocess(monkeypatch)
    draft_llm(monkeypatch, ["```html\n<p>v1</p>\n```"])
    seen = {}

    async def fake_refine(original, mime, width, height, code, instruction=""):
        seen["code"] = code
        seen["instruction"] = instruction
        yield {"type": "code", "code": "<p>v3</p>"}

    monkeypatch.setattr("app.routes.projects.refine_step", fake_refine)
    created = client.post(
        "/generate",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"hint": "dark theme"},
    )
    project_id = events(created)[0]["project_id"]
    store.add_version(project_id, "<p>v2</p>", "narrow the sidebar")

    client.post(
        f"/projects/{project_id}/edit",
        data={"instruction": "bigger logo", "code": "<p>v1</p>"},
    )
    assert seen["code"] == "<p>v1</p>"
    assert "dark theme" in seen["instruction"]
    assert "narrow the sidebar" not in seen["instruction"]
    assert "bigger logo" in seen["instruction"]


def test_unchanged_follow_up_does_not_add_a_version(monkeypatch):
    fake_preprocess(monkeypatch)
    draft_llm(monkeypatch, ["```html\n<p>draft</p>\n```"])

    async def fake_refine(original, mime, width, height, code, instruction=""):
        yield {"type": "status", "message": "Already close to the original, nothing to fix."}

    monkeypatch.setattr("app.routes.projects.refine_step", fake_refine)
    created = client.post("/generate", files={"image": ("a.png", png_bytes(), "image/png")})
    project_id = events(created)[0]["project_id"]

    response = client.post(f"/projects/{project_id}/edit", data={"code": "<p>draft</p>"})
    assert events(response)[-1] == {"type": "done"}
    assert len(client.get(f"/projects/{project_id}").json()["versions"]) == 1


def test_missing_project_is_not_found():
    response = client.post("/projects/not-a-real-project/edit", data={"instruction": "bigger logo"})
    assert response.status_code == 404


def test_edit_without_code_is_rejected():
    project_id = store.create_project(png_bytes(), "image/png", 40, 20, "")
    response = client.post(f"/projects/{project_id}/edit", data={"instruction": "bigger logo"})
    assert response.status_code == 400
