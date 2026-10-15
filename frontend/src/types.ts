// Mirrors the SSE events sent by backend/app/routes/generate.py.
// A "discriminated union": checking `evt.type` tells TypeScript which fields exist.
export type SseEvent =
    | { type: "meta"; width: number; height: number }
    | { type: "status"; message: string }
    | { type: "chunk"; delta: string }
    | { type: "code"; code: string }
    | { type: "done" }
    | { type: "error"; message: string };

export type ImageMeta = { width: number; height: number };