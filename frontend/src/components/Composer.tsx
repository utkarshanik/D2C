import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowUp, Image, Link2, Mic, Paperclip, Square, X } from "lucide-react"
import { FigmaLink } from "./FigmaLink"
import { SelectMenu } from "./SelectMenu"
import { Uploader, type UploaderHandle } from "./Uploader"
import { TARGET_OPTIONS } from "../targets"
import type { DesignSource } from "../workspace"
import { useDismiss } from "../hooks/useDismiss"

type SpeechResultEvent = {
    results: ArrayLike<ArrayLike<{ transcript: string }>>
}

type SpeechErrorEvent = {
    error?: string
}

type SpeechRecognitionLike = {
    lang: string
    interimResults: boolean
    continuous: boolean
    onresult: ((event: SpeechResultEvent) => void) | null
    onerror: ((event: SpeechErrorEvent) => void) | null
    onend: (() => void) | null
    start: () => void
    stop: () => void
}

type SendMode = "generate" | "refine" | "stop"

type Props = {
    source: DesignSource
    onSource: (source: DesignSource) => void
    target: string
    onTarget: (target: string) => void
    file: File | null
    onFile: (file: File) => void
    onClearFile: () => void
    instruction: string
    onInstruction: (value: string) => void
    onFigmaPreview: (previewId: string | null) => void
    onConfirmFigma: (previewId: string) => void
    busy: boolean
    sendMode: SendMode
    sendDisabled: boolean
    onSend: () => void
    onAlert: (message: string) => void
}

const speechCtor = () => {
    const root = window as Window & {
        SpeechRecognition?: new () => SpeechRecognitionLike
        webkitSpeechRecognition?: new () => SpeechRecognitionLike
    }
    return root.SpeechRecognition ?? root.webkitSpeechRecognition
}

const sendLabel = (mode: SendMode) => {
    if (mode === "stop") return "Stop"
    if (mode === "refine") return "Refine"
    return "Generate"
}

