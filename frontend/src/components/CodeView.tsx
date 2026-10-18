import { useEffect, useRef } from "react"
import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react"

const defineTheme: BeforeMount = (monaco) => {
    monaco.editor.defineTheme("d2c", {
        base: "vs-dark",
        inherit: true,
        rules: [
            { token: "comment", foreground: "6b9080", fontStyle: "italic" },
            { token: "string", foreground: "86efac" },
            { token: "keyword", foreground: "c4b5fd" },
            { token: "tag", foreground: "5eead4" },
            { token: "attribute.name", foreground: "fde68a" },
            { token: "attribute.value", foreground: "86efac" },
        ],
        colors: {
            "editor.background": "#071512",
            "editor.foreground": "#d7f5ea",
            "editorLineNumber.foreground": "#3e5c54",
            "editorLineNumber.activeForeground": "#8ee0b8",
            "editor.selectionBackground": "#1f4d3d",
            "editorCursor.foreground": "#8ee0b8",
            "scrollbarSlider.background": "#1c3b34",
            "scrollbarSlider.hoverBackground": "#2a5248",
        },
    })
}

export const CodeView = ({ code, language = "html" }: { code: string; language?: string }) => {
    const editorRef = useRef<Parameters<OnMount>[0] | null>(null)

    useEffect(() => {
        const editor = editorRef.current
        if (editor) editor.revealLine(editor.getModel()?.getLineCount() ?? 1)
    }, [code])

    return (
        <Editor
            height="100%"
            language={language}
            theme="d2c"
            value={code}
            beforeMount={defineTheme}
            onMount={(editor) => {
                editorRef.current = editor
            }}
            options={{
                readOnly: true,
                minimap: { enabled: false },
                wordWrap: "on",
                fontSize: 13,
                scrollBeyondLastLine: false,
                automaticLayout: true,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                padding: { top: 12, bottom: 12 },
                renderLineHighlight: "none",
                overviewRulerLanes: 0,
                hideCursorInOverviewRuler: true,
                scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
            }}
        />
    )
}
