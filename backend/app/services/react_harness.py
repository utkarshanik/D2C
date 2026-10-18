"""Turn a TSX component into one HTML page Playwright can photograph.

Sandpack compiles the same component in the browser preview. Playwright can
only screenshot a page, so this page loads the pinned React and MUI builds,
strips imports down to those globals, and lets Babel compile the TSX.
"""
import json
import re

from app.services.renderer import render_html

REACT_VERSION = "18.3.1"
MUI_VERSION = "5.18.0"
BABEL_VERSION = "7.29.10"
REACT_RENDER_TIMEOUT_MS = 45_000

# Globals the UMD builds attach to window. Deep imports and icon packages are
# rejected because those scripts are not on the page.
_MODULES = {
    "react": "ReactGlobal",
    "react-dom": "ReactDOMGlobal",
    "react-dom/client": "ReactDOMGlobal",
    "@mui/material": "MaterialUI",
    "@mui/material/styles": "MaterialUI",
    "@mui/material/colors": "MaterialUI.colors",
}

_IMPORT_FROM = re.compile(
    r"""^[ \t]*import\s+(type\s+)?(.+?)\s+from\s+['"]([^'"]+)['"]\s*;?\s*$"""
)
_IMPORT_SIDE = re.compile(
    r"""^[ \t]*import\s+['"]([^'"]+)['"]\s*;?\s*$"""
)
_EXPORT_FN = re.compile(r"export\s+default\s+function\s+([A-Za-z_$][\w$]*)")
_EXPORT_CLASS = re.compile(r"export\s+default\s+class\s+([A-Za-z_$][\w$]*)")
_EXPORT_EXPR = re.compile(r"export\s+default\s+")


class HarnessError(ValueError):
    """The component cannot be prepared for a screenshot."""


def _named_binding(clause: str, module_global: str) -> str | None:
    inner = clause.strip()
    if not (inner.startswith("{") and inner.endswith("}")):
        raise HarnessError(f"Could not read import {{{clause}}}.")
    parts: list[str] = []
    for piece in inner[1:-1].split(","):
        piece = piece.strip()
        if not piece or piece.startswith("type "):
            continue
        parts.append(piece)
    if not parts:
        return None
    return f"const {{ {', '.join(parts)} }} = {module_global};"


def _bindings(clause: str, module: str) -> list[str]:
    try:
        module_global = _MODULES[module]
    except KeyError:
        raise HarnessError(
            f"Import {module!r} is not available. Use @mui/material, @mui/material/styles, or @mui/material/colors."
        ) from None

    clause = clause.strip()
    if clause.startswith("* as "):
        alias = clause[5:].strip()
        if alias in ("React", "ReactDOM"):
            return []
        return [f"const {alias} = {module_global};"]

    default: str | None = None
    named: str | None = None
    if clause.startswith("{"):
        named = clause
    elif "{" in clause:
        default_part, named_part = clause.split("{", 1)
        default = default_part.strip().rstrip(",").strip() or None
        named = "{" + named_part
    else:
        default = clause

    lines: list[str] = []
    if default and default not in ("React", "ReactDOM"):
        lines.append(f"const {default} = {module_global};")
    if named:
        binding = _named_binding(named, module_global)
        if binding:
            lines.append(binding)
    return lines


