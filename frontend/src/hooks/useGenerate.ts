import { useCallback, useEffect, useRef, useState } from "react";
import type { ImageMeta, OpenedProject, ProjectDetail, ProjectSummary, SseEvent } from "../types";

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
    const [projectId, setProjectId] = useState<string | null>(null);
    const [projects, setProjects] = useState<ProjectSummary[]>([]);

    // useRef: values we must READ inside callbacks without causing re-renders
    const abortRef = useRef<AbortController | null>(null);
    const previewRef = useRef(""); // always the latest clean code (state could be stale inside callbacks)
    const refiningRef = useRef(false); // is the current request a /refine call?
    const changedRef = useRef(false); // did this refine call actually change the code?
    const projectIdRef = useRef<string | null>(null);
    const wasBusyRef = useRef(false);

    const rememberProject = useCallback((id: string | null) => {
        projectIdRef.current = id;
        setProjectId(id);
    }, []);

    const stop = useCallback(() => abortRef.current?.abort(), []);
    useEffect(() => () => abortRef.current?.abort(), []); // cancel the request if the page unmounts

    const handleEvent = useCallback((evt: SseEvent) => {
        switch (evt.type) {
            case "meta":
                setMeta({ width: evt.width, height: evt.height });
                if (evt.project_id) rememberProject(evt.project_id);
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
                // A failed draft is deleted on the server, so forget its id.
                if (!previewRef.current.trim()) rememberProject(null);
                // After a refine that changed nothing, the last status explains why
                // ("No improvement...", "Already close..."), so do not overwrite it.
                if (!refiningRef.current) setStatus("Done");
                else if (changedRef.current) setStatus("Refined. Use Undo to go back.");
                break;
            case "error":
                setError(evt.message);
                setStatus("");
                if (!previewRef.current.trim()) rememberProject(null);
                break;
        }
    }, [rememberProject]);

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

    const refreshProjects = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/projects`);
            if (!res.ok) return;
            setProjects((await res.json()) as ProjectSummary[]);
        } catch {
            // The list is a convenience. Generate and refine already surface their own errors.
        }
    }, []);

    useEffect(() => {
        void refreshProjects();
    }, [refreshProjects]);

    useEffect(() => {
        if (wasBusyRef.current && !busy) void refreshProjects();
        wasBusyRef.current = busy;
    }, [busy, refreshProjects]);

    // First run: screenshot (+ optional hint) in, first draft out. Starts a fresh session.
    const generate = useCallback(
        async (file: File, hint: string) => {
            setCode("");
            setPreviewCode("");
            previewRef.current = "";
            setHistory([]);
            setMeta(null);
            rememberProject(null);

            const form = new FormData(); // browser API: builds the multipart body FastAPI expects
            form.append("image", file);
            if (hint.trim()) form.append("hint", hint.trim());
            await run("/generate", form, false);
        },
        [rememberProject, run],
    );

    // Refine uses the saved project: the server loads the screenshot and earlier requests.
    // The code on screen is sent too, so Undo still chooses which version the edit starts from.
    // With an instruction the model applies it; without one it tries to match the original better.
    const refine = useCallback(
        async (file: File | null, instruction: string) => {
            if (!previewRef.current) return;
            const form = new FormData();
            form.append("code", previewRef.current);
            if (instruction.trim()) form.append("instruction", instruction.trim());
            const id = projectIdRef.current;
            if (id) {
                await run(`/projects/${id}/edit`, form, true);
                return;
            }
            if (!file) return;
            form.append("image", file);
            await run("/refine", form, true);
        },
        [run],
    );

    const openProject = useCallback(async (id: string): Promise<OpenedProject | null> => {
        setError("");
        const res = await fetch(`${API_URL}/projects/${id}`);
        if (!res.ok) {
            setError("Could not open that project.");
            return null;
        }
        const project = (await res.json()) as ProjectDetail;
        const versions = project.versions;
        const latestCode = versions[versions.length - 1]?.code ?? "";
        rememberProject(project.id);
        previewRef.current = latestCode;
        setCode(latestCode);
        setPreviewCode(latestCode);
        setHistory(versions.slice(0, -1).map((version) => version.code));
        setMeta({ width: project.width, height: project.height });
        setScores([]);
        setStatus(latestCode ? "Opened a saved project." : "");

        const imageRes = await fetch(`${API_URL}/projects/${id}/image`);
        if (!imageRes.ok) return { hint: project.hint, file: null };
        const blob = await imageRes.blob();
        const ext = blob.type === "image/jpeg" ? "jpg" : blob.type === "image/webp" ? "webp" : "png";
        const file = new File([blob], `design.${ext}`, { type: blob.type || "image/png" });
        return { hint: project.hint, file };
    }, [rememberProject]);

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
        projectId, projects,
        canUndo: history.length > 0,
        generate, refine, undo, stop, openProject,
    };
}
