import { useCallback, useEffect, useMemo, useState } from "react";
import { FigmaLink } from "./FigmaLink";

const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024; // same limit as the backend

type Source = "screenshot" | "figma";

type Props = {
    file: File | null;
    onSelect: (file: File) => void;
    disabled: boolean;
    onConfirmFigma: (previewId: string) => void;
};

export function Uploader({ file, onSelect, disabled, onConfirmFigma }: Props) {
    const [error, setError] = useState("");
    const [source, setSource] = useState<Source>("screenshot");

    // Quick checks in the browser. The backend re-checks everything: never trust only the client.
    const accept = useCallback(
        (candidate: File | null | undefined) => {
            if (!candidate || disabled) return;
            if (!ALLOWED_TYPES.includes(candidate.type)) return setError("Use a PNG, JPEG or WEBP image.");
            if (candidate.size > MAX_BYTES) return setError("Image is larger than 5 MB.");
            setError("");
            onSelect(candidate);
        },
        [disabled, onSelect],
    );

    // Ctrl/Cmd+V anywhere on the page: pick up an image from the clipboard.
    // Only on the screenshot tab, so a paste into the Figma link box is left alone.
    useEffect(() => {
        if (source !== "screenshot") return;
        const onPaste = (e: ClipboardEvent) => {
            const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith("image/"));
            accept(item?.getAsFile());
        };
        window.addEventListener("paste", onPaste);
        return () => window.removeEventListener("paste", onPaste);
    }, [accept, source]);

    // URL.createObjectURL gives the <img> a temporary local address for the file;
    // the cleanup frees it when the file changes.
    const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);
    useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

    return (
        <div className="source">
            <div className="source-tabs" role="tablist" aria-label="Design source">
                <button
                    type="button"
                    role="tab"
                    aria-selected={source === "screenshot"}
                    onClick={() => setSource("screenshot")}
                    disabled={disabled}
                >
                    Screenshot
                </button>
                <button
                    type="button"
                    role="tab"
                    aria-selected={source === "figma"}
                    onClick={() => setSource("figma")}
                    disabled={disabled}
                >
                    Figma link
                </button>
            </div>
            <div hidden={source !== "screenshot"}>
                <label
                    className="dropzone"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                        e.preventDefault();
                        accept(e.dataTransfer.files[0]);
                    }}
                >
                    <input type="file" accept={ALLOWED_TYPES.join(",")} hidden disabled={disabled}
                        onChange={(e) => accept(e.target.files?.[0])} />
                    {previewUrl ? <img src={previewUrl} alt="Uploaded design" /> : <span>Click, drop or paste (Ctrl+V) a screenshot</span>}
                </label>
                {error && <p className="error">{error}</p>}
            </div>
            <div hidden={source !== "figma"}>
                <FigmaLink disabled={disabled} onConfirm={onConfirmFigma} />
            </div>
        </div>
    );
}