def to_runnable_tsx(source: str) -> tuple[str, str]:
    """Drop imports and exports Babel cannot run inside one function.

    Type annotations stay in the text. Babel's TypeScript preset removes them
    in the browser. React and ReactDOM are already in scope.
    """
    kept: list[str] = []
    bindings: list[str] = []
    for line in source.splitlines():
        side = _IMPORT_SIDE.match(line)
        if side:
            module = side.group(1)
            if module not in _MODULES:
                raise HarnessError(f"Import {module!r} is not available.")
            continue
        imported = _IMPORT_FROM.match(line)
        if imported:
            is_type, clause, module = imported.groups()
            if is_type:
                continue
            bindings.extend(_bindings(clause, module))
            continue
        kept.append(line)

    body = "\n".join(kept)
    exported = _EXPORT_FN.search(body)
    if exported:
        name = exported.group(1)
        body = _EXPORT_FN.sub(f"function {name}", body, count=1)
    else:
        exported = _EXPORT_CLASS.search(body)
        if exported:
            name = exported.group(1)
            body = _EXPORT_CLASS.sub(f"class {name}", body, count=1)
        elif _EXPORT_EXPR.search(body):
            body = _EXPORT_EXPR.sub("const __defaultExport = ", body, count=1)
            name = "__defaultExport"
        else:
            fallback = re.search(r"function\s+([A-Za-z_$][\w$]*)", body)
            if fallback is None:
                raise HarnessError("The component must be a default export.")
            name = fallback.group(1)

    body = re.sub(r"(?m)^[ \t]*export\s+(?=const|function|class|let|var|type|interface|enum)", "", body)
    body = re.sub(r"(?m)^[ \t]*export\s+\{[^}]*\}\s*;?\s*$", "", body)
    if not re.fullmatch(r"[A-Za-z_$][\w$]*", name):
        raise HarnessError("The component must be a default export.")
    preamble = "const React = ReactGlobal;\nconst ReactDOM = ReactDOMGlobal;\n"
    # `return` is added after Babel runs. A top-level return is a syntax error
    # in the file Babel parses, and that was leaving the preview blank.
    return preamble + "\n".join(bindings) + "\n" + body.strip() + "\n", name


def _js_string(source: str) -> str:
    # "<" would let the component close the surrounding script tag.
    return json.dumps(source).replace("<", "\\u003c")


def _error_page(message: str) -> str:
    safe = json.dumps(message).replace("<", "\\u003c")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;font:16px sans-serif">
<pre id="root" style="white-space:pre-wrap;padding:16px"></pre>
<script>
document.getElementById("root").textContent = {safe};
window.__ready = true;
</script>
</body>
</html>"""


def build_preview_html(source: str) -> str:
    """Return a page that renders the component or shows why it could not."""
    try:
        runnable, export_name = to_runnable_tsx(source)
    except HarnessError as exc:
        return _error_page(str(exc))

    payload = _js_string(runnable)
    exported = json.dumps(export_name)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap">
<style>html,body,#root{{margin:0;height:100%;}}</style>
<script src="https://unpkg.com/react@{REACT_VERSION}/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@{REACT_VERSION}/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@mui/material@{MUI_VERSION}/umd/material-ui.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone@{BABEL_VERSION}/babel.min.js"></script>
</head>
<body>
<div id="root"></div>
<script>
const source = {payload};
try {{
  if (!window.Babel || !window.React || !window.ReactDOM || !window.MaterialUI) {{
    throw new Error("React or MUI failed to load");
  }}
  const compiled = Babel.transform(source, {{
    filename: "App.tsx",
    presets: [
      ["typescript", {{ allExtensions: true, isTSX: true }}],
      ["react", {{ runtime: "classic" }}]
    ]
  }}).code + "\\nreturn " + {exported} + ";";
  const App = new Function("ReactGlobal", "ReactDOMGlobal", "MaterialUI", compiled)(
    window.React, window.ReactDOM, window.MaterialUI
  );
  const theme = window.MaterialUI.createTheme();
  const tree = window.React.createElement(
    window.MaterialUI.ThemeProvider,
    {{ theme: theme }},
    window.React.createElement(window.MaterialUI.CssBaseline, null, window.React.createElement(App))
  );
  window.ReactDOM.createRoot(document.getElementById("root")).render(tree);
  requestAnimationFrame(function () {{ window.__ready = true; }});
}} catch (err) {{
  document.getElementById("root").textContent = (err && err.message) ? err.message : String(err);
  window.__ready = true;
}}
</script>
</body>
</html>"""


async def render_code(target_id: str, code: str, width: int, height: int) -> bytes:
    """Screenshot HTML directly, or a TSX component through the harness page."""
    from app.targets import get_target

    target = get_target(target_id)
    if target.preview == "html":
        return await render_html(code, width, height)
    page = build_preview_html(code)
    return await render_html(
        page,
        width,
        height,
        wait_for="() => window.__ready === true",
        timeout_ms=REACT_RENDER_TIMEOUT_MS,
    )
