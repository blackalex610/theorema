"""Lightweight retrieval benchmark for the NVO content pipeline (Phase 4 wrap-up).

Not a metrics dashboard (out of scope — see NVO_CONTENT_ARCHITECTURE_PLAN.md's
minimal-implementation-checklist item 6, deferred until there's an operator
who needs one). Gives a single JSON-able report an operator can run before
flipping NVO_USE_DB_RETRIEVAL / NVO_USE_EMBEDDING_RETRIEVAL on in production.
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.services.nvo_content_qa import qa_report
from app.services.nvo_content_retrieval import build_slot_pool


def benchmark_retrieval(db: Session, iterations: int = 5) -> dict:
    quality = qa_report(db)

    durations_ms = []
    for _ in range(iterations):
        start = time.perf_counter()
        build_slot_pool(db, list(range(1, 24)))
        durations_ms.append((time.perf_counter() - start) * 1000)

    durations_ms.sort()
    p50 = durations_ms[len(durations_ms) // 2]
    p95_index = min(len(durations_ms) - 1, int(len(durations_ms) * 0.95))

    return {
        "corpus_ready": quality["is_generation_ready"],
        "missing_slots": quality["missing_slots"],
        "integrity_issue_count": len(quality["integrity_issues"]),
        "latency_ms": {"p50": round(p50, 2), "p95": round(durations_ms[p95_index], 2)},
    }
