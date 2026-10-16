import { useCallback, useEffect, useRef, useState } from "react";
import type { ImageMeta, SseEvent } from "../types";

// import.meta.env.VITE_* values come from frontend/.env (Vite exposes only VITE_ ones)
const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function useGenerate() {
    const [code, setCode] = useState(""); // what the code tab shows (raw while streaming)
    const [previewCode, setPreviewCode] = useState(""); // clean final HTML for the iframe
    const [meta, setMeta] = useState<ImageMeta | null>(null);
    const [status, setStatus] = useState("");
    const [scores, setScores] = useState<number[]>([]); // SSIM per round: draft, then each fix
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    // useRef: holds the AbortController between renders without causing re-renders
    const abortRef = useRef<AbortController | null>(null);

    const stop = useCallback(() => abortRef.current?.abort(), []);
    useEffect(() => () => abortRef.current?.abort(), []); // cancel the request if the page unmounts

    const handleEvent = useCallback((evt: SseEvent) => {
        switch (evt.type) {
            case "meta":
                setMeta({ width: evt.width, height: evt.height });
                break;
            case "status":
                setStatus(evt.message);
                break;
            case "chunk":
                setCode((c) => c + evt.delta); // live typing
                break;
            case "code":
                setCode(evt.code); // replace raw text with the cleaned code
                setPreviewCode(evt.code); // only now is it safe to render in the iframe
                break;
            case "score":
                setScores((prev) => [...prev, evt.score]);
                break;
            case "done":
                setStatus("Done");
                break;
            case "error":
                setError(evt.message);
                setStatus("");
                break;
        }
    }, []);

    const generate = useCallback(
        async (file: File, hint: string) => {
            abortRef.current?.abort();
            const controller = new AbortController(); // lets the Stop button cancel the fetch
            abortRef.current = controller;

            setBusy(true);
            setCode("");
            setPreviewCode("");
            setMeta(null);
            setScores([]);
            setError("");
            setStatus("Uploading...");

            const form = new FormData(); // browser API: builds the multipart body FastAPI expects
            form.append("image", file);
            if (hint.trim()) form.append("hint", hint.trim());

            try {
                // fetch (not EventSource): EventSource can only send GET, but we POST a file
                const res = await fetch(`${API_URL}/generate`, {
                    method: "POST",
                    body: form,
                    signal: controller.signal,
                });

                if (!res.ok || !res.body) {
                    // 400/413 arrive as normal HTTP errors, before streaming starts
                    const body = await res.json().catch(() => null);
                    throw new Error(body?.detail ?? `Request failed (${res.status})`);
                }

                const reader = res.body.getReader(); // read the response as it arrives
                const decoder = new TextDecoder(); // bytes -> text
                let buffer = "";

                for (; ;) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    // network chunks don't line up with SSE messages, so buffer and split on the blank line
                    buffer += decoder.decode(value, { stream: true });
                    const messages = buffer.split("\n\n");
                    buffer = messages.pop() ?? ""; // the last piece may be incomplete: keep it

                    for (const message of messages) {
                        if (!message.startsWith("data: ")) continue;
                        let evt: SseEvent;
                        try {
                            evt = JSON.parse(message.slice(6)) as SseEvent;
                        } catch {
                            continue; // ignore a malformed message instead of crashing the stream
                        }
                        handleEvent(evt);
                    }
                }
            } catch (err) {
                if ((err as Error).name === "AbortError") setStatus("Stopped");
                else setError((err as Error).message);
            } finally {
                setBusy(false);
            }
        },
        [handleEvent],
    );

    return { code, previewCode, meta, scores, status, error, busy, generate, stop };
}
