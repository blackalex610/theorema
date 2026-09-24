"""Embedding generation for the NVO problem corpus (Phase 4: hybrid retrieval).

Calls OpenAI's embeddings API and caches the result in nvo_problem_embeddings,
keyed by problem_id. Re-embeds only rows missing an embedding for the current
model, so switching OPENAI_EMBEDDING_MODEL re-embeds everything exactly once
without touching rows already embedded under the old model.

Run directly: `python -m app.services.nvo_content_embeddings`
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.services.openai_client import openai_client
from app.database import SessionLocal
from app.models.nvo_content import NvoProblem, NvoProblemEmbedding

logger = logging.getLogger(__name__)


def _embedding_text(problem: NvoProblem) -> str:
    """The text actually embedded — statement only. Options/answers are not
    semantic content worth ranking on and would bias similarity toward
    superficial option wording."""
    return problem.statement


def problems_needing_embeddings(db: Session, model: str) -> list[NvoProblem]:
    embedded_ids = {
        row.problem_id
        for row in db.query(NvoProblemEmbedding).filter_by(embedding_model=model).all()
    }
    return [
        p for p in db.query(NvoProblem).filter(NvoProblem.is_active.is_(True)).all()
        if p.id not in embedded_ids
    ]


def embed_texts(texts: list[str], model: str) -> list[list[float]]:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")
    client = openai_client()
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def backfill_embeddings(db: Session, model: str | None = None) -> dict:
    model = model or settings.OPENAI_EMBEDDING_MODEL
    pending = problems_needing_embeddings(db, model)
    if not pending:
        return {"embedded": 0, "model": model}

    vectors = embed_texts([_embedding_text(p) for p in pending], model)
    for problem, vector in zip(pending, vectors):
        db.merge(
            NvoProblemEmbedding(
                problem_id=problem.id,
                embedding_json=json.dumps(vector),
                embedding_model=model,
            )
        )
    db.commit()
    return {"embedded": len(pending), "model": model}


def run() -> dict:
    db = SessionLocal()
    try:
        return backfill_embeddings(db)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run(), indent=2))
