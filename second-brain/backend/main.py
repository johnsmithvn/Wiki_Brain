import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import assets, daily, graph, notes, search, tags, templates
from backend.config import settings
from backend.services.file_service import file_service
from backend.services.index_service import index_service
from backend.services.link_service import link_service
from backend.services.tag_service import tag_service
from backend.services.watcher_service import watcher_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _build_initial_index() -> None:
    logger.info("Building search index...")
    all_notes = file_service.list_all_notes()
    index_data: list[dict] = []

    for meta in all_notes:
        try:
            path = (settings.KNOWLEDGE_DIR / meta.path).resolve()
            content = path.read_text(encoding="utf-8")
            extracted_tags = tag_service.update_tags(meta.path, content)
            link_service.register_path(meta.path)
            index_data.append({
                "path": meta.path,
                "title": meta.title,
                "content": content,
                "tags": extracted_tags,
            })
        except Exception as e:
            logger.warning(f"Failed to index {meta.path}: {e}")

    # Build links after all paths are registered
    for data in index_data:
        link_service.update_links(data["path"], data["content"])

    index_service.reindex_all(index_data)
    logger.info(f"Indexed {len(index_data)} notes")


def _create_welcome_note() -> None:
    welcome_path = settings.KNOWLEDGE_DIR / "Welcome.md"
    if not welcome_path.exists():
        welcome_path.write_text(
            """# Welcome to Second Brain 🧠

This is your personal knowledge base. Start creating notes and connecting your ideas!

## Getting Started

- Create a new note using the **+** button in the sidebar
- Use `[[wiki-links]]` to connect notes together
- Add `#tags` to organize your knowledge
- Use the graph view to visualize connections

## Features

- ✍️ **Markdown Editor** — Write with full markdown support
- 🔗 **Bi-directional Links** — Connect ideas with `[[links]]`
- 🕸️ **Graph View** — See how your knowledge connects
- 🔍 **Full-text Search** — Find anything instantly
- 📁 **Folders & Tags** — Organize your way
- 🌙 **Dark Mode** — Easy on the eyes

## Example Link

Check out [[Getting Started]] for more tips!

#welcome #second-brain
""",
            encoding="utf-8",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    _create_welcome_note()
    index_service.initialize()
    _build_initial_index()
    try:
        watcher_service.start()
    except Exception as e:
        logger.warning(f"Watcher failed to start. Running in degraded mode: {e}")
    logger.info(f"Second Brain started — serving from {settings.KNOWLEDGE_DIR}")
    yield
    watcher_service.stop()
    index_service.close()
    logger.info("Second Brain shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_cache_control_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# API routes
app.include_router(notes.router)
app.include_router(search.router)
app.include_router(graph.router)
app.include_router(tags.router)
app.include_router(daily.router)
app.include_router(assets.router)
app.include_router(templates.router)

# Serve uploaded assets
assets_dir = settings.KNOWLEDGE_DIR / "_assets"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/assets/files", StaticFiles(directory=str(assets_dir)), name="assets")

# Serve frontend
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
