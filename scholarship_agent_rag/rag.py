"""
run 
.\rag-env\Scripts\Activate.ps1

then 
$env:GOOGLE_CLOUD_PROJECT = "brain-433706"
$env:GOOGLE_CLOUD_LOCATION = "asia-southeast1"
$env:VERTEX_MODEL = "claude-sonnet-4-6"
python rag.py


Scholarship RAG — FastAPI web service for Cloud Run.
Uses Vertex AI (Claude Sonnet 4.6) for answer generation.

── Startup (once) ──────────────────────────────────────────────────────────────
  docs/ (.txt / .pdf)
    → load_documents()       read raw text from each file
    → chunk_text()           split into 500-char overlapping chunks
    → SentenceTransformer    embed each chunk → float32 vectors
    → faiss.IndexFlatIP      store normalised vectors (cosine similarity)

── Per request (POST /ask) ─────────────────────────────────────────────────────
  user question
    → SentenceTransformer    embed the question → query vector
    → FAISS index.search()   find top-5 most similar chunks
    → AnthropicVertex        send chunks + question to Claude Sonnet 4.6
    → return answer (JSON)
"""

import os
import numpy as np
import faiss
from pathlib import Path
from typing import List, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from anthropic import AnthropicVertex


# ── Configuration ──────────────────────────────────────────────────────────────
DOCS_DIR    = Path("docs")
CHUNK_SIZE  = 500
CHUNK_OVERLAP = 50
TOP_K       = 5
EMBED_MODEL = "all-MiniLM-L6-v2"

# Vertex AI — verify this model ID in GCP Vertex AI Model Garden if needed
LLM_MODEL   = os.environ.get("VERTEX_MODEL", "claude-sonnet-4-6")
GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_REGION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")


# ── Global index state (built once at startup) ─────────────────────────────────
_index: faiss.Index = None
_chunks: List[str] = []
_embed_model: SentenceTransformer = None


# ── Document loading ───────────────────────────────────────────────────────────
def load_documents(docs_dir: Path) -> List[Tuple[str, str]]:
    docs = []
    for path in sorted(docs_dir.iterdir()):
        if path.suffix == ".txt":
            docs.append((path.name, path.read_text(encoding="utf-8")))
        elif path.suffix == ".pdf":
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            docs.append((path.name, text))
    return docs


# ── Chunking ───────────────────────────────────────────────────────────────────
def chunk_text(text: str) -> List[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c.strip()]


# ── Index building ─────────────────────────────────────────────────────────────
def build_index(
    docs: List[Tuple[str, str]], model: SentenceTransformer
) -> Tuple[faiss.Index, List[str]]:
    all_chunks = []
    for filename, text in docs:
        for chunk in chunk_text(text):
            all_chunks.append(f"[Source: {filename}]\n{chunk}")

    print(f"Embedding {len(all_chunks)} chunks …")
    embeddings = model.encode(all_chunks, show_progress_bar=True, convert_to_numpy=True)
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    print(f"FAISS index ready — {index.ntotal} vectors.")
    return index, all_chunks


# ── Retrieval ──────────────────────────────────────────────────────────────────
def retrieve(query: str) -> List[str]:
    query_vec = _embed_model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(query_vec)
    _, indices = _index.search(query_vec, TOP_K)
    return [_chunks[i] for i in indices[0]]


# ── LLM answer generation via Vertex AI ───────────────────────────────────────
def generate_answer(question: str, context_chunks: List[str]) -> str:
    client = AnthropicVertex(region=GCP_REGION, project_id=GCP_PROJECT)
    context = "\n\n---\n\n".join(context_chunks)

    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Answer the question using only the scholarship information provided below.\n"
                    "If the answer is not in the context, say so clearly.\n\n"
                    f"CONTEXT:\n{context}\n\n"
                    f"QUESTION: {question}"
                ),
            }
        ],
    )
    return response.content[0].text


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _index, _chunks, _embed_model
    if not DOCS_DIR.exists():
        raise RuntimeError(f"'{DOCS_DIR}' directory not found — add scholarship docs and rebuild the image.")
    docs = load_documents(DOCS_DIR)
    if not docs:
        raise RuntimeError(f"No .txt or .pdf files found in '{DOCS_DIR}'.")
    print(f"Loaded {len(docs)} document(s): {[d[0] for d in docs]}")
    print("Loading embedding model …")
    _embed_model = SentenceTransformer(EMBED_MODEL)
    _index, _chunks = build_index(docs, _embed_model)
    yield


app = FastAPI(title="Scholarship RAG", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    context_chunks = retrieve(req.question)
    answer = generate_answer(req.question, context_chunks)
    return AskResponse(answer=answer)


# ── CLI mode: python rag.py ────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = load_documents(DOCS_DIR)
    if not docs:
        print(f"No documents found in '{DOCS_DIR}'. Add .txt or .pdf files and retry.")
        raise SystemExit(1)

    print(f"Loaded {len(docs)} document(s)")
    print("Loading embedding model …")
    _embed_model = SentenceTransformer(EMBED_MODEL)
    _index, _chunks = build_index(docs, _embed_model)
    print("Ready. Type your question or 'quit' to exit.\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() in ("quit", "exit", "q"):
            break
        answer = generate_answer(question, retrieve(question))
        print(f"\nAnswer:\n{answer}\n")
