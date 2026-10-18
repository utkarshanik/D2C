// Ids must match backend/app/targets.py.
export const HTML_TAILWIND = "html_tailwind"
export const REACT_MUI = "react_mui"

export const previewKind = (target: string): "html" | "react" =>
    target === REACT_MUI ? "react" : "html"

export const TARGET_OPTIONS = [
    { value: HTML_TAILWIND, label: "HTML + Tailwind CSS" },
    { value: REACT_MUI, label: "React + MUI" },
] as const

export const targetLabel = (id: string) =>
    TARGET_OPTIONS.find((option) => option.value === id)?.label ?? "HTML + Tailwind CSS"

export const downloadName = (id: string) => (id === REACT_MUI ? "Design.tsx" : "index.html")
