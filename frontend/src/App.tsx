import { useState } from "react";
import "./App.css";
import { CodeView } from "./components/CodeView";
import { Preview } from "./components/Preview";
import { Uploader } from "./components/Uploader";
import { useGenerate } from "./hooks/useGenerate";
import { HTML_TAILWIND, REACT_MUI } from "./targets";

type Tab = "preview" | "code";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [hint, setHint] = useState("");
  const [instruction, setInstruction] = useState(""); // for the Refine button
  const [manualTab, setManualTab] = useState<Tab | null>(null);
  const {
    code, previewCode, meta, scores, status, error, busy, projectId, projects,
    target, previewTarget, canUndo, generate, refine, undo, stop, openProject, setTarget,
  } = useGenerate();

  // Until the user clicks a tab: show the code while the first draft streams, the preview otherwise
  // (during a refine the preview stays up, and updates when the new code arrives)
  const tab: Tab = manualTab ?? (busy && !previewCode ? "code" : "preview");

  const onGenerate = () => {
    if (!file) return;
    setManualTab(null);
    setInstruction("");
    void generate(file, hint);
  };

  const onRefine = () => {
    if (!previewCode || (!file && !projectId)) return;
    void refine(file, instruction);
  };

  const onOpenProject = async (id: string) => {
    const opened = await openProject(id);
    if (!opened) return;
    setFile(opened.file);
    setHint(opened.hint);
    setInstruction("");
    setManualTab("preview");
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>Design to code</h2>
        <label className="target">
          Output
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={busy}
          >
            <option value={HTML_TAILWIND}>HTML + Tailwind</option>
            <option value={REACT_MUI}>React + MUI</option>
          </select>
        </label>
        {projects.length > 0 && (
          <section className="projects">
            <h3>Saved projects</h3>
            {projects.map((project) => (
              <button
                key={project.id}
                type="button"
                className={project.id === projectId ? "project active" : "project"}
                onClick={() => void onOpenProject(project.id)}
                disabled={busy}
                aria-current={project.id === projectId ? "true" : undefined}
              >
                {project.width}×{project.height} · {project.version_count}{" "}
                {project.version_count === 1 ? "version" : "versions"}
              </button>
            ))}
          </section>
        )}
        <Uploader file={file} onSelect={setFile} disabled={busy} />
        {meta && <p className="muted">Original: {meta.width} × {meta.height}px</p>}
        <textarea
          placeholder="Optional hint for the first draft, e.g. dark theme"
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          disabled={busy}
          rows={3}
        />
        <div className="row">
          <button onClick={onGenerate} disabled={!file || busy}>{busy ? "Working..." : "Generate code"}</button>
          {busy && <button onClick={stop} className="secondary">Stop</button>}
        </div>
        {previewCode && (
          <section className="refine">
            <h3>Refine</h3>
            <textarea
              placeholder="What should change? Leave empty to match the original more closely."
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              disabled={busy}
              maxLength={1000}
              rows={3}
            />
            <div className="row">
              <button onClick={onRefine} disabled={busy || !previewCode || (!file && !projectId)}>Refine</button>
              <button onClick={undo} disabled={busy || !canUndo} className="secondary">Undo</button>
            </div>
          </section>
        )}
        {scores.length > 0 && (
          // SSIM can dip below 0 for very different images, so clamp before showing a percentage
          <p className="muted">Match with original: {scores.map((s) => `${Math.round(Math.max(0, s) * 100)}%`).join(" → ")}</p>
        )}
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
          {tab === "preview"
            ? <Preview html={previewCode} target={previewTarget} />
            : <CodeView code={code} language={previewTarget === REACT_MUI ? "typescript" : "html"} />}
        </div>
      </main>
    </div>
  );
}
