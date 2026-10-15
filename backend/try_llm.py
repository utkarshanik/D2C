"""Manual check for module 1:  python try_llm.py out.png"""
import asyncio
import sys

from app.prompts.html_tailwind import SYSTEM_PROMPT, USER_PROMPT
from app.services.llm import build_messages, extract_code, stream_code


async def main(path: str):
    image = open(path, "rb").read()
    messages = build_messages(SYSTEM_PROMPT, USER_PROMPT, [image])
    full = ""
    async for delta in stream_code(messages):
        print(delta, end="", flush=True)  # tokens appear as they arrive
        full += delta
    print("\n\n--- extracted code length:", len(extract_code(full)))


asyncio.run(main(sys.argv[1]))