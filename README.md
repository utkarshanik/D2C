# Design to Code

Upload a UI screenshot and get matching front-end code, streamed live, with a preview and an automatic render-and-compare refinement loop.

> **For AI assistants (Cursor):** read this whole file before changing code. Follow the Rules section strictly. Build one module at a time, in the order given in the Module Roadmap, and do not implement modules that are not requested.

---

## 1. Goals

- User uploads or pastes a screenshot of a UI.
- A vision LLM generates code that recreates it (HTML + Tailwind first, React + MUI later).
- Code streams to the browser in real time; a sandboxed iframe shows the live preview.
- The backend renders the generated code in a headless browser, compares it with the original screenshot, and asks the model to fix differences (refine loop).
- Users can request follow-up edits ("make the sidebar narrower").

## 2. Hard Constraints

- **Everything must be free.** No paid APIs, no paid services, no paid hosting required to run the project.
- **Real-time UX:** generation must stream; the UI must never wait for the full response before showing progress.
- **Model-agnostic:** all LLM calls go through LiteLLM so providers can be swapped via config only.
- **Safe by default:** generated code runs only in a sandboxed iframe (`sandbox="allow-scripts"`) and is rendered only in headless Chromium on the backend.

## 3. Architecture

```
┌────────────┐   POST + SSE   ┌──────────────┐   LiteLLM   ┌──────────────────────┐
│  Frontend  │───────────────▶│ API backend  │────────────▶│ Vision LLM           │
│  React     │◀───────────────│ FastAPI      │◀────────────│ Gemini Flash (free)  │
└────────────┘                └──────┬───────┘             │ fallback: Ollama     │
                                     │                     └──────────────────────┘
                  ┌──────────────────┼──────────────────┐
                  ▼                  ▼                  ▼
           Preprocessing       Render service       SQLite + disk
           (colors, OCR)       (Playwright)         (projects, images)
```

### Request flow

1. Frontend uploads the screenshot to `POST /api/generate` (multipart).
2. Backend preprocesses the image (resize, palette, optional OCR).
3. Backend calls the vision model with the image and rules; tokens stream back as SSE `chunk` events.
4. Backend extracts the code block and sends a `code` event.
5. Refine loop (up to `REFINE_ROUNDS`): render the code with Playwright at the original screenshot size, send original and render back to the model with a "fix the differences" prompt, send the new `code` event. Stop early if the SSIM score is above the threshold.
6. Backend sends `done`. Frontend shows the final preview and code.

## 4. Tech Stack (all free)

| Layer | Choice |
|---|---|
| Frontend | React + Vite, Monaco editor, Sandpack (for React/MUI previews later) |
| Streaming | Server-Sent Events (SSE) |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Model gateway | LiteLLM |
| Primary model | Gemini Flash via Google AI Studio free tier |
| Fallback model | Ollama running locally (a vision model such as Qwen2.5-VL or Llama 3.2 Vision) |
| Rendering | Playwright (headless Chromium) |
| Image tools | Pillow, OpenCV, scikit-image (SSIM) |
| OCR | Tesseract via `pytesseract` |
| Database | SQLite via SQLAlchemy |
| File storage | Local disk |
| Component library (later) | MUI; optional MUI MCP server for docs while coding in Cursor |

Notes:
- Model names and free-tier limits change. Never hardcode a model name; read it from config.
- Free-tier requests are rate limited. Handle HTTP 429 with exponential backoff and fall back to `FALLBACK_MODEL`.
- Free-tier Gemini prompts may be used by Google to improve its products, so do not send sensitive screenshots.

## 5. Project Structure

```
design-to-code/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, router registration
│   │   ├── config.py          # pydantic-settings, reads .env
│   │   ├── routes/
│   │   │   ├── generate.py    # POST /api/generate (SSE)
│   │   │   └── projects.py    # project and version history
│   │   ├── services/
│   │   │   ├── llm.py         # LiteLLM calls, streaming, retry, fallback
│   │   │   ├── renderer.py    # Playwright render -> PNG
│   │   │   ├── preprocess.py  # resize, palette, OCR
│   │   │   └── refine.py      # compare + fix loop, SSIM stop condition
│   │   ├── prompts/           # system prompts per target (html_tailwind, react_mui)
│   │   └── db/                # SQLAlchemy models and session
│   ├── tests/
│   ├── requirements.txt
│   └── .env
├── frontend/
│   └── src/
│       ├── components/        # Uploader, CodeView, Preview
│       ├── hooks/             # useGenerate (reads the SSE stream)
│       └── api/
├── .gitignore
└── README.md
```

## 6. Setup

### Prerequisites
- Python 3.11+, Node.js 20+, Git
- Free Gemini API key from Google AI Studio
- Tesseract installed on the system (`sudo apt install tesseract-ocr`, `brew install tesseract`, or the Windows installer)
- Optional: Ollama for the local fallback model

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install fastapi "uvicorn[standard]" python-multipart pydantic-settings \
            litellm playwright pillow opencv-python-headless scikit-image \
            pytesseract sqlalchemy pytest httpx
