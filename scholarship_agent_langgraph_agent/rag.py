r"""
Setup (first time only):
  1. C:\Users\Bryan Ngu\Sunway Internship\langgraph\Scripts\Activate.ps1
  2. pip install python-dotenv

Run locally:
  1. C:\Users\Bryan Ngu\Sunway Internship\langgraph\Scripts\Activate.ps1
  2. cd scholarship_agent_langgraph_agent
  3. python rag.py


Scholarship RAG (Agent Loop) — FastAPI web service for Cloud Run.
Uses LangGraph + Vertex AI (Claude Sonnet 4.6) with a dynamic LLM planner.

── Startup (once) ──────────────────────────────────────────────────────────────
  docs/ (.txt / .pdf)
    → read raw text from each file
    → split into 500-char overlapping chunks
    → SentenceTransformer (all-MiniLM-L6-v2)  embed each chunk
    → FAISS IndexFlatIP + L2 normalize         cosine similarity index

── Per request (POST /ask) ─────────────────────────────────────────────────────
  user question
    → planner   Claude decides: retrieve | rewrite | generate | finish
        ↓ retrieve   FAISS top-5 search               → back to planner
        ↓ rewrite    Claude rewrites the question     → back to planner
        ↓ generate   Claude answers with context      → back to planner
        ↓ finish     return current answer as final
    (max 3 planner loops to prevent infinite cycles)
"""

import json
import os
import re
from contextlib import asynccontextmanager
from typing import List

import faiss
import numpy as np
from anthropic import AnthropicVertex
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langgraph.graph import END, StateGraph
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing_extensions import TypedDict

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────
DOCS_DIR      = "docs"
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50
TOP_K         = 5
EMBED_MODEL   = "all-MiniLM-L6-v2"
MAX_LOOPS     = 3

LLM_MODEL   = os.environ.get("VERTEX_MODEL", "claude-sonnet-4-6")
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GCP_REGION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")

if not GCP_PROJECT:
    raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set. Check your .env file.")

_embed_model: SentenceTransformer = None
_index: faiss.IndexFlatIP = None
_chunks: List[str] = []
_graph = None


# ── LLM helper ─────────────────────────────────────────────────────────────────
def llm(prompt: str) -> str:
    client = AnthropicVertex(region=GCP_REGION, project_id=GCP_PROJECT)
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── Agent state ────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    question: str
    rewritten_question: str
    context: List[str]
    answer: str
    loop_count: int
    planned_action: str
    action_history: List[str]


# ── Planner node ───────────────────────────────────────────────────────────────
def node_planner(state: AgentState) -> dict:
    history_str    = ", ".join(state["action_history"]) if state["action_history"] else "none yet"
    context_status = f"yes ({len(state['context'])} chunks)" if state["context"] else "no"
    answer_status  = "yes" if state["answer"] else "no"

    response = llm(
        "You are a planning agent for a scholarship Q&A system.\n"
        "Decide the single next action based on the current state.\n\n"
        f"Question: {state['question']}\n"
        f"Actions taken so far: {history_str}\n"
        f"Context retrieved: {context_status}\n"
        f"Answer generated: {answer_status}\n\n"
        "Available actions:\n"
        "- retrieve: search the scholarship knowledge base\n"
        "- rewrite: improve the question for a better search result\n"
        "- generate: produce the final answer using retrieved context\n"
        "- finish: return the current answer as the final response\n\n"
        "Decision rules:\n"
        "- No context yet → retrieve (or rewrite first if the question is vague)\n"
        "- Context retrieved but no answer → generate\n"
        "- Answer already generated → finish\n"
        "- Never repeat an action already taken\n\n"
        'Respond with ONLY valid JSON, no other text:\n'
        '{"action": "retrieve|rewrite|generate|finish", "reason": "one short sentence"}'
    )

    action = "retrieve"
    try:
        match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            action = parsed.get("action", "retrieve")
    except (json.JSONDecodeError, AttributeError):
        pass

    if action not in ("retrieve", "rewrite", "generate", "finish"):
        action = "retrieve"

    print(f"[planner] loop={state['loop_count'] + 1} → {action}")
    return {
        "planned_action": action,
        "loop_count": state["loop_count"] + 1,
    }


