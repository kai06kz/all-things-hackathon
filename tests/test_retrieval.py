from pathlib import Path

from rag.retrieval import KnowledgeIndex, chunk_text, cosine_similarity


class FakeEmbedder:
    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)

    @staticmethod
    def _vector(text):
        lower = text.lower()
        return [float(lower.count("rest")), float(lower.count("graphql"))]


def test_chunk_text_creates_overlapping_bounded_chunks():
    chunks = chunk_text("abcdefghij", chunk_size=6, chunk_overlap=2)

    assert chunks == ["abcdef", "efghij"]


def test_markdown_index_loads_and_ranks_documents(tmp_path: Path):
    (tmp_path / "rest.md").write_text("REST uses HTTP methods.", encoding="utf-8")
    (tmp_path / "graphql.md").write_text("GraphQL uses a typed schema.", encoding="utf-8")
    index = KnowledgeIndex.from_markdown_directory(tmp_path, FakeEmbedder())

    results = index.search("Explain REST", top_k=1)

    assert index.size == 2
    assert results[0].filename == "rest.md"
    assert results[0].score > 0


def test_empty_directory_has_no_search_results(tmp_path: Path):
    index = KnowledgeIndex.from_markdown_directory(tmp_path, FakeEmbedder())

    assert index.size == 0
    assert index.search("REST") == []


def test_cosine_similarity_handles_zero_vectors():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0