from __future__ import annotations

import os
import time
from typing import Any

from groq import Groq

from app.retrieve import retrieve
from app.store import SearchHit

REFUS = "Je ne dispose pas de cette information dans le corpus."

SYSTEM_PROMPT = """Tu es AssistKB Search.
Tu reponds uniquement a partir du CONTEXTE fourni.
Tu dois citer les sources utiles sous forme [source#chunk].
Si le contexte ne permet pas de repondre, reponds exactement : Je ne dispose pas de cette information dans le corpus.
Ne jamais inventer de chiffre, date, nom d'entreprise ou fait absent du contexte.
"""


def _build_context(hits: list[SearchHit]) -> str:
    """Format retrieved chunks before sending them to the LLM."""
    blocks: list[str] = []

    for hit in hits:
        source = hit.metadata.get("source", "source inconnue")
        chunk_index = hit.metadata.get("chunk_index", "?")
        blocks.append(f"SOURCE [{source}#{chunk_index}] score={hit.score:.3f}\n{hit.text}")

    return "\n\n---\n\n".join(blocks)


def _format_sources(hits: list[SearchHit]) -> list[dict[str, Any]]:
    """Return source metadata in a stable API format."""
    return [
        {
            "source": hit.metadata.get("source"),
            "chunk_index": hit.metadata.get("chunk_index"),
            "path": hit.metadata.get("path"),
            "extension": hit.metadata.get("extension"),
            "score": round(hit.score, 4),
        }
        for hit in hits
    ]


def _fallback_answer(hits: list[SearchHit]) -> str:
    """Return extractive evidence when no Groq API key is configured."""
    lines = ["Voici les passages les plus pertinents trouves dans le corpus :"]

    for hit in hits[:3]:
        source = hit.metadata.get("source", "source inconnue")
        chunk_index = hit.metadata.get("chunk_index", "?")
        excerpt = hit.text[:420].replace("\n", " ")
        lines.append(f"- [{source}#{chunk_index}] {excerpt}...")

    return "\n".join(lines)


def _call_groq(question: str, hits: list[SearchHit]) -> tuple[str, dict[str, int]]:
    """Generate a grounded answer with Groq."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    context = _build_context(hits)

    completion = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"QUESTION:\n{question}\n\nCONTEXTE:\n{context}"},
        ],
    )

    answer_text = completion.choices[0].message.content or ""
    usage = completion.usage
    tokens = {
        "prompt": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion": int(getattr(usage, "completion_tokens", 0) or 0),
    }
    return answer_text, tokens


def answer(question: str, top_k: int | None = None) -> dict[str, Any]:
    """Run the online RAG pipeline for one user question."""
    started = time.perf_counter()
    effective_top_k = top_k or int(os.environ.get("TOP_K", "5"))
    threshold = float(os.environ.get("SEUIL_SIMILARITE", "0.35"))

    hits = retrieve(question, top_k=effective_top_k)
    best_score = hits[0].score if hits else 0.0

    if not hits or best_score < threshold:
        return {
            "answer": REFUS,
            "sources": [],
            "best_score": round(best_score, 4),
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "tokens": {"prompt": 0, "completion": 0},
        }

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_key_here":
        answer_text = _fallback_answer(hits)
        tokens = {"prompt": 0, "completion": 0}
    else:
        answer_text, tokens = _call_groq(question, hits)

    return {
        "answer": answer_text,
        "sources": _format_sources(hits),
        "best_score": round(best_score, 4),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "tokens": tokens,
    }