export const Composer = ({
    source,
    onSource,
    target,
    onTarget,
    file,
    onFile,
    onClearFile,
    instruction,
    onInstruction,
    onFigmaPreview,
    onConfirmFigma,
    busy,
    sendMode,
    sendDisabled,
    onSend,
    onAlert,
}: Props) => {
    const [shotOpen, setShotOpen] = useState(false)
    const [figmaOpen, setFigmaOpen] = useState(false)
    const [figmaReady, setFigmaReady] = useState(false)
    const [listening, setListening] = useState(false)
    const [dragging, setDragging] = useState(false)
    const uploaderRef = useRef<UploaderHandle>(null)
    const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
    const instructionRef = useRef(instruction)
    const formRef = useRef<HTMLFormElement>(null)
    instructionRef.current = instruction

    const handlePreview = useCallback((previewId: string | null) => {
        setFigmaReady(Boolean(previewId))
        onFigmaPreview(previewId)
    }, [onFigmaPreview])

    const closePopovers = () => {
        setShotOpen(false)
        setFigmaOpen(false)
    }

    useDismiss(shotOpen || figmaOpen, closePopovers, formRef)

    useEffect(() => () => recognitionRef.current?.stop(), [])

    const handleSource = (value: string) => {
        const next: DesignSource = value === "figma" ? "figma" : "screenshot"
        onSource(next)
        setFigmaOpen(next === "figma")
        setShotOpen(next === "screenshot")
    }

    const handleFile = (next: File) => {
        onFile(next)
        setShotOpen(false)
    }

    const handleAttach = () => {
        if (source === "figma") {
            setFigmaOpen((open) => !open)
            setShotOpen(false)
            return
        }
        setFigmaOpen(false)
        uploaderRef.current?.open()
    }

    const handleMic = () => {
        if (listening) {
            recognitionRef.current?.stop()
            setListening(false)
            return
        }
        const Ctor = speechCtor()
        if (!Ctor) {
            onAlert("Speech input isn't available in this browser.")
            return
        }
        const recognition = new Ctor()
        recognition.lang = "en-US"
        recognition.interimResults = false
        recognition.continuous = false
        recognition.onresult = (event) => {
            const transcript = event.results[0]?.[0]?.transcript?.trim() ?? ""
            if (!transcript) return
            const current = instructionRef.current.trim()
            onInstruction(current ? `${current} ${transcript}` : transcript)
        }
        recognition.onerror = (event) => {
            setListening(false)
            if (event.error === "aborted" || event.error === "no-speech") return
            onAlert("Microphone permission is blocked or unavailable.")
        }
        recognition.onend = () => setListening(false)
        recognitionRef.current = recognition
        try {
            recognition.start()
            setListening(true)
        } catch {
            setListening(false)
            onAlert("Couldn't start the microphone.")
        }
    }

    return (
        <form
            ref={formRef}
            className={dragging ? "composer is-dragging" : "composer"}
            aria-label="Design composer"
            onSubmit={(event) => {
                event.preventDefault()
                closePopovers()
                if (!sendDisabled) onSend()
            }}
            onDragOver={(event) => {
                if (source !== "screenshot" || busy) return
                event.preventDefault()
                setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
                event.preventDefault()
                setDragging(false)
                if (source !== "screenshot" || busy) return
                uploaderRef.current?.accept(event.dataTransfer.files[0])
            }}
        >
            <Uploader
                ref={uploaderRef}
                file={file}
                onSelect={handleFile}
                onReject={(message) => {
                    onAlert(message)
                    setShotOpen(true)
                }}
                disabled={busy}
                active={source === "screenshot"}
                expanded={source === "screenshot" && shotOpen}
            />
            <div className="composer-popover" hidden={source !== "figma" || !figmaOpen}>
                <FigmaLink disabled={busy} onConfirm={onConfirmFigma} onPreviewChange={handlePreview} />
            </div>
            <textarea
                className="composer-input"
                value={instruction}
                onChange={(event) => onInstruction(event.target.value)}
                onKeyDown={(event) => {
                    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return
                    event.preventDefault()
                    event.currentTarget.form?.requestSubmit()
                }}
                placeholder="Ask for a follow-up…"
                disabled={busy}
                maxLength={1000}
                rows={2}
                aria-label="Instructions"
            />
            <div className="composer-bar">
                <SelectMenu
                    label="Design input"
                    value={source}
                    disabled={busy}
                    onOpen={closePopovers}
                    onChange={handleSource}
                    options={[
                        { value: "screenshot", label: "Screenshot", icon: Image },
                        { value: "figma", label: "Figma", icon: Link2 },
                    ]}
                />
                <SelectMenu
                    label="Output format"
                    value={target}
                    disabled={busy}
                    onOpen={closePopovers}
                    onChange={onTarget}
                    options={[...TARGET_OPTIONS]}
                />
                {source === "screenshot" && file && (
                    <span className="file-chip">
                        <button type="button" onClick={() => setShotOpen(true)} title={file.name}>
                            <Image size={13} aria-hidden="true" />
                            <span>{file.name}</span>
                        </button>
                        <button type="button" aria-label="Remove screenshot" onClick={onClearFile} disabled={busy}>
                            <X size={12} aria-hidden="true" />
                        </button>
                    </span>
                )}
                {source === "figma" && figmaReady && (
                    <span className="file-chip">
                        <button type="button" onClick={() => setFigmaOpen(true)}>
                            <Link2 size={13} aria-hidden="true" />
                            <span>Figma frame</span>
                        </button>
                    </span>
                )}
                <div className="composer-actions">
                    <button
                        type="button"
                        className="icon-btn"
                        aria-label={source === "figma" ? "Attach a Figma link" : "Attach a screenshot"}
                        title={source === "figma" ? "Figma link" : "Attach screenshot"}
                        onClick={handleAttach}
                        disabled={busy}
                    >
                        <Paperclip size={20} aria-hidden="true" />
                    </button>
                    <button
                        type="button"
                        className={listening ? "icon-btn listening" : "icon-btn"}
                        aria-label={listening ? "Stop microphone" : "Dictate instructions"}
                        aria-pressed={listening}
                        title={listening ? "Stop microphone" : "Dictate instructions"}
                        onClick={handleMic}
                        disabled={busy}
                    >
                        <Mic size={20} aria-hidden="true" />
                    </button>
                    <button
                        type="submit"
                        className="send"
                        disabled={sendDisabled}
                        aria-label={sendLabel(sendMode)}
                        title={sendLabel(sendMode)}
                    >
                        {sendMode === "stop"
                            ? <Square size={12} fill="currentColor" aria-hidden="true" />
                            : <ArrowUp size={20} aria-hidden="true" />}
                    </button>
                </div>
            </div>
        </form>
    )
}
