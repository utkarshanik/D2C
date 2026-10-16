"""Extract deterministic visual facts from an uploaded screenshot."""

import asyncio
import io
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

PALETTE_SIZE = 8
MAX_PALETTE_SAMPLES = 100_000
MAX_OCR_CHARACTERS = 4_000
OCR_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class PaletteColor:
    """An exact source-image color and its share of sampled pixels."""

    hex: str
    percentage: float


@dataclass(frozen=True)
class PreprocessResult:
    """Pixel measurements that are safe to inject into a generation prompt."""

    width: int
    height: int
    palette: tuple[PaletteColor, ...]
    ocr_text: str


def _rgb_image(image: Image.Image) -> Image.Image:
    """Flatten transparency onto white, matching normal browser rendering."""
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba_image = image.convert("RGBA")
        background = Image.new("RGBA", rgba_image.size, "white")
        return Image.alpha_composite(background, rgba_image).convert("RGB")

    return image.convert("RGB")


def extract_palette(
    image: Image.Image,
    color_count: int = PALETTE_SIZE,
    max_samples: int = MAX_PALETTE_SAMPLES,
) -> tuple[PaletteColor, ...]:
    """Return the most common exact RGB values, ordered by pixel frequency."""
    rgb_image = _rgb_image(image)
    pixel_count = rgb_image.width * rgb_image.height

    if pixel_count > max_samples:
        scale = math.sqrt(max_samples / pixel_count)
        sample_size = (
            max(1, round(rgb_image.width * scale)),
            max(1, round(rgb_image.height * scale)),
        )
        rgb_image = rgb_image.resize(sample_size, Image.Resampling.NEAREST)

    if hasattr(rgb_image, "get_flattened_data"):
        pixels = list(rgb_image.get_flattened_data())
    else:
        pixels = list(rgb_image.getdata())
    counts = Counter(pixels)
    sample_count = len(pixels)

    return tuple(
        PaletteColor(
            hex=f"#{red:02X}{green:02X}{blue:02X}",
            percentage=round(count / sample_count * 100, 2),
        )
        for (red, green, blue), count in counts.most_common(color_count)
    )


def normalize_ocr_text(raw_text: str) -> str:
    """Remove OCR whitespace noise while preserving meaningful line breaks."""
    normalized_lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in raw_text.splitlines()
        if line.strip()
    ]
    return "\n".join(normalized_lines)[:MAX_OCR_CHARACTERS]


def extract_ocr_text(image: Image.Image) -> str:
    """Read visible text with local Tesseract, without making OCR mandatory."""
    try:
        import pytesseract

        grayscale_image = ImageOps.autocontrast(_rgb_image(image).convert("L"))
        raw_text = pytesseract.image_to_string(
            grayscale_image,
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except (ImportError, OSError, RuntimeError) as error:
        log.warning("OCR unavailable; continuing without extracted text: %s", error)
        return ""

    return normalize_ocr_text(raw_text)


def preprocess_image_sync(image_bytes: bytes) -> PreprocessResult:
    """Decode once and collect palette and OCR measurements."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        image.load()
        return PreprocessResult(
            width=image.width,
            height=image.height,
            palette=extract_palette(image),
            ocr_text=extract_ocr_text(image),
        )


async def preprocess_image(image_bytes: bytes) -> PreprocessResult:
    """Run CPU-bound pixel analysis outside FastAPI's event loop."""
    return await asyncio.to_thread(preprocess_image_sync, image_bytes)
