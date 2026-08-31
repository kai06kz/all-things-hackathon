"""Streamlit interface for the Google ADK knowledge-base RAG application."""
from __future__ import annotations

import asyncio
from pathlib import Path

import streamlit as st
from google.genai.errors import ClientError

from rag.agent import KnowledgeChat, create_knowledge_chat
from rag.gmail import GmailSearch

ROOT_DIR = Path(__file__).parent
KNOWLEDGE_DIR = ROOT_DIR / "my_knowledge_folder"

st.set_page_config(page_title="Knowledge RAG", page_icon=":material/menu_book:", layout="wide")


def get_chat(api_key: str, gmail: GmailSearch | None) -> KnowledgeChat:
    if "knowledge_chat" not in st.session_state:
        chat = create_knowledge_chat(KNOWLEDGE_DIR, api_key, gmail)
        asyncio.run(chat.initialize())
        st.session_state.knowledge_chat = chat
    return st.session_state.knowledge_chat


def render_evidence() -> None:
    evidence = st.session_state.get("last_evidence", [])
    with st.sidebar:
        st.header("Evidence")
        st.caption(f"{st.session_state.get('indexed_chunk_count', 0)} indexed chunks")
        if not evidence:
            st.info("Relevant source excerpts will appear here after an answer.")
            return
        for chunk in evidence:
            with st.expander(f"{chunk.filename} | relevance {chunk.score:.2f}"):
                st.write(chunk.text)


def main() -> None:
    st.title("Knowledge RAG")
    st.caption("Google ADK agent with Gemini retrieval over the bundled knowledge base.")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_evidence" not in st.session_state:
        st.session_state.last_evidence = []

    try:
        with st.sidebar:
            api_key = st.text_input(
                "Your Gemini API key",
                type="password",
                help="Used only for this browser session and never saved by the app.",
            )
            st.caption("Create a key in your own Google AI Studio project.")

            st.divider()
            st.subheader("Connect Gmail (optional)")
            gmail_addr = st.text_input("Gmail address", help="Leave empty to skip Gmail search.")
            app_password = st.text_input(
                "Gmail App Password",
                type="password",
                help="A 16-character App Password, held only in this session.",
            )
            st.caption("Enable 2-Step Verification, then create an App Password in your Google Account.")

            if st.button("Clear session", icon=":material/delete:"):
                st.session_state.clear()
                st.rerun()

        credentials = (api_key, gmail_addr, app_password)
        if (
            st.session_state.get("configured_credentials") is not None
            and st.session_state.configured_credentials != credentials
        ):
            st.session_state.pop("knowledge_chat", None)
            st.session_state.pop("indexed_chunk_count", None)
            st.session_state.messages = []
            st.session_state.last_evidence = []
        st.session_state.configured_credentials = credentials

        render_evidence()
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        with st.form("question_form", clear_on_submit=True):
            prompt = st.text_area("Ask a question", height=100)
            submitted = st.form_submit_button("Ask")
        if not submitted:
            return
        prompt = prompt.strip()
        if not prompt:
            st.warning("Enter a question before submitting.")
            return
        if not api_key.strip():
            st.error("Enter your Gemini API key in the sidebar before sending a question.")
            return

        gmail: GmailSearch | None = None
        if gmail_addr.strip() or app_password.strip():
            if not gmail_addr.strip() or not app_password.strip():
                st.warning("Enter both a Gmail address and an App Password, or leave both empty.")
                return
            gmail = GmailSearch(gmail_addr, app_password)

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar=":material/psychology:"):
            with st.spinner("Searching..."):
                chat = get_chat(api_key, gmail)
                st.session_state.indexed_chunk_count = chat._index.size
                reply, evidence = asyncio.run(chat.ask(prompt))
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.last_evidence = evidence
        st.rerun()
    except RuntimeError as error:
        st.error(str(error))
    except ClientError as error:
        if "API_KEY_INVALID" in str(error) or "API key not valid" in str(error):
            st.error("Gemini rejected the configured API key as invalid.")
            st.info("Create a valid key at https://aistudio.google.com/apikey, then paste it in the sidebar.")
        else:
            st.error(f"Gemini request failed: {error}")
    except Exception as error:
        st.error("The knowledge service is temporarily unavailable. Please try again shortly.")
        st.exception(error)


if __name__ == "__main__":
    main()
