import { useEffect, useState } from "react"
import "./App.css"
import { CodeView } from "./components/CodeView"
import { Composer } from "./components/Composer"
import { PreviewStage } from "./components/PreviewStage"
import { Sidebar } from "./components/Sidebar"
import { TopBar } from "./components/TopBar"
import { UpgradeDialog } from "./components/UpgradeDialog"
import { WorkspaceToolbar } from "./components/WorkspaceToolbar"
import { useGenerate } from "./hooks/useGenerate"
import { downloadName, REACT_MUI, targetLabel } from "./targets"
import type { DesignSource, DeviceMode, WorkspaceView } from "./workspace"

export default function App() {
    const [file, setFile] = useState<File | null>(null)
    const [hint, setHint] = useState("")
    const [instruction, setInstruction] = useState("")
    const [view, setView] = useState<WorkspaceView>("preview")
    const [device, setDevice] = useState<DeviceMode>("desktop")
    const [zoom, setZoom] = useState(100)
    const [source, setSource] = useState<DesignSource>("screenshot")
    const [figmaPreviewId, setFigmaPreviewId] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)
    const [upgradeOpen, setUpgradeOpen] = useState(false)
    const [sidebarOpen, setSidebarOpen] = useState(false)
    const [notice, setNotice] = useState("")
    const [chatKey, setChatKey] = useState(0)
    const [narrow, setNarrow] = useState(false)
    const {
        code, previewCode, meta, scores, status, error, busy, projectId, projects, projectsReady,
        target, previewTarget, canUndo, generate, generateFromFigma, refine, undo, stop, openProject, setTarget, reset,
    } = useGenerate()

    useEffect(() => {
        if (!copied) return
        const id = window.setTimeout(() => setCopied(false), 1600)
        return () => window.clearTimeout(id)
    }, [copied])

    useEffect(() => {
        const query = window.matchMedia("(max-width: 1080px)")
        const apply = () => setNarrow(query.matches)
        apply()
        query.addEventListener("change", apply)
        return () => query.removeEventListener("change", apply)
    }, [])

    useEffect(() => {
        if (!sidebarOpen) return
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") setSidebarOpen(false)
        }
        window.addEventListener("keydown", onKey)
        return () => window.removeEventListener("keydown", onKey)
    }, [sidebarOpen])

    const currentCode = previewCode || code
    const hasResult = Boolean(previewCode)

    const handleNewChat = () => {
        reset()
        setFile(null)
        setHint("")
        setInstruction("")
        setFigmaPreviewId(null)
        setNotice("")
        setView("preview")
        setDevice("desktop")
        setZoom(100)
        setSource("screenshot")
        setSidebarOpen(false)
        setChatKey((value) => value + 1)
    }

    const handleOpenProject = async (id: string) => {
        const opened = await openProject(id)
        if (!opened) return
        setFile(opened.file)
        setHint(opened.hint)
        setInstruction("")
        setNotice("")
        setFigmaPreviewId(null)
        setSource("screenshot")
        setView("preview")
        setSidebarOpen(false)
    }

    const handleGenerate = () => {
        if (source === "figma") {
            if (!figmaPreviewId) {
                setNotice("Preview a Figma frame first.")
                return
            }
            const nextHint = instruction.trim() || hint
            setNotice("")
            setInstruction("")
            void generateFromFigma(figmaPreviewId, nextHint)
            return
        }
        if (!file) return
        const nextHint = instruction.trim() || hint
        setNotice("")
        setInstruction("")
        void generate(file, nextHint)
    }

    const handleRefine = () => {
        if (!previewCode || (!file && !projectId)) return
        const next = instruction
        setNotice("")
        setInstruction("")
        void refine(file, next)
    }

    const handleSend = () => {
        if (busy) {
            stop()
            return
        }
        if (hasResult && instruction.trim()) {
            handleRefine()
            return
        }
        handleGenerate()
    }

    const handleCopy = async () => {
        if (!currentCode) return
        try {
            await navigator.clipboard.writeText(currentCode)
            setCopied(true)
        } catch {
            setNotice("Couldn't copy the code.")
        }
    }

    const handleDownload = () => {
        if (!currentCode) return
        const blob = new Blob([currentCode], { type: "text/plain;charset=utf-8" })
        const url = URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = url
        link.download = downloadName(previewTarget)
        link.click()
        URL.revokeObjectURL(url)
    }

    const canSendDesign = source === "figma" ? Boolean(figmaPreviewId) : Boolean(file)
    const canRefineNow = Boolean(hasResult && instruction.trim() && (file || projectId))
    const sendDisabled = !busy && !canSendDesign && !canRefineNow
    const sendMode = busy ? "stop" : hasResult && instruction.trim() ? "refine" : "generate"
    const alertMessage = notice || error
    const scoreLabel = scores.length
        ? `Match with original: ${scores.map((score) => `${Math.round(Math.max(0, score) * 100)}%`).join(" → ")}`
        : ""

    return (
        <div className="app">
            <Sidebar
                open={sidebarOpen}
                narrow={narrow}
                projects={projects}
                projectId={projectId}
                busy={busy}
                projectsReady={projectsReady}
                onNewChat={handleNewChat}
                onOpenProject={(id) => void handleOpenProject(id)}
                onUpgrade={() => setUpgradeOpen(true)}
                onClose={() => setSidebarOpen(false)}
            />
            <div className="workspace">
                {sidebarOpen && (
                    <button type="button" className="scrim" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />
                )}
                <TopBar
                    projects={projects}
                    projectId={projectId}
                    busy={busy}
                    onOpenProject={(id) => void handleOpenProject(id)}
                    onNewChat={handleNewChat}
                    onUpgrade={() => setUpgradeOpen(true)}
                    onMenu={() => setSidebarOpen(true)}
                />
                <WorkspaceToolbar
                    view={view}
                    onView={setView}
                    device={device}
                    onDevice={setDevice}
                    busy={busy}
                    copied={copied}
                    canCopy={Boolean(currentCode)}
                    canDownload={Boolean(currentCode)}
                    canUndo={canUndo}
                    canMatch={Boolean(previewCode && (file || projectId))}
                    canRegenerate={source === "figma" ? Boolean(figmaPreviewId) : Boolean(file)}
                    onCopy={() => void handleCopy()}
                    onDownload={handleDownload}
                    onUndo={undo}
                    onStop={stop}
                    onMatch={() => {
                        setNotice("")
                        void refine(file, "")
                    }}
                    onRegenerate={handleGenerate}
                />
                <div className="split" data-view={view}>
                    <section
                        className={view === "preview" ? "preview-card active" : "preview-card"}
                        id="preview-panel"
                        aria-label="Preview"
                        hidden={narrow && view !== "preview"}
                    >
                        <PreviewStage
                            html={previewCode}
                            target={previewTarget}
                            device={device}
                            zoom={zoom}
                            onZoom={setZoom}
                            busy={busy}
                            status={status}
                            meta={meta}
                        />
                    </section>
                    <section
                        className={view === "code" ? "code-card active" : "code-card"}
                        id="code-panel"
                        aria-label="Code"
                        hidden={narrow && view !== "code"}
                    >
                        <header className="code-head">
                            <span>{targetLabel(previewTarget)}</span>
                        </header>
                        <div className="code-body">
                            {code ? (
                                <CodeView code={code} language={previewTarget === REACT_MUI ? "typescript" : "html"} />
                            ) : (
                                <div className="code-empty" role="status">
                                    {busy && <span className="spinner" aria-hidden="true" />}
                                    <p>{busy ? "Writing code…" : "Generated code will show up here."}</p>
                                </div>
                            )}
                        </div>
                    </section>
                </div>
                {(alertMessage || status || scoreLabel) && (
                    <div className="status-row">
                        {alertMessage
                            ? <p className="error" role="alert">{alertMessage}</p>
                            : status
                                ? <p role="status">{status}</p>
                                : null}
                        {scoreLabel && <p>{scoreLabel}</p>}
                    </div>
                )}
                <Composer
                    key={chatKey}
                    source={source}
                    onSource={setSource}
                    target={target}
                    onTarget={setTarget}
                    file={file}
                    onFile={(next) => {
                        setFile(next)
                        setNotice("")
                    }}
                    onClearFile={() => setFile(null)}
                    instruction={instruction}
                    onInstruction={(value) => {
                        setInstruction(value)
                        if (notice) setNotice("")
                    }}
                    onFigmaPreview={setFigmaPreviewId}
                    onConfirmFigma={(previewId) => {
                        const nextHint = instruction.trim() || hint
                        setNotice("")
                        setInstruction("")
                        void generateFromFigma(previewId, nextHint)
                    }}
                    busy={busy}
                    sendMode={sendMode}
                    sendDisabled={sendDisabled}
                    onSend={handleSend}
                    onAlert={setNotice}
                />
            </div>
            <UpgradeDialog open={upgradeOpen} onClose={() => setUpgradeOpen(false)} />
        </div>
    )
}
