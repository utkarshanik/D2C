"""
Small helpers that clean up what the model returns.

Only the standard library (`re`) is used here, so this file is trivially testable.
"""
import re

# Matches ```html ... ``` (or just ``` ... ```). The `(?:```|$)` ending also matches a
# reply that was cut off before the closing fence, so truncated output is still usable.
# The language tag is optional, so ```html, ```tsx and a bare ``` all match.
# A reply cut off before the closing fence still returns the code written so far.
_FENCE = re.compile(r"```(?:[A-Za-z0-9_+-]*)?[ \t]*\n(.*?)(?:```|$)", re.S)


def extract_code(text: str) -> str:
    """Return only the code from the model's reply."""
    match = _FENCE.search(text)
    return (match.group(1) if match else text).strip()


def extract_html(text: str) -> str:
    """Return only the code from the model's reply.

    The system prompt asks for one fenced block, but models sometimes add text
    around it or forget the fence. We handle all three cases.
    """
    return extract_code(text)