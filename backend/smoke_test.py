"""
Smoke tests for setup. Run from the backend/ folder with the venv active:

    python smoke_test.py

Checks:
  1. Playwright can render HTML and save a screenshot (out.png)
  2. LiteLLM can send an image + text to your PRIMARY_MODEL and get a reply
"""
import asyncio
import base64
import io
import os

from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()  # reads backend/.env


async def test_playwright():
    from playwright.async_api import async_playwright

    html = "<h1 style='font-family:sans-serif;color:#2563eb'>Hello render</h1>"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 600, "height": 200})
        await page.set_content(html)
        await page.screenshot(path="out.png")
        await browser.close()
    print("[OK] Playwright rendered out.png")


def make_test_image() -> str:
    """Create a tiny image with a blue button so we don't need a sample file."""
    img = Image.new("RGB", (400, 200), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([100, 70, 300, 130], fill="#2563eb")
    d.text((170, 93), "Click me", fill="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_llm():
    from litellm import completion

    model = os.environ["PRIMARY_MODEL"]
    resp = completion(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this UI in one sentence."},
                    {"type": "image_url", "image_url": {"url": make_test_image()}},
                ],
            }
        ],
    )
    print(f"[OK] {model} replied:", resp.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(test_playwright())
    test_llm()