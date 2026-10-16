"""Offline tests for module 6 screenshot preprocessing."""

import io

from PIL import Image

from app.services import preprocess


def image_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_extract_palette_returns_exact_source_colors_in_frequency_order():
    image = Image.new("RGB", (10, 10), "#112233")
    for x in range(3):
        for y in range(10):
            image.putpixel((x, y), (171, 205, 239))

    palette = preprocess.extract_palette(image, color_count=2)

    assert palette[0].hex == "#112233"
    assert palette[0].percentage == 70.0
    assert palette[1].hex == "#ABCDEF"
    assert palette[1].percentage == 30.0


def test_normalize_ocr_text_removes_whitespace_noise():
    text = preprocess.normalize_ocr_text(
        "  Welcome   back  \n\n Create account \n"
    )

    assert text == "Welcome back\nCreate account"


def test_preprocess_result_contains_dimensions_palette_and_ocr(monkeypatch):
    monkeypatch.setattr(preprocess, "extract_ocr_text", lambda image: "Sign in")
    image = Image.new("RGB", (16, 9), "#445566")

    result = preprocess.preprocess_image_sync(image_bytes(image))

    assert (result.width, result.height) == (16, 9)
    assert result.palette[0].hex == "#445566"
    assert result.ocr_text == "Sign in"
