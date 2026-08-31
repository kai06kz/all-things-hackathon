import email

import pytest

from rag.agent import KnowledgeChat
from rag.gmail import GmailSearch, _extract_text
from rag.retrieval import KnowledgeChunk, KnowledgeIndex


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


def test_gmail_search_requires_credentials():
    with pytest.raises(RuntimeError):
        GmailSearch("", "")
    with pytest.raises(RuntimeError):
        GmailSearch("me@gmail.com", "")


def test_search_gmail_not_configured_without_gmail():
    index = KnowledgeIndex(
        [KnowledgeChunk("REST uses HTTP.", "rest.md", 0)], [[1.0, 0.0]], FakeEmbedder()
    )
    chat = KnowledgeChat(index, "test-key")
    assert chat.search_gmail("from:boss")["status"] == "not_configured"


def test_extract_text_plain_no_transfer_encoding():
    msg = email.message_from_string("From: a@b.com\nSubject: hi\n\nhello world")
    assert _extract_text(msg) == "hello world"


def test_extract_text_html_fallback():
    msg = email.message_from_string(
        "Content-Type: text/html; charset=utf-8\n\n<p>hi <b>there</b></p>"
    )
    text = _extract_text(msg)
    assert "hi" in text
    assert "there" in text