# ── Tool nodes ─────────────────────────────────────────────────────────────────
def node_retrieve(state: AgentState) -> dict:
    query = state["rewritten_question"] or state["question"]
    query_vec = _embed_model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(query_vec)
    _, indices = _index.search(query_vec, TOP_K)
    context = [_chunks[i] for i in indices[0] if i < len(_chunks)]
    print(f"[retrieve] {len(context)} chunks for: {query[:60]}")
    return {
        "context": context,
        "action_history": state["action_history"] + ["retrieve"],
    }


def node_rewrite(state: AgentState) -> dict:
    rewritten = llm(
        "Rewrite the following question to be more specific for searching a "
        "scholarship knowledge base. Return only the rewritten question.\n\n"
        f"Question: {state['question']}"
    )
    print(f"[rewrite] → {rewritten.strip()[:80]}")
    return {
        "rewritten_question": rewritten.strip(),
        "action_history": state["action_history"] + ["rewrite"],
    }


def node_generate(state: AgentState) -> dict:
    context_text = "\n\n---\n\n".join(state["context"]) if state["context"] else "No context available."
    question = state["rewritten_question"] or state["question"]
    answer = llm(
        "Answer the question using ONLY the scholarship information provided below.\n"
        "If the answer is not found, say 'not found in documents'.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {question}"
    )
    print(f"[generate] answer ({len(answer)} chars)")
    return {
        "answer": answer,
        "action_history": state["action_history"] + ["generate"],
    }


# ── Conditional routing ────────────────────────────────────────────────────────
def route_from_planner(state: AgentState) -> str:
    if state["loop_count"] >= MAX_LOOPS:
        print("[router] max loops reached → end")
        return "end"
    action = state["planned_action"]
    if action == "finish":
        return "end"
    return action  # "retrieve" | "rewrite" | "generate"


# ── Graph builder ──────────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("planner",  node_planner)
    g.add_node("retrieve", node_retrieve)
    g.add_node("rewrite",  node_rewrite)
    g.add_node("generate", node_generate)

    g.set_entry_point("planner")
    g.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "retrieve": "retrieve",
            "rewrite":  "rewrite",
            "generate": "generate",
            "end":      END,
        },
    )
    g.add_edge("retrieve", "planner")
    g.add_edge("rewrite",  "planner")
    g.add_edge("generate", "planner")
    return g.compile()


# ── FAISS index builder ────────────────────────────────────────────────────────
def build_index() -> None:
    global _embed_model, _index, _chunks

    import pathlib
    raw_texts = []
    for path in pathlib.Path(DOCS_DIR).rglob("*"):
        if path.suffix == ".txt":
            raw_texts.append(path.read_text(encoding="utf-8", errors="ignore"))
        elif path.suffix == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                raw_texts.append(" ".join(p.extract_text() or "" for p in reader.pages))
            except Exception:
                pass

    if not raw_texts:
        raise RuntimeError(f"No .txt or .pdf files found in '{DOCS_DIR}'.")

    full_text = "\n\n".join(raw_texts)
    step = CHUNK_SIZE - CHUNK_OVERLAP
    _chunks = [full_text[i : i + CHUNK_SIZE] for i in range(0, len(full_text), step)]
    _chunks = [c for c in _chunks if c.strip()]
    print(f"Indexed {len(_chunks)} chunks from {len(raw_texts)} file(s)")

    _embed_model = SentenceTransformer(EMBED_MODEL)
    vecs = _embed_model.encode(_chunks, convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(vecs)

    _index = faiss.IndexFlatIP(vecs.shape[1])
    _index.add(vecs)


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    build_index()
    _graph = build_graph()
    print("Agent loop ready.")
    yield


app = FastAPI(title="Scholarship RAG (Agent Loop)", lifespan=lifespan)


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
        "question":          req.question,
        "rewritten_question": "",
        "context":           [],
        "answer":            "",
        "loop_count":        0,
        "planned_action":    "",
        "action_history":    [],
    })
    return AskResponse(answer=result.get("answer") or "No answer generated.")


# ── CLI mode: python rag.py ────────────────────────────────────────────────────
if __name__ == "__main__":
    build_index()
    graph = build_graph()
    print("Ready. Type your question or 'quit' to exit.\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() in ("quit", "exit", "q"):
            break
        result = graph.invoke({
            "question":          question,
            "rewritten_question": "",
            "context":           [],
            "answer":            "",
            "loop_count":        0,
            "planned_action":    "",
            "action_history":    [],
        })
        print(f"\nAnswer:\n{result.get('answer', 'No answer generated.')}\n")
