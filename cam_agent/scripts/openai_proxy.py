"""
Minimal OpenAI-compatible proxy for local LLM providers (e.g., Ollama).

Expose `/v1/chat/completions` and `/v1/completions` endpoints that translate
requests to the existing `LLMClient` interface.
"""

from __future__ import annotations

import argparse
import time
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from cam_agent.services import LLMClient


def build_prompt(messages: List[Dict[str, str]]) -> str:
    """Convert chat messages into a simple conversational prompt."""
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"{role.upper()}: {content}")
    lines.append("ASSISTANT:")
    return "\n".join(lines)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: float = 0.2
    max_tokens: Optional[int] = Field(default=None, alias="max_tokens")
    stream: bool = False


class CompletionRequest(BaseModel):
    model: str
    prompt: str
    temperature: float = 0.2
    max_tokens: Optional[int] = None
    stream: bool = False


def create_app(llm_client: Optional[LLMClient] = None) -> FastAPI:
    client = llm_client or LLMClient()
    app = FastAPI(title="CAM OpenAI-Compatible Proxy")

    @app.post("/v1/chat/completions")
    def chat_completions(request: ChatCompletionRequest):
        if request.stream:
            raise HTTPException(status_code=400, detail="Streaming not supported in proxy.")
        prompt = build_prompt([msg.dict() for msg in request.messages])
        try:
            response = client.call(
                request.model,
                prompt,
                temperature=request.temperature,
                num_predict=request.max_tokens,
            )
        except Exception as exc:  # pragma: no cover - runtime protection
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        now = int(time.time())
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": now,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response.text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            },
        }

    @app.post("/v1/completions")
    def completions(request: CompletionRequest):
        if request.stream:
            raise HTTPException(status_code=400, detail="Streaming not supported in proxy.")
        try:
            response = client.call(
                request.model,
                request.prompt,
                temperature=request.temperature,
                num_predict=request.max_tokens,
            )
        except Exception as exc:  # pragma: no cover - runtime protection
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        now = int(time.time())
        return {
            "id": f"cmpl-{uuid.uuid4().hex}",
            "object": "text_completion",
            "created": now,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "text": response.text,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            },
        }

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenAI-compatible proxy for local LLM provider.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

