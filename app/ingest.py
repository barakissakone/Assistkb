from __future__ import annotations

import csv
import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - useful when running outside Docker before installing dependencies.
    PdfReader = None

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIRS = [ROOT / "corpus" / "seed", ROOT / "corpus" / "raw"]
SUPPORTED_EXTENSIONS = {".html", ".htm", ".txt", ".md", ".json", ".csv", ".pdf"}


@dataclass(frozen=True)
class Chunk:
    """Text fragment indexed in the vector store.

    Attributes:
        id: Stable UUID accepted by Qdrant.
        text: Chunk content used for embeddings and answer generation.
        metadata: Source information returned by the API for traceability.
    """

    id: str
    text: str
    metadata: dict[str, Any]


def clean_html(path: Path) -> str:
    """Extract readable text from an HTML document."""
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def read_json(path: Path) -> str:
    """Read a JSON file and serialize it as plain text.

    The goal is not to preserve the full JSON structure for analytics, but to make
    its content searchable by the RAG pipeline.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return json.dumps(data, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def read_csv(path: Path, max_rows: int = 500) -> str:
    """Read a CSV file as text, limiting the number of rows for the MVP."""
    lines: list[str] = []

    with path.open("r", encoding="utf-8", errors="ignore", newline="") as file:
        sample = file.read(4096)
        file.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(file, dialect)
        for row_index, row in enumerate(reader):
            if row_index >= max_rows:
                break
            cleaned = [cell.strip() for cell in row if cell.strip()]
            if cleaned:
                lines.append(" | ".join(cleaned))

    return "\n".join(lines)


def read_pdf(path: Path, max_pages: int | None = None) -> str:
    """Extract text from a PDF file with a page limit.

    The limit prevents a very large public PDF from making indexing too slow for a
    one-day practical project. It can be changed with PDF_MAX_PAGES in .env.
    """
    if PdfReader is None:
        print(f"[ingest] PDF ignore {path.name}: pypdf is not installed")
        return ""

    limit = max_pages or int(os.environ.get("PDF_MAX_PAGES", "30"))
    pages: list[str] = []

    try:
        reader = PdfReader(str(path))
        for page_index, page in enumerate(reader.pages):
            if page_index >= limit:
                break
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
    except Exception as exc:  # PDF extraction can fail on malformed or protected files.
        print(f"[ingest] PDF ignore {path.name}: {exc}")
        return ""

    return "\n\n".join(pages)


def read_document(path: Path) -> str:
    """Read a supported corpus file and return normalized text."""
    suffix = path.suffix.lower()

    if suffix in {".html", ".htm"}:
        return clean_html(path)
    if suffix == ".json":
        return read_json(path)
    if suffix == ".csv":
        return read_csv(path)
    if suffix == ".pdf":
        return read_pdf(path)

    return path.read_text(encoding="utf-8", errors="ignore")


def split_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    """Split text into overlapping word chunks.

    Overlap is used to avoid losing context when an important sentence is located
    near a chunk boundary.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    words = text.split()
    if not words:
        return []

    min_words = int(os.environ.get("MIN_CHUNK_WORDS", "40"))
    step = chunk_size - overlap
    chunks: list[str] = []

    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if len(chunk_words) < min_words:
            continue
        chunks.append(" ".join(chunk_words))

    return chunks


def build_chunk_id(path: Path, index: int, text: str) -> str:
    """Build a stable UUID compatible with Qdrant point IDs."""
    relative_path = path.relative_to(ROOT).as_posix()
    raw_id = f"{relative_path}:{index}:{text[:120]}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))


def load_chunks() -> list[Chunk]:
    """Load every supported document from the seed and raw corpora."""
    chunks: list[Chunk] = []

    for directory in CORPUS_DIRS:
        if not directory.exists():
            continue

        for path in sorted(directory.rglob("*")):
            suffix = path.suffix.lower()
            if not path.is_file() or suffix not in SUPPORTED_EXTENSIONS:
                continue

            text = read_document(path)
            if not text.strip():
                continue

            for index, chunk_text in enumerate(split_text(text)):
                chunks.append(
                    Chunk(
                        id=build_chunk_id(path, index, chunk_text),
                        text=chunk_text,
                        metadata={
                            "source": path.name,
                            "chunk_index": index,
                            "path": str(path.relative_to(ROOT)),
                            "extension": suffix,
                        },
                    )
                )

    return chunks


if __name__ == "__main__":
    loaded_chunks = load_chunks()
    print(f"[ingest] {len(loaded_chunks)} chunks charges")
    for chunk in loaded_chunks[:3]:
        print(asdict(chunk) | {"text": chunk.text[:160] + "..."})