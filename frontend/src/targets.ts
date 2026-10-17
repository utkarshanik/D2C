// Ids must match backend/app/targets.py.
export const HTML_TAILWIND = "html_tailwind"
export const REACT_MUI = "react_mui"

export const previewKind = (target: string): "html" | "react" =>
    target === REACT_MUI ? "react" : "html"
