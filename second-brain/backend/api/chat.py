"""
Chat API — RAG chat with SSE streaming, summary, and link suggestion.

Design ref: docs/DESIGN-graph-vector-reasoning.md §9-10
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.models.schemas import ChatRequest, SuggestLinksRequest, SummarizeRequest
from backend.services.file_service import file_service
from backend.services.link_service import link_service
from backend.services.llm_service import llm_service
from backend.services.rag_service import (
    SYSTEM_PROMPT,
    retrieve_context,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(body: ChatRequest):
    """RAG chat with SSE streaming response."""
    if not llm_service.available:
        raise HTTPException(503, "Ollama is not available. Start Ollama and try again.")

    # Retrieve context
    ctx = await retrieve_context(body.question)

    # Build prompt
    system = SYSTEM_PROMPT.format(context=ctx.context_text)

    async def event_stream():
        try:
            async for token in llm_service.generate_stream(system, body.question):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.error("LLM streaming error: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        # Send sources at end
        yield f"data: {json.dumps({'sources': ctx.sources, 'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/summarize")
async def summarize_note(body: SummarizeRequest):
    """Stream an LLM summary of a note."""
    if not llm_service.available:
        raise HTTPException(503, "Ollama is not available. Start Ollama and try again.")

    # Read note content
    note_path = settings.KNOWLEDGE_DIR / body.note_path
    if not note_path.exists():
        raise HTTPException(404, f"Note not found: {body.note_path}")

    content = note_path.read_text(encoding="utf-8")

    system = (
        "Summarize the following note. Keep key points and main ideas. "
        "Be concise. Answer in the same language as the note."
    )

    async def event_stream():
        try:
            async for token in llm_service.generate_stream(system, content):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.error("Summary streaming error: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/suggest-links")
async def suggest_links(body: SuggestLinksRequest):
    """Suggest [[wiki links]] to related notes not already linked."""
    from backend.services.embedding_service import embedding_service
    from backend.services.vector_service import vector_service

    if not vector_service.available:
        return {"suggestions": []}

    # Embed current note content → find similar notes
    query_vector = await embedding_service.embed_query(body.content[:2000])
    hits = vector_service.search(query_vector, limit=15, type_filter="chunk")

    # Collect unique note paths from hits
    related_paths = list(dict.fromkeys(
        h.payload["note_path"] for h in hits
        if h.payload["note_path"] != body.note_path
    ))

    # Exclude notes already linked
    existing = set(link_service.get_forward_links(body.note_path))
    suggestions = [p for p in related_paths if p not in existing][:5]

    # Return with titles
    result = []
    for path in suggestions:
        meta = file_service.get_metadata(path)
        result.append({"path": path, "title": meta.title if meta else path})

    return {"suggestions": result}
