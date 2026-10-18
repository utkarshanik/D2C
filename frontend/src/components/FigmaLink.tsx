import { useEffect, useRef, useState } from "react"
import { API_URL } from "../api"

type Phase = "idle" | "loading" | "preview" | "error"

type FramePreview = {
    previewId: string
    width: number
    height: number
    name: string
}

type Props = {
    disabled: boolean
    onConfirm: (previewId: string) => void
}

const FALLBACK = "Could not load a preview from Figma. Try again."

const messageFrom = async (response: Response) => {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    if (typeof detail === "string" && detail.trim()) return detail
    return FALLBACK
}

export function FigmaLink({ disabled, onConfirm }: Props) {
    const [link, setLink] = useState("")
    const [phase, setPhase] = useState<Phase>("idle")
    const [error, setError] = useState("")
    const [preview, setPreview] = useState<FramePreview | null>(null)
    const abortRef = useRef<AbortController | null>(null)
    const requestRef = useRef(0)

    useEffect(() => () => abortRef.current?.abort(), [])

    const handleCancel = () => {
        requestRef.current += 1
        abortRef.current?.abort()
        setPreview(null)
        setError("")
        setPhase("idle")
    }

    const handlePreview = async () => {
        const figmaUrl = link.trim()
        if (!figmaUrl || disabled) return

        abortRef.current?.abort()
        const controller = new AbortController()
        abortRef.current = controller
        const requestId = requestRef.current + 1
        requestRef.current = requestId

        setPhase("loading")
        setError("")
        setPreview(null)

        try {
            const response = await fetch(`${API_URL}/figma/preview`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ figma_url: figmaUrl }),
                signal: controller.signal,
            })
            if (requestId !== requestRef.current) return
            if (!response.ok) {
                setError(await messageFrom(response))
                setPhase("error")
                return
            }
            const body = await response.json()
            if (requestId !== requestRef.current) return
            const previewId = body?.preview_id
            if (
                typeof previewId !== "string"
                || !/^[0-9a-f]{32}$/.test(previewId)
                || typeof body.width !== "number"
                || typeof body.height !== "number"
            ) {
                setError(FALLBACK)
                setPhase("error")
                return
            }
            setPreview({
                previewId,
                width: body.width,
                height: body.height,
                name: typeof body.name === "string" ? body.name : "",
            })
            setPhase("preview")
        } catch (err) {
            if ((err as Error).name === "AbortError") return
            if (requestId !== requestRef.current) return
            setError(FALLBACK)
            setPhase("error")
        }
    }

    const handleOk = () => {
        if (!preview || disabled) return
        onConfirm(preview.previewId)
    }

    const showForm = phase !== "preview"

    return (
        <div className="figma" aria-busy={phase === "loading"}>
            {showForm && (
                <label className="figma-label" htmlFor="figma-url">
                    Figma link
                    <input
                        id="figma-url"
                        type="url"
                        inputMode="url"
                        placeholder="https://www.figma.com/design/…?node-id=…"
                        value={link}
                        onChange={(e) => {
                            setLink(e.target.value)
                            if (phase === "error") {
                                setPhase("idle")
                                setError("")
                            }
                        }}
                        onKeyDown={(e) => {
                            if (e.key !== "Enter") return
                            e.preventDefault()
                            void handlePreview()
                        }}
                        disabled={disabled || phase === "loading"}
                        aria-invalid={phase === "error"}
                        aria-describedby={phase === "error" ? "figma-error" : undefined}
                    />
                </label>
            )}

            {phase === "loading" && (
                <div className="loading-row" role="status">
                    <span className="spinner" aria-hidden="true" />
                    Rendering the frame from Figma
                </div>
            )}

            {phase === "preview" && preview && (
                <div className="figma-preview">
                    <img
                        src={`${API_URL}/figma/preview/${preview.previewId}/image`}
                        alt={preview.name ? `Figma frame: ${preview.name}` : "Figma frame preview"}
                        onError={() => {
                            setPreview(null)
                            setError("That preview expired. Preview the link again.")
                            setPhase("error")
                        }}
                    />
                    <p className="muted">
                        {preview.width} × {preview.height}px
                        {preview.name ? ` · ${preview.name}` : ""}
                    </p>
                    <div className="row">
                        <button type="button" onClick={handleOk} disabled={disabled} aria-label="OK, generate code">
                            OK
                        </button>
                        <button
                            type="button"
                            className="secondary"
                            onClick={handleCancel}
                            disabled={disabled}
                            aria-label="Cancel and change link"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            )}

            {phase === "error" && (
                <p id="figma-error" className="error" role="alert">{error}</p>
            )}

            {showForm && (
                <div className="row">
                    <button
                        type="button"
                        onClick={() => void handlePreview()}
                        disabled={disabled || phase === "loading" || !link.trim()}
                    >
                        Preview
                    </button>
                    {phase === "loading" && (
                        <button type="button" className="secondary" onClick={handleCancel}>
                            Cancel
                        </button>
                    )}
                </div>
            )}
        </div>
    )
}
