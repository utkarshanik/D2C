"""Shared image checks for uploads and Figma renders."""
import io

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024  # 5 MB cap protects the server and the free model quota
FORMAT_TO_MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def inspect_image(data: bytes) -> tuple[int, int, str]:
    """Return (width, height, mime) or raise HTTPException(400).

    The filename and the client content-type are ignored. Pillow has to decode the bytes.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()  # fully decode so truncated or corrupt files fail here, not later
            mime = FORMAT_TO_MIME.get(img.format or "")
            if mime is None:
                raise HTTPException(400, "Unsupported image type. Use PNG, JPEG or WEBP.")
            return img.width, img.height, mime
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "File is not a valid image.")
