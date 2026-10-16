# Prompt for the refine step. Kept next to the first-draft prompt so every
# prompt lives in app/prompts/. The system prompt is reused from html_tailwind.py.

REFINE_PROMPT = """Image 1 is the TARGET design. Image 2 is a screenshot of how the CURRENT code renders.
Compare them carefully: layout, alignment, spacing, sizes, colors, borders and text.
Fix every visible difference. Keep anything that already matches.
{hint_block}Return the FULL corrected HTML in one ```html fenced block. No explanations.

Current code:
{code}"""

# Without this, the refine step would "fix" the page back to the original and
# undo changes the user asked for (e.g. "make it a light theme").
HINT_BLOCK = (
    "The user asked for these deliberate changes compared with the target image. "
    "Keep them, do not undo them: {hint}\n"
)