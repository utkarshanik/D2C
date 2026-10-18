"""FastAPI app, CORS, and router registration."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import init_db
from app.routes.figma import router as figma_router
from app.routes.generate import router as generate_router
from app.routes.projects import router as projects_router
from app.routes.render import router as render_router
from app.routes.refine import router as refine_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Design to code", description="Generate code from design", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Register the generate router
app.include_router(generate_router)
app.include_router(figma_router)
app.include_router(render_router)
app.include_router(refine_router)
app.include_router(projects_router)

@app.get("/health")
def health():
    return {"status": "ok"}