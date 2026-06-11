# Evaluation top-k

| TOP_K | Score moyen | Taux de refus | Latence moyenne | Tokens moyens | Tests OK |
|---:|---:|---:|---:|---:|---:|
| 3 | 0.4083 | 50.00% | 2595 ms | 871 | 4/4 |
| 5 | 0.4083 | 50.00% | 6988 ms | 916 | 4/4 |
| 8 | 0.4083 | 50.00% | 8965 ms | 897 | 4/4 |

## Interpretation

- Un top_k faible réduit la quantité de contexte envoyée au LLM, mais peut manquer une source utile.
- Un top_k élevé augmente le contexte disponible, mais peut ajouter du bruit et consommer plus de tokens.
- Le seuil de similarité permet de refuser les questions hors corpus afin de limiter les hallucinations.