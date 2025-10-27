"""
Scenario executor orchestrating retrieval + LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional

from cam_agent.config.models import ModelConfig
from cam_agent.services.formatter import (
    RetrievalContext,
    enrich_citations,
    prepare_context,
    sanitize_legal_references,
)
from cam_agent.services.models import LLMClient
from cam_agent.services.retrieval import RetrievalManager, RetrievalResult
from cam_agent.services.types import ModelOutput, QueryRequest
from cam_agent.utils.rag import build_prompt

FALLBACK_MESSAGE = (
    "I’m not confident this question is covered by the documents I have. "
    "Please add a relevant PDF or broaden the context and try again. "
    "If this relates to personal wellbeing or safety, contact a qualified health professional or emergency services immediately."
)


@dataclass(slots=True)
class ScenarioExecutor:
    """Executes a CAM scenario end-to-end for a single request."""

    config: ModelConfig
    store_dir: Optional[str] = None
    llm_client: Optional[LLMClient] = None
    min_sim: float = 0.20
    top_k: int = 12
    _retrieval: Optional[RetrievalManager] = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.llm_client is None:
            client_kwargs = {}
            if self.config.api_mode:
                client_kwargs["api_mode"] = self.config.api_mode
            if self.config.endpoint:
                client_kwargs["endpoint"] = self.config.endpoint
            auth_token = None
            if self.config.auth_env_var:
                auth_token = os.getenv(self.config.auth_env_var)
            if auth_token:
                client_kwargs["auth_token"] = auth_token
            self.llm_client = LLMClient(**client_kwargs)
        if self.config.use_rag:
            if not self.store_dir:
                raise ValueError("store_dir is required for RAG-enabled scenarios.")
            embed_model = self.config.embed_model or "sentence-transformers/all-MiniLM-L6-v2"
            self._retrieval = RetrievalManager(
                store_dir=Path(self.store_dir),
                embed_model=embed_model,
            )

    def execute(self, request: QueryRequest) -> ModelOutput:
        """Produce an LLM answer (with retrieval if configured)."""
        hits_context: RetrievalContext | None = None
        retrieval_result: RetrievalResult | None = None

        if self.config.use_rag and self._retrieval:
            retrieval_result = self._retrieval.search(
                request.question,
                top_k=self.top_k,
                min_sim=self.min_sim,
            )
            if retrieval_result.hits:
                hits_context = prepare_context(retrieval_result.hits)

        prompt = request.question
        retrieval_context_block = ""
        legend = ""

        if self.config.use_rag:
            if hits_context:
                retrieval_context_block = hits_context.ctx_block
                legend = hits_context.legend
                prompt = build_prompt(request.question, hits_context.ctx_block)
            else:
                response_text = FALLBACK_MESSAGE
                return ModelOutput(
                    text=response_text,
                    model=self.config.name,
                    prompt=prompt,
                    retrieval_context="",
                    legend="",
                    retrieved_hits=[],
                    metadata={
                        "reason": "insufficient_retrieval",
                        "min_sim": self.min_sim,
                    },
                )

        llm_response = self.llm_client.call(
            self.config.name,
            prompt,
            temperature=self.config.temperature,
            num_ctx=self.config.num_ctx,
            num_predict=self.config.num_predict,
            seed=self.config.seed,
        )

        answer_text = llm_response.text
        if hits_context:
            answer_text = enrich_citations(answer_text, hits_context)
        answer_text = sanitize_legal_references(answer_text, retrieval_context_block)

        return ModelOutput(
            text=answer_text,
            model=self.config.name,
            prompt=prompt,
            retrieval_context=retrieval_context_block,
            legend=legend,
            retrieved_hits=retrieval_result.hits if retrieval_result else [],
            metadata={"scores": retrieval_result.scores if retrieval_result else []},
        )
__all__ = ["ScenarioExecutor", "FALLBACK_MESSAGE"]
