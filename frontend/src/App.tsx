import { useState } from "react";
import "./App.css";
import { CodeView } from "./components/CodeView";
import { Preview } from "./components/Preview";
import { Uploader } from "./components/Uploader";
import { useGenerate } from "./hooks/useGenerate";

type Tab = "preview" | "code";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [hint, setHint] = useState("");
  const [manualTab, setManualTab] = useState<Tab | null>(null);
  const { code, previewCode, meta, status, error, busy, generate, stop } = useGenerate();

  // Until the user clicks a tab: show the code while streaming, the preview when finished
  const tab: Tab = manualTab ?? (busy ? "code" : "preview");

  const onGenerate = () => {
    if (!file) return;
    setManualTab(null);
    void generate(file, hint);
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>Design to code</h2>
        <Uploader file={file} onSelect={setFile} disabled={busy} />
        {meta && <p className="muted">Original: {meta.width} × {meta.height}px</p>}
        <textarea
          placeholder="Optional hint, e.g. dark theme"
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          disabled={busy}
          rows={3}
        />
        <div className="row">
          <button onClick={onGenerate} disabled={!file || busy}>{busy ? "Working..." : "Generate code"}</button>
          {busy && <button onClick={stop} className="secondary">Stop</button>}
        </div>
        {status && <p className="muted">{status}</p>}
        {error && <p className="error">{error}</p>}
      </aside>

      <main className="main">
        <div className="tabs">
          <button onClick={() => setManualTab("preview")} disabled={tab === "preview"}>Preview</button>
          <button onClick={() => setManualTab("code")} disabled={tab === "code"}>Code</button>
          {code && (
            <button className="secondary push" onClick={() => void navigator.clipboard.writeText(previewCode || code)}>
              Copy code
            </button>
          )}
        </div>
        <div className="panel">
          {tab === "preview" ? <Preview html={previewCode} /> : <CodeView code={code} />}
        </div>
      </main>
    </div>
  );
}
