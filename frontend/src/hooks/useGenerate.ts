import { useCallback, useEffect, useRef, useState } from "react";
import type { ImageMeta, SseEvent } from "../types";

// import.meta.env.VITE_* values come from frontend/.env (Vite exposes only VITE_ ones)
const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function useGenerate() {
    const [code, setCode] = useState(""); // what the code tab shows (raw while streaming)
    const [previewCode, setPreviewCode] = useState(""); // clean HTML for the iframe = the current version
    const [history, setHistory] = useState<string[]>([]); // earlier versions, so Refine can be undone
    const [meta, setMeta] = useState<ImageMeta | null>(null);
    const [scores, setScores] = useState<number[]>([]); // SSIM before/after the last match-refine
    const [status, setStatus] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    // useRef: values we must READ inside callbacks without causing re-renders
    const abortRef = useRef<AbortController | null>(null);
    const previewRef = useRef(""); // always the latest clean code (state could be stale inside callbacks)
    const refiningRef = useRef(false); // is the current request a /refine call?
    const changedRef = useRef(false); // did this refine call actually change the code?

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
                setCode((c) => c + evt.delta); // live typing (first draft only)
                break;
            case "code": {
                if (refiningRef.current) {
                    // keep the version we are replacing; capture it NOW, before the ref changes
                    const previous = previewRef.current;
                    setHistory((h) => [...h, previous]);
                    changedRef.current = true;
                }
                previewRef.current = evt.code;
                setCode(evt.code); // replace raw text with the cleaned code
                setPreviewCode(evt.code); // only now is it safe to render in the iframe
                break;
            }
            case "score":
                setScores((prev) => [...prev, evt.score]);
                break;
            case "done":
                // After a refine that changed nothing, the last status explains why
                // ("No improvement...", "Already close..."), so do not overwrite it.
                if (!refiningRef.current) setStatus("Done");
                else if (changedRef.current) setStatus("Refined. Use Undo to go back.");
                break;
            case "error":
                setError(evt.message);
                setStatus("");
                break;
        }
    }, []);

    // Shared by generate and refine: POST a form, read the SSE stream, feed each event to handleEvent.
    const run = useCallback(
        async (path: string, form: FormData, refining: boolean) => {
            abortRef.current?.abort();
            const controller = new AbortController(); // lets the Stop button cancel the fetch
            abortRef.current = controller;
            refiningRef.current = refining;
            changedRef.current = false;

            setBusy(true);
            setError("");
            setScores([]);
            setStatus(refining ? "Refining..." : "Uploading...");

            try {
                // fetch (not EventSource): EventSource can only send GET, but we POST a file
                const res = await fetch(`${API_URL}${path}`, {
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

    // First run: screenshot (+ optional hint) in, first draft out. Starts a fresh session.
    const generate = useCallback(
        async (file: File, hint: string) => {
            setCode("");
            setPreviewCode("");
            previewRef.current = "";
            setHistory([]);
            setMeta(null);

            const form = new FormData(); // browser API: builds the multipart body FastAPI expects
            form.append("image", file);
            if (hint.trim()) form.append("hint", hint.trim());
            await run("/generate", form, false);
        },
        [run],
    );

    // Refine button: send the screenshot again plus the CURRENT code (the server keeps no state).
    // With an instruction the model applies it; without one it tries to match the original better.
    const refine = useCallback(
        async (file: File, instruction: string) => {
            if (!previewRef.current) return;
            const form = new FormData();
            form.append("image", file);
            form.append("code", previewRef.current);
            if (instruction.trim()) form.append("instruction", instruction.trim());
            await run("/refine", form, true);
        },
        [run],
    );

    // Go back to the version before the last refine. Pure frontend: no request needed.
    const undo = useCallback(() => {
        const previous = history[history.length - 1];
        if (previous === undefined) return;
        setHistory(history.slice(0, -1));
        previewRef.current = previous;
        setCode(previous);
        setPreviewCode(previous);
        setScores([]);
        setStatus("Went back to the previous version.");
    }, [history]);

    return {
        code, previewCode, meta, scores, status, error, busy,
        canUndo: history.length > 0,
        generate, refine, undo, stop,
    };
}
