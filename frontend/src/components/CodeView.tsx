import { useEffect, useRef } from "react";
// @monaco-editor/react: the VS Code editor as a React component (read-only code viewer here)
import Editor, { type OnMount } from "@monaco-editor/react";

export function CodeView({ code, language = "html" }: { code: string; language?: string }) {
    const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

    // keep the newest line in view while tokens stream in
    useEffect(() => {
        const editor = editorRef.current;
        if (editor) editor.revealLine(editor.getModel()?.getLineCount() ?? 1);
    }, [code]);

    return (
        <Editor
            height="100%"
            language={language}
            theme="vs-dark"
            value={code}
            onMount={(editor) => { editorRef.current = editor; }}
            options={{ readOnly: true, minimap: { enabled: false }, wordWrap: "on", fontSize: 13, scrollBeyondLastLine: false }}
        />
    );
}
