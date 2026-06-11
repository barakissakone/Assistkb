from __future__ import annotations

import csv
import sys
from pathlib import Path
from statistics import mean
from typing import Any

# Permet d'exécuter ce script depuis la racine du projet :
# python analytics/eval_topk.py
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generate import REFUS, answer


OUTPUT_DIR = ROOT / "analytics"
OUTPUT_CSV = OUTPUT_DIR / "topk_results.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "topk_summary.md"

TOP_K_VALUES = [3, 5, 8]

QUESTIONS = [
    {
        "type": "corpus",
        "question": "Comment reduire les hallucinations dans AssistKB ?",
        "expected": "reponse",
    },
    {
        "type": "corpus",
        "question": "Quelles mesures de securite sont recommandees pour les donnees personnelles ?",
        "expected": "reponse",
    },
    {
        "type": "hors_corpus",
        "question": "Quelle est la capitale de l Australie ?",
        "expected": "refus",
    },
    {
        "type": "hors_corpus",
        "question": "Quel est le chiffre d affaires 2025 de la societe banque-alpha ?",
        "expected": "refus",
    },
]


def normalize_decision(result: dict[str, Any]) -> str:
    """Convertit la réponse API en décision simple : reponse ou refus."""
    response_text = str(result.get("answer", "")).strip()
    sources = result.get("sources", [])

    if response_text == REFUS:
        return "refus"

    if not sources:
        return "refus"

    return "reponse"


def sources_to_text(sources: list[dict[str, Any]], limit: int = 3) -> str:
    """Formate les principales sources pour le CSV."""
    formatted_sources = []

    for source in sources[:limit]:
        name = source.get("source", "unknown")
        chunk_index = source.get("chunk_index", "?")
        score = source.get("score", 0)
        formatted_sources.append(f"{name}#{chunk_index} score={score}")

    return " | ".join(formatted_sources)


def run_evaluation() -> list[dict[str, Any]]:
    """Exécute les questions de test pour plusieurs valeurs de top_k."""
    rows: list[dict[str, Any]] = []

    for top_k in TOP_K_VALUES:
        print(f"\nEvaluation avec top_k={top_k}")

        for item in QUESTIONS:
            question = item["question"]
            print(f"- {question}")

            result = answer(question=question, top_k=top_k)

            tokens = result.get("tokens", {}) or {}
            sources = result.get("sources", []) or []
            decision = normalize_decision(result)
            status = "OK" if decision == item["expected"] else "A_VERIFIER"

            rows.append(
                {
                    "top_k": top_k,
                    "type": item["type"],
                    "question": question,
                    "expected": item["expected"],
                    "decision": decision,
                    "status": status,
                    "best_score": result.get("best_score", 0),
                    "latency_ms": result.get("latency_ms", 0),
                    "prompt_tokens": tokens.get("prompt", 0),
                    "completion_tokens": tokens.get("completion", 0),
                    "total_tokens": int(tokens.get("prompt", 0) or 0)
                    + int(tokens.get("completion", 0) or 0),
                    "sources": sources_to_text(sources),
                }
            )

    return rows


def write_csv(rows: list[dict[str, Any]]) -> None:
    """Écrit le tableau complet au format CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "top_k",
        "type",
        "question",
        "expected",
        "decision",
        "status",
        "best_score",
        "latency_ms",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "sources",
    ]

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, Any]]) -> None:
    """Écrit une synthèse Markdown exploitable dans le compte rendu."""
    lines = [
        "# Evaluation top-k",
        "",
        "| TOP_K | Score moyen | Taux de refus | Latence moyenne | Tokens moyens | Tests OK |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    for top_k in TOP_K_VALUES:
        subset = [row for row in rows if row["top_k"] == top_k]

        avg_score = mean(float(row["best_score"] or 0) for row in subset)
        avg_latency = mean(float(row["latency_ms"] or 0) for row in subset)
        avg_tokens = mean(int(row["total_tokens"] or 0) for row in subset)
        refusal_rate = sum(1 for row in subset if row["decision"] == "refus") / len(subset)
        ok_count = sum(1 for row in subset if row["status"] == "OK")

        lines.append(
            f"| {top_k} | {avg_score:.4f} | {refusal_rate:.2%} | "
            f"{avg_latency:.0f} ms | {avg_tokens:.0f} | {ok_count}/{len(subset)} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Un top_k faible réduit la quantité de contexte envoyée au LLM, mais peut manquer une source utile.",
            "- Un top_k élevé augmente le contexte disponible, mais peut ajouter du bruit et consommer plus de tokens.",
            "- Le seuil de similarité permet de refuser les questions hors corpus afin de limiter les hallucinations.",
        ]
    )

    OUTPUT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = run_evaluation()
    write_csv(rows)
    write_summary(rows)

    print("\nEvaluation terminee.")
    print(f"CSV : {OUTPUT_CSV}")
    print(f"Synthese : {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()