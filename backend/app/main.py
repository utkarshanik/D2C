"""FastAPI app, CORS, and router registration."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.generate import router as generate_router
from app.routes.render import router as render_router
from app.routes.refine import router as refine_router
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = FastAPI(title="Design to code", description="Generate code from design", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Register the generate router
app.include_router(generate_router)
app.include_router(render_router)
app.include_router(refine_router)

@app.get("/health")
def health():
    return {"status": "ok"}