// Mirrors the SSE events sent by backend/app/routes/generate.py.
// A "discriminated union": checking `evt.type` tells TypeScript which fields exist.
export type SseEvent =
    | { type: "meta"; width: number; height: number; project_id?: string; target?: string }
    | { type: "status"; message: string }
    | { type: "chunk"; delta: string }
    | { type: "code"; code: string }
    | { type: "score"; round: number; score: number } // SSIM match with the original (module 5)
    | { type: "done" }
    | { type: "error"; message: string };

export type ImageMeta = { width: number; height: number };

export type ProjectSummary = {
    id: string;
    created_at: string;
    width: number;
    height: number;
    mime: string;
    hint: string;
    target: string;
    version_count: number;
};

export type ProjectVersion = {
    id: number;
    number: number;
    created_at: string;
    code: string;
    instruction: string;
};

export type ProjectDetail = ProjectSummary & {
    target: string;
    versions: ProjectVersion[];
};

export type OpenedProject = {
    hint: string;
    file: File | null;
};