playwright install chromium
pip freeze > requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm install @monaco-editor/react @codesandbox/sandpack-react
npm run dev                          # http://localhost:5173
```

### Environment (`backend/.env`, never commit)

```
GEMINI_API_KEY=your-key-here
PRIMARY_MODEL=gemini/<current-flash-model-name>
FALLBACK_MODEL=ollama/<local-vision-model>
REFINE_ROUNDS=2
SSIM_STOP_THRESHOLD=0.95
CORS_ORIGINS=http://localhost:5173
```

## 7. API Contract

### `POST /api/generate`

Request: `multipart/form-data`
- `image` (file, required)
- `target` (string, optional): `html_tailwind` (default) or `react_mui`
- `hint` (string, optional): extra user instructions

Response: `text/event-stream`. Each message is `data: <json>\n\n` with one of:

```json
{ "type": "status", "message": "Refining (1/2)..." }
{ "type": "chunk",  "delta": "<partial text>" }
{ "type": "code",   "code": "<full clean code>" }
{ "type": "done" }
{ "type": "error",  "message": "<readable error>" }
```

- `chunk` events are raw streamed tokens for live display.
- `code` events replace the displayed code with the cleaned version after each pass.
- Frontend reads the stream with `fetch` and a stream reader (not `EventSource`, which only supports GET).

## 8. Module Roadmap

Build in this order. Each module must work and be testable on its own before starting the next.

| # | Module | Definition of done | Status |
|---|---|---|---|
| 0 | Project setup | Backend `/health` works, Playwright takes a screenshot, one LiteLLM call returns, frontend can call backend | todo |
| 1 | LLM service (`llm.py`) | Image + prompt returns code through LiteLLM; streams; retries on 429; falls back to `FALLBACK_MODEL` | todo |
| 2 | Generate route with SSE | Tokens stream to a test client using the event contract above | todo |
| 3 | Frontend uploader + live preview | Upload/paste shows streamed code and a sandboxed iframe preview | todo |
| 4 | Renderer (`renderer.py`) | Generated HTML becomes a PNG at the original screenshot size | todo |
| 5 | Refine loop (`refine.py`) | Compare and fix runs for N rounds with SSIM early stop | todo |
| 6 | Preprocessing | Palette and OCR text are added to the prompt | done |
| 7 | Persistence | Projects and versions saved in SQLite; follow-up edits use history | done |
| 8 | React + MUI target | Sandpack preview; MUI-aware prompt with an allowed-components list | todo |

Update the Status column as modules are completed.

## 9. Prompting Guidelines

- System prompts live in `backend/app/prompts/`, one file per target. Do not inline long prompts in route code.
- Always specify the output format ("ONE self-contained HTML file", or "one React component") and require code only, inside a single fenced block.
- For MUI: pin the MUI major version in the prompt and give an explicit list of allowed components; tell the model not to invent components.
- Pass extracted exact values (hex colors, OCR text) into the prompt rather than letting the model guess.
- Refine prompt sends two images (target, then current render) plus the current code and asks for a difference list followed by full corrected code.

## 10. Rules for AI Assistants (Cursor)

1. Implement only the module requested. Do not scaffold or stub later modules.
2. Keep route handlers thin; put logic in `services/`.
3. All LLM calls go through `services/llm.py` using LiteLLM. Never import a provider SDK directly.
4. Never hardcode API keys or model names. Read from `config.py`.
5. Use async code in FastAPI routes and services. Playwright must use the async API.
6. Do not add paid services or dependencies that require a paid plan.
7. Do not change the SSE event contract in section 7 without being asked.
8. Treat all model output as untrusted: never `exec`/`eval` it on the backend; only render it in Playwright or the sandboxed iframe.
9. Handle errors by sending an SSE `error` event, never by leaving the stream hanging.
10. Add or update a test in `backend/tests/` for each backend module.
11. Keep dependencies minimal and add new ones to `requirements.txt` or `package.json`.

## 11. Testing

- Backend: `pytest` in `backend/`. Mock LiteLLM calls in unit tests; keep one opt-in integration test that uses the real model.
- Renderer: test that known HTML produces a PNG of the expected dimensions.
- Refine: test SSIM stop logic with identical and different image pairs.
- Frontend: manual test of upload, paste, streaming, stop button, and error display.

## 12. Known Risks

- **Free-tier rate limits:** cap refine rounds, back off on 429, fall back to the local model.
- **Fidelity is approximate:** the model estimates sizes and colors visually; exact color and OCR extraction plus the refine loop reduce the gap.
- **Executing generated code:** always sandbox. Run Playwright in an isolated container if deploying publicly.
- **Playwright on free hosting:** may exceed memory limits; prefer running the backend locally for demos.
