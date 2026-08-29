import streamlit as st
from google import genai
import chromadb
from dotenv import load_dotenv
import os
from google.cloud import firestore

if os.path.exists("service_account.json"):
    db = firestore.Client.from_service_account_json("service_account.json")
else:
    db = firestore.Client()

load_dotenv()

client = genai.Client()
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="engineering_kb")

st.set_page_config(page_title="Personal Engineering Agent", layout="wide")

# Initialize session state for chat and provenance
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_evidence" not in st.session_state:
    st.session_state.last_evidence = []

col_chat, col_evidence = st.columns([3, 2])

with col_chat:
    st.subheader("💬 Multi-turn Engineering Agent")
    
    # Display conversation history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input box
    if prompt := st.chat_input("Ask about past project decisions, architecture, or risks:"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        count = collection.count()
        if count == 0:
            bot_reply = "Knowledge base is empty. Ingest files or run sync first."
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
        else:
            with st.spinner("Retrieving knowledge and synthesizing..."):
                # Vector retrieval
                query_emb = client.models.embed_content(
                    model="models/gemini-embedding-2", 
                    contents=prompt
                ).embeddings[0].values
                
                n_res = min(3, count)
                results = collection.query(query_embeddings=[query_emb], n_results=n_res)
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                
                context = "\n".join([
                    f"[Source: {m.get('source')} | Project: {m.get('project')}]: {d}" 
                    for d, m in zip(docs, metas)
                ])

                # Build chat history string for multi-turn context
                history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-4:]])

                agent_prompt = f"""
You are an engineering partner assistant.
Answer the user based on the retrieved context and prior dialogue.
Always cite the source document.
At the very end of your response, proactively suggest ONE relevant engineering follow-up question or risk to verify.

Context:
{context}

Recent Dialogue:
{history_str}

User Question: {prompt}
"""
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=agent_prompt
                )
                
                bot_reply = response.text
                with st.chat_message("assistant"):
                    st.markdown(bot_reply)
                
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                st.session_state.last_evidence = list(zip(docs, metas))
                
                # Save to Firestore
                try:
                    db.collection("chat_history").add({
                        "question": prompt,  # Fixed variable name
                        "answer": response.text,
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                except Exception as e:
                    print(f"Firestore logging skipped: {e}")

with col_evidence:
    st.subheader("📑 Provenance Evidence")
    if st.session_state.last_evidence:
        for doc, meta in st.session_state.last_evidence:
            with st.expander(f"{meta.get('title', 'Document')} ({meta.get('project')})", expanded=True):
                st.caption(f"Source: `{meta.get('source')}`")
                st.write(doc)
    else:
        st.info("Ask a question to see retrieved evidence chunks.")