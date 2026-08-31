"""Small in-memory retrieval index for the bundled Markdown knowledge base."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


class Embedder(Protocol):
    """Interface used to create embeddings without coupling retrieval to an SDK."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Create one vector for each document text."""

    def embed_query(self, text: str) -> list[float]:
        """Create one vector for a search query."""


@dataclass(frozen=True)
class KnowledgeChunk:
    text: str
    filename: str
    chunk_index: int
    score: float = 0.0


class GeminiEmbedder:
    """Gemini Developer API adapter for the retrieval index."""

    def __init__(self, api_key: str, model: str = "gemini-embedding-001") -> None:
        from google import genai

        if not api_key.strip():
            raise RuntimeError("A Gemini API key is required to build the knowledge index.")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.models.embed_content(model=self._model, contents=list(texts))
        return [list(embedding.values) for embedding in response.embeddings]

    def embed_query(self, text: str) -> list[float]:
        response = self._client.models.embed_content(model=self._model, contents=text)
        return list(response.embeddings[0].values)


class KnowledgeIndex:
    """A read-only, cosine-ranked index suited to a small demo corpus."""

    def __init__(
        self, chunks: Sequence[KnowledgeChunk], vectors: Sequence[Sequence[float]], embedder: Embedder
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Each knowledge chunk must have one embedding vector.")
        self._chunks = list(chunks)
        self._vectors = [list(vector) for vector in vectors]
        self._embedder = embedder

    @classmethod
    def from_markdown_directory(
        cls,
        directory: Path,
        embedder: Embedder,
        *,
        chunk_size: int = 1_200,
        chunk_overlap: int = 200,
    ) -> "KnowledgeIndex":
        if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size.")

        chunks: list[KnowledgeChunk] = []
        for path in sorted(directory.rglob("*.md")):
            if not path.is_file():
                continue
            for index, text in enumerate(chunk_text(path.read_text(encoding="utf-8"), chunk_size, chunk_overlap)):
                chunks.append(KnowledgeChunk(text=text, filename=path.name, chunk_index=index))

        vectors = embedder.embed_documents([chunk.text for chunk in chunks]) if chunks else []
        return cls(chunks, vectors, embedder)

    @property
    def size(self) -> int:
        return len(self._chunks)

    def search(self, query: str, *, top_k: int = 4) -> list[KnowledgeChunk]:
        if not query.strip() or not self._chunks or top_k <= 0:
            return []

        query_vector = self._embedder.embed_query(query)
        scored = [
            KnowledgeChunk(
                text=chunk.text,
                filename=chunk.filename,
                chunk_index=chunk.chunk_index,
                score=cosine_similarity(query_vector, vector),
            )
            for chunk, vector in zip(self._chunks, self._vectors)
        ]
        return sorted(scored, key=lambda chunk: chunk.score, reverse=True)[:top_k]


def count_markdown_chunks(
    directory: Path,
    *,
    chunk_size: int = 1_200,
    chunk_overlap: int = 200,
) -> int:
    """Count how many chunks would be created from a Markdown knowledge directory."""
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size.")

    total = 0
    for path in sorted(directory.rglob("*.md")):
        if not path.is_file():
            continue
        total += len(chunk_text(path.read_text(encoding="utf-8"), chunk_size, chunk_overlap))
    return total


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split non-empty text into overlapping bounded chunks."""
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    step = chunk_size - chunk_overlap
    for start in range(0, len(normalized), step):
        chunk = normalized[start : start + chunk_size]
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(normalized):
            break
    return chunks


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vectors must have the same dimensions.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(first * second for first, second in zip(left, right)) / (left_norm * right_norm)
