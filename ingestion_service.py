import os
import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google import genai
import chromadb
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

# Initialize Google GenAI and persistent ChromaDB clients
client = genai.Client()
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="engineering_kb")

WATCH_DIR = "./my_knowledge_folder"
os.makedirs(WATCH_DIR, exist_ok=True)

INGESTION_PROMPT = """
You are an engineering ingestion agent. Extract structured facts and retrieval chunks from the document.
Return valid JSON only without markdown formatting:
{
  "title": "Document title or main topic",
  "project": "Project name or General",
  "summary": "Core summary",
  "facts": ["Key decisions, parameters, or actions"],
  "chunks": [{"chunk_id": "c1", "text": "Self-contained text chunk", "section": "Section name"}]
}
"""

def extract_file_content(file_path: str) -> str:
    # Extract text from supported formats
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif file_path.endswith((".txt", ".md", ".csv")):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

def process_file(file_path: str):
    # Ingest document and store vector embeddings
    print(f"[*] Processing file: {file_path}")
    content = extract_file_content(file_path)
    if not content.strip():
        print(f"[!] File is empty or unsupported: {file_path}")
        return

    prompt = f"{INGESTION_PROMPT}\nFile: {file_path}\nContent:\n{content[:8000]}"
    try:
        response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        
        # Clean potential markdown backticks from response
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

        data = json.loads(raw_text)
        chunks = data.get("chunks", [])
        
        for idx, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            if not text.strip():
                continue
            emb_response = client.models.embed_content(model="models/gemini-embedding-2", contents=text)
            emb = emb_response.embeddings[0].values
            doc_id = f"{os.path.basename(file_path)}_{idx}_{int(time.time())}"
            collection.add(
                ids=[doc_id],
                embeddings=[emb],
                documents=[text],
                metadatas=[{
                    "source": file_path,
                    "project": data.get("project", "General"),
                    "title": data.get("title", "")
                }]
            )
        print(f"[+] Successfully ingested: {file_path} ({len(chunks)} chunks added)")
    except Exception as e:
        print(f"[-] Error processing {file_path}: {e}")

class IngestionHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            time.sleep(1)
            process_file(event.src_path)

if __name__ == "__main__":
    # Scan existing files in folder upon startup
    print(f"[*] Scanning existing files in {WATCH_DIR}...")
    for root, _, files in os.walk(WATCH_DIR):
        for file in files:
            if file.endswith((".pdf", ".txt", ".md", ".csv")):
                process_file(os.path.join(root, file))

    observer = Observer()
    observer.schedule(IngestionHandler(), path=WATCH_DIR, recursive=False)
    observer.start()
    print(f"[*] Watcher active. Drop files into {WATCH_DIR} to ingest.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()