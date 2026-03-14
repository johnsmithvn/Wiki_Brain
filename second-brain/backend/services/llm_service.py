"""
LLM Service — Async streaming interface to Ollama (local LLM).

Streams chat completions from Ollama's /api/chat endpoint.

Design ref: docs/DESIGN-graph-vector-reasoning.md §8
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Ollama LLM streaming client."""

    def __init__(self) -> None:
        self._base_url: str = settings.OLLAMA_URL
        self._model: str = settings.LLM_MODEL

    @property
    def available(self) -> bool:
        """Quick check — does Ollama respond?"""
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def generate_stream(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens from Ollama /api/chat."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": True,
                    "options": {"temperature": temperature},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("done"):
                        break
                    msg = data.get("message")
                    if msg:
                        token = msg.get("content", "")
                        if token:
                            yield token

    async def generate(self, system: str, user: str, temperature: float = 0.3) -> str:
        """Non-streaming completion — collects full response."""
        parts: list[str] = []
        async for token in self.generate_stream(system, user, temperature):
            parts.append(token)
        return "".join(parts)


# Singleton
llm_service = LLMService()
