from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Metrics:
    """In-memory metrics used for the project demonstration."""

    latencies_ms: list[int] = field(default_factory=list)
    best_scores: list[float] = field(default_factory=list)
    prompt_tokens: list[int] = field(default_factory=list)
    completion_tokens: list[int] = field(default_factory=list)
    refusals: int = 0
    total: int = 0

    def add(self, latency_ms: int, best_score: float, refused: bool, tokens: dict | None = None) -> None:
        """Record one API request."""
        tokens = tokens or {}
        self.total += 1
        self.latencies_ms.append(latency_ms)
        self.best_scores.append(best_score)
        self.prompt_tokens.append(int(tokens.get("prompt", 0) or 0))
        self.completion_tokens.append(int(tokens.get("completion", 0) or 0))

        if refused:
            self.refusals += 1

    def snapshot(self) -> dict:
        """Return aggregated metrics for the /metrics endpoint."""
        if not self.total:
            return {
                "total": 0,
                "score_moyen": 0,
                "taux_refus": 0,
                "latence_p50_ms": 0,
                "latence_p95_ms": 0,
                "prompt_tokens_moyens": 0,
                "completion_tokens_moyens": 0,
            }

        latencies = sorted(self.latencies_ms)
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]

        return {
            "total": self.total,
            "score_moyen": round(sum(self.best_scores) / len(self.best_scores), 4),
            "taux_refus": round(self.refusals / self.total, 4),
            "latence_p50_ms": p50,
            "latence_p95_ms": p95,
            "prompt_tokens_moyens": round(sum(self.prompt_tokens) / len(self.prompt_tokens), 2),
            "completion_tokens_moyens": round(sum(self.completion_tokens) / len(self.completion_tokens), 2),
        }


metrics = Metrics()
