r"""
Setup (first time only):
  1. C:\Users\Bryan Ngu\Sunway Internship\langgraph\Scripts\Activate.ps1
  2. pip install python-dotenv

Run locally:
  1. C:\Users\Bryan Ngu\Sunway Internship\langgraph\Scripts\Activate.ps1
  2. cd scholarship_agent_langgraph
  3. python rag.py

Scholarship RAG (LangGraph) — FastAPI web service for Cloud Run.
Uses LangGraph + Vertex AI (Claude Sonnet 4.6) for a stateful, self-correcting RAG workflow.

── Graph flow ───────────────────────────────────────────────────────────────────
  query_rewrite     rewrite vague question for better retrieval
      ↓
  retrieve          FAISS top-k search on rewritten question
      ↓
  evaluate_context  Claude checks if context is sufficient
      ↓ sufficient (or retrieve_count ≥ 2)    ↓ insufficient → retrieve (max 1 retry)
  generate          Claude answers using retrieved context
      ↓
  verify            Claude checks answer is grounded in context
      ↓ verified (or verify_count ≥ 2)         ↓ unsupported → generate (max 1 retry)
  END
"""

import os
import numpy as np
import faiss
from pathlib import Path
from typing import List, Tuple, TypedDict
from contextlib import asynccontextmanager
import uvicorn
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from anthropic import AnthropicVertex
from langgraph.graph import StateGraph, END

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────
DOCS_DIR      = Path("docs")
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50
TOP_K         = 5
EMBED_MODEL   = "all-MiniLM-L6-v2"

LLM_MODEL   = os.environ.get("VERTEX_MODEL", "claude-sonnet-4-6")
GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_REGION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")

_index: faiss.Index = None
_chunks: List[str] = []
_embed_model: SentenceTransformer = None
_graph = None


# ── Graph state ────────────────────────────────────────────────────────────────
class RAGState(TypedDict):
    question: str
    rewritten_question: str
    context: List[str]
    answer: str
    retrieve_count: int
    verify_count: int
    context_sufficient: bool
    answer_verified: bool


# ── LLM helper ─────────────────────────────────────────────────────────────────
def llm(prompt: str) -> str:
    client = AnthropicVertex(region=GCP_REGION, project_id=GCP_PROJECT)
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


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
def build_index(docs: List[Tuple[str, str]], model: SentenceTransformer) -> Tuple[faiss.Index, List[str]]:
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


# ── Graph nodes ────────────────────────────────────────────────────────────────
def node_query_rewrite(state: RAGState) -> dict:
    rewritten = llm(
        "Rewrite this question to be more specific for searching a scholarship knowledge base.\n"
        "Return only the rewritten question, nothing else.\n\n"
        f"Question: {state['question']}"
    )
    return {"rewritten_question": rewritten}


def node_retrieve(state: RAGState) -> dict:
    query = state["rewritten_question"] or state["question"]
    query_vec = _embed_model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(query_vec)
    _, indices = _index.search(query_vec, TOP_K)
    context = [_chunks[i] for i in indices[0]]
    return {"context": context, "retrieve_count": state["retrieve_count"] + 1}


def node_evaluate_context(state: RAGState) -> dict:
    context_text = "\n\n---\n\n".join(state["context"])
    result = llm(
        "Does the context below contain enough information to answer the question?\n"
        "Reply with only 'sufficient' or 'insufficient'.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {state['rewritten_question']}"
    )
    return {"context_sufficient": "sufficient" in result.lower()}


def node_generate(state: RAGState) -> dict:
    context_text = "\n\n---\n\n".join(state["context"])
    answer = llm(
        "Answer using only the scholarship information below.\n"
        "If the answer is not found, say 'not found in documents'.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {state['question']}"
    )
    return {"answer": answer}


def node_verify(state: RAGState) -> dict:
    context_text = "\n\n---\n\n".join(state["context"])
    result = llm(
        "Is the answer fully supported by the context below?\n"
        "Reply with only 'supported' or 'unsupported'.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Answer: {state['answer']}"
    )
    return {
        "answer_verified": "supported" in result.lower(),
        "verify_count": state["verify_count"] + 1,
    }


# ── Conditional edges ──────────────────────────────────────────────────────────
def route_after_evaluate(state: RAGState) -> str:
    # Force proceed after 1 retry (retrieve_count ≥ 2) to avoid infinite loop
    if state["context_sufficient"] or state["retrieve_count"] >= 2:
        return "generate"
    return "retrieve"


def route_after_verify(state: RAGState) -> str:
    # Force end after 1 retry (verify_count ≥ 2) to avoid infinite loop
    if state["answer_verified"] or state["verify_count"] >= 2:
        return "end"
    return "generate"


# ── Graph builder ──────────────────────────────────────────────────────────────
def build_graph():
    graph = StateGraph(RAGState)

    graph.add_node("query_rewrite",    node_query_rewrite)
    graph.add_node("retrieve",         node_retrieve)
    graph.add_node("evaluate_context", node_evaluate_context)
    graph.add_node("generate",         node_generate)
    graph.add_node("verify",           node_verify)

    graph.set_entry_point("query_rewrite")
    graph.add_edge("query_rewrite", "retrieve")
    graph.add_edge("retrieve", "evaluate_context")
    graph.add_conditional_edges(
        "evaluate_context",
        route_after_evaluate,
        {"generate": "generate", "retrieve": "retrieve"},
    )
    graph.add_edge("generate", "verify")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"end": END, "generate": "generate"},
    )

    return graph.compile()


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _index, _chunks, _embed_model, _graph
    if not DOCS_DIR.exists():
        raise RuntimeError(f"'{DOCS_DIR}' directory not found.")
    docs = load_documents(DOCS_DIR)
    if not docs:
        raise RuntimeError(f"No .txt or .pdf files found in '{DOCS_DIR}'.")
    print(f"Loaded {len(docs)} document(s): {[d[0] for d in docs]}")
    print("Loading embedding model …")
    _embed_model = SentenceTransformer(EMBED_MODEL)
    _index, _chunks = build_index(docs, _embed_model)
    _graph = build_graph()
    print("LangGraph RAG ready.")
    yield


app = FastAPI(title="Scholarship RAG (LangGraph)", lifespan=lifespan)


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
    result = _graph.invoke({
        "question": req.question,
        "rewritten_question": "",
        "context": [],
        "answer": "",
        "retrieve_count": 0,
        "verify_count": 0,
        "context_sufficient": False,
        "answer_verified": False,
    })
    return AskResponse(answer=result["answer"])




if __name__ == "__main__":
    if not DOCS_DIR.exists():
        raise RuntimeError(f"'{DOCS_DIR}' directory not found.")
    docs = load_documents(DOCS_DIR)
    if not docs:
        raise RuntimeError(f"No .txt or .pdf files found in '{DOCS_DIR}'.")
    print(f"Loaded {len(docs)} document(s): {[d[0] for d in docs]}")
    print("Loading embedding model …")
    _embed_model = SentenceTransformer(EMBED_MODEL)
    _index, _chunks = build_index(docs, _embed_model)

    chain = build_graph()

    while True:
        q = input("Question: ")
        if q.lower() in ["exit", "quit"]:
            break

        result = chain.invoke({
            "question": q,
            "rewritten_question": "",
            "context": [],
            "answer": "",
            "retrieve_count": 0,
            "verify_count": 0,
            "context_sufficient": False,
            "answer_verified": False,
        })

        print(result["answer"])