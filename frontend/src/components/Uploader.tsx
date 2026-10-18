import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react"
import { ALLOWED_TYPES, validateDesignFile } from "../files"

type Props = {
    file: File | null
    onSelect: (file: File) => void
    onReject?: (message: string) => void
    disabled: boolean
    active: boolean
    expanded: boolean
}

export type UploaderHandle = {
    open: () => void
    accept: (file: File | null | undefined) => void
}

export const Uploader = forwardRef<UploaderHandle, Props>(function Uploader(
    { file, onSelect, onReject, disabled, active, expanded },
    ref,
) {
    const [error, setError] = useState("")
    const inputRef = useRef<HTMLInputElement>(null)

    const accept = useCallback((candidate: File | null | undefined) => {
        if (!candidate || disabled) return
        const problem = validateDesignFile(candidate)
        if (problem) {
            setError(problem)
            onReject?.(problem)
            return
        }
        setError("")
        onSelect(candidate)
    }, [disabled, onReject, onSelect])

    useImperativeHandle(ref, () => ({
        open: () => inputRef.current?.click(),
        accept,
    }), [accept])

    useEffect(() => {
        if (!active) return
        const onPaste = (event: ClipboardEvent) => {
            const item = [...(event.clipboardData?.items ?? [])].find((entry) => entry.type.startsWith("image/"))
            const pasted = item?.getAsFile()
            if (!pasted) return
            event.preventDefault()
            accept(pasted)
        }
        window.addEventListener("paste", onPaste)
        return () => window.removeEventListener("paste", onPaste)
    }, [accept, active])

    const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file])
    useEffect(() => () => {
        if (previewUrl) URL.revokeObjectURL(previewUrl)
    }, [previewUrl])

    return (
        <div className="uploader-root">
            <input
                ref={inputRef}
                id="design-file"
                className="file-input"
                type="file"
                accept={ALLOWED_TYPES.join(",")}
                tabIndex={-1}
                aria-label="Screenshot file"
                disabled={disabled}
                onChange={(event) => {
                    accept(event.target.files?.[0])
                    event.target.value = ""
                }}
            />
            {expanded && (
                <div className="composer-popover" role="dialog" aria-label="Screenshot">
                    <label
                        className="dropzone"
                        htmlFor="design-file"
                        onDragOver={(event) => event.preventDefault()}
                        onDrop={(event) => {
                            event.preventDefault()
                            event.stopPropagation()
                            accept(event.dataTransfer.files[0])
                        }}
                    >
                        {previewUrl
                            ? <img src={previewUrl} alt="Uploaded design" />
                            : <span>Click, drop, or paste a PNG, JPEG, or WEBP screenshot</span>}
                    </label>
                    {error && <p className="error" role="alert">{error}</p>}
                </div>
            )}
        </div>
    )
})
