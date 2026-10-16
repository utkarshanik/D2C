# Prompts for the Refine button. The system prompt is reused from html_tailwind.py.

# No instruction from the user: make the render match the original image.
MATCH_PROMPT = """Image 1 is the TARGET design. Image 2 is a screenshot of how the CURRENT code renders.
Compare them carefully: layout, alignment, spacing, sizes, colors, borders and text.
Fix every visible difference. Keep anything that already matches.
Return the FULL corrected HTML in one ```html fenced block. No explanations.

Current code:
{code}"""

# The user typed what they want changed: that request wins over the original image.
EDIT_PROMPT = """Image 1 is the ORIGINAL design, for reference. Image 2 is a screenshot of how the CURRENT code renders.
Apply this change request from the user:

{instruction}

Change only what the request needs and keep everything else as it is.
If the request conflicts with the original design, the request wins.
Return the FULL updated HTML in one ```html fenced block. No explanations.

Current code:
{code}"""