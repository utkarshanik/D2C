import { useCallback, useEffect, useMemo, useState } from "react";

const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024; // same limit as the backend

type Props = {
    file: File | null;
    onSelect: (file: File) => void;
    disabled: boolean;
};

export function Uploader({ file, onSelect, disabled }: Props) {
    const [error, setError] = useState("");

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

    // Ctrl/Cmd+V anywhere on the page: pick up an image from the clipboard
    useEffect(() => {
        const onPaste = (e: ClipboardEvent) => {
            const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith("image/"));
            accept(item?.getAsFile());
        };
        window.addEventListener("paste", onPaste);
        return () => window.removeEventListener("paste", onPaste);
    }, [accept]);

    // URL.createObjectURL gives the <img> a temporary local address for the file;
    // the cleanup frees it when the file changes.
    const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);
    useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

    return (
        <div>
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
    );
}
