from rag.agent import KnowledgeChat
from rag.retrieval import KnowledgeChunk, KnowledgeIndex


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


def test_search_tool_returns_evidence_metadata(monkeypatch):
    index = KnowledgeIndex(
        [KnowledgeChunk("REST uses HTTP.", "rest.md", 0)], [[1.0, 0.0]], FakeEmbedder()
    )
    chat = KnowledgeChat(index, "test-key")

    result = chat.search_knowledge_base("REST")

    assert result["status"] == "ok"
    assert result["chunks"][0]["filename"] == "rest.md"
    assert chat._evidence[0].text == "REST uses HTTP."


def test_search_gmail_stores_latest_results():
    class FakeGmail:
        def search(self, query):
            return [{"from": "a@b.com", "subject": "Hello", "date": "Today", "text": "Hi"}]

    index = KnowledgeIndex(
        [KnowledgeChunk("REST uses HTTP.", "rest.md", 0)], [[1.0, 0.0]], FakeEmbedder()
    )
    chat = KnowledgeChat(index, "test-key", gmail=FakeGmail())

    result = chat.search_gmail("from:boss")

    assert result["status"] == "ok"
    assert chat.gmail_results[0]["subject"] == "Hello"
