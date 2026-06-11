from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field
from app.generate import answer, REFUS
from app.metrics import metrics

app = FastAPI(title="AssistKB Search - Projet A", version="1.0.0")

class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int | None = Field(default=None, ge=1, le=20)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.post("/ask")
def ask(payload: AskRequest) -> dict:
    result = answer(payload.question, top_k=payload.top_k)
    metrics.add(
        latency_ms=result.get("latency_ms", 0),
        best_score=result.get("best_score", 0.0),
        refused=result.get("answer") == REFUS,
    )
    return result

@app.get("/metrics")
def get_metrics() -> dict:
    return metrics.snapshot()