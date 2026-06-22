r"""
Setup (first time only):
  1. C:\Users\Bryan Ngu\Sunway Internship\langgraph\Scripts\Activate.ps1
  2. pip install python-dotenv

Run locally:
  1. C:\Users\Bryan Ngu\Sunway Internship\langgraph\Scripts\Activate.ps1
  2. cd scholarship_agent_langgraph_multiagent
  3. python rag.py

Scholarship RAG (Multi-Agent + Tools + Memory) — FastAPI web service for Cloud Run.
Uses LangGraph + Vertex AI (Claude Sonnet 4.6) with a 3-agent system.

── Startup (once) ──────────────────────────────────────────────────────────────
  docs/ (.txt / .pdf)
    → read raw text from each file
    → split into 500-char overlapping chunks (tagged [Source: filename])
    → SentenceTransformer (all-MiniLM-L6-v2)  embed each chunk
    → FAISS IndexFlatIP + L2 normalize         cosine similarity index

── Graph flow (Phase 6) ─────────────────────────────────────────────────────────
  Research Agent   rewrites question → calls retrieve_tool + memory_tool via tool_executor
      ↓
  Writer Agent     generates answer from context (+ critique on retry)
      ↓
  Critic Agent     evaluates grounding + correctness; returns explicit JSON verdict
      ├─ passed=true                 → END  (stores to long-term memory)
      ├─ passed=false, next=writer   → Writer retry  (max 1)
      └─ passed=false, next=research → Research retry (max 1) → Writer → Critic
  END

── Tool layer (Phase 7) ─────────────────────────────────────────────────────────
  retrieve_tool(query)      FAISS top-k cosine-similarity search
  search_tool(query)        stub delegating to retrieve_tool
  memory_tool(question)     semantic long-term memory lookup
  tool_executor(name, q)    single entry point — agents call only this, never tools directly

── Memory layer (Phase 8) ───────────────────────────────────────────────────────
  short_term_memory   context + critique in LangGraph state (per request)
  long_term_memory    embedding-based store; retrieves by cosine similarity (threshold=0.75)
                      supports rephrased/paraphrased questions — no exact match required
"""

import json
import os
import pathlib
import re
from contextlib import asynccontextmanager
from typing import Callable, Dict, List, Optional

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
DOCS_DIR         = "docs"
CHUNK_SIZE       = 500
CHUNK_OVERLAP    = 50
TOP_K            = 5
EMBED_MODEL      = "all-MiniLM-L6-v2"
MEMORY_THRESHOLD = 0.75   # cosine similarity threshold for long-term memory recall

LLM_MODEL   = os.environ.get("VERTEX_MODEL", "claude-sonnet-4-6")
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GCP_REGION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")

if not GCP_PROJECT:
    raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set.")

_embed_model: Optional[SentenceTransformer] = None
_index: Optional[faiss.IndexFlatIP] = None
_chunks: List[str] = []
_graph = None

# ── Memory Layer (Phase 8) ─────────────────────────────────────────────────────
# Embedding-based long-term memory — handles rephrased/paraphrased questions.
# Each record stores the original question, answer, and its normalized embedding.
_memory_store: List[dict] = []   # [{"question": str, "answer": str, "vec": np.ndarray}]


def memory_store(question: str, answer: str) -> None:
    vec = _embed_model.encode([question.strip()], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(vec)
    _memory_store.append({"question": question.strip(), "answer": answer, "vec": vec[0]})
    print(f"[memory] stored: {question.strip()[:60]}")


def memory_retrieve(question: str) -> Optional[str]:
    """Returns best matching past answer if cosine similarity ≥ MEMORY_THRESHOLD."""
    if not _memory_store:
        return None
    q_vec = _embed_model.encode([question.strip()], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_vec)
    best_score, best_answer = -1.0, None
    for record in _memory_store:
        score = float(np.dot(q_vec[0], record["vec"]))
        if score > best_score:
            best_score, best_answer = score, record["answer"]
    if best_score >= MEMORY_THRESHOLD:
        print(f"[memory] hit (score={best_score:.3f}): {question.strip()[:60]}")
        return best_answer
    return None


# ── LLM helper ─────────────────────────────────────────────────────────────────
def llm(prompt: str) -> str:
    client = AnthropicVertex(region=GCP_REGION, project_id=GCP_PROJECT)
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── Tool Layer (Phase 7) ───────────────────────────────────────────────────────
def retrieve_tool(query: str) -> List[str]:
    """FAISS cosine-similarity search."""
    query_vec = _embed_model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(query_vec)
    _, indices = _index.search(query_vec, TOP_K)
    results = [_chunks[i] for i in indices[0] if i < len(_chunks)]
    print(f"[retrieve_tool] {len(results)} chunks for: {query[:60]}")
    return results


def search_tool(query: str) -> List[str]:
    """Stub search tool — delegates to retrieve_tool."""
    return retrieve_tool(query)


def memory_tool(question: str) -> List[str]:
    """Long-term memory lookup via semantic similarity."""
    result = memory_retrieve(question)
    return [f"[Long-term Memory]\n{result}"] if result else []


TOOLS: Dict[str, Callable[[str], List[str]]] = {
    "retrieve": retrieve_tool,
    "search":   search_tool,
    "memory":   memory_tool,
}


def tool_executor(tool_name: str, query: str) -> List[str]:
    """Single entry point for all tool calls. Agents must use only this."""
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool '{tool_name}'. Available: {list(TOOLS)}")
    return TOOLS[tool_name](query)


# ── Graph State (Phase 6) ──────────────────────────────────────────────────────
class MultiAgentState(TypedDict):
    question: str
    rewritten_question: str   # short_term_memory: rewritten query used for retrieval
    context: List[str]        # short_term_memory: retrieved chunks for this request
    answer: str
    critique: str             # short_term_memory: critic feedback for Writer retry
    passed: bool              # explicit PASS signal from Critic (not inferred from string)
    next_action: str          # critic-controlled routing: "writer" | "research" | "end"
    writer_count: int         # Writer runs at most twice (max 1 retry)
    research_count: int       # Research can be re-triggered at most once


# ── Agent Nodes ────────────────────────────────────────────────────────────────
def node_research_agent(state: MultiAgentState) -> dict:
    """Research Agent: determines query, calls tools only — no generation logic."""
    question = state["question"]
    critique = state.get("critique", "")

    rewrite_prompt = (
        "Rewrite this question to be more specific for searching a scholarship knowledge base.\n"
        "Return only the rewritten question, nothing else.\n\n"
        f"Question: {question}"
    )
    if critique:
        rewrite_prompt += (
            f"\n\nNote: A previous search was insufficient. Critique: {critique}\n"
            "Adjust the query to find more relevant information."
        )

    rewritten = llm(rewrite_prompt).strip() or question
    print(f"[research] rewritten: {rewritten[:80]}")

    context = tool_executor("retrieve", rewritten)
    context.extend(tool_executor("memory", question))

    return {
        "context":            context,
        "rewritten_question": rewritten,
        "research_count":     state["research_count"] + 1,
    }


def node_writer_agent(state: MultiAgentState) -> dict:
    """Writer Agent: generates answer from context only — no retrieval, no evaluation."""
    context_text = "\n\n---\n\n".join(state["context"]) if state["context"] else "No context available."
    critique = state.get("critique", "")

    prompt = (
        "Answer the question using ONLY the scholarship information provided below.\n"
        "If the answer is not found, say 'not found in documents'.\n"
    )
    if critique:
        prompt += f"\nPrevious critique (you must address this): {critique}\n"
    prompt += f"\nContext:\n{context_text}\n\nQuestion: {state['question']}"

    answer = llm(prompt)
    print(f"[writer] attempt {state['writer_count'] + 1} — {len(answer)} chars")
    return {
        "answer":       answer,
        "writer_count": state["writer_count"] + 1,
    }


def node_critic_agent(state: MultiAgentState) -> dict:
    """Critic Agent: returns explicit structured verdict — no string inference for PASS/FAIL."""
    context_text = "\n\n---\n\n".join(state["context"])
    result = llm(
        "Evaluate the answer strictly against the context below.\n"
        "Check: (1) Is it fully grounded in the context? (2) Is it correct and complete?\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {state['question']}\n"
        f"Answer: {state['answer']}\n\n"
        "Reply with ONLY valid JSON (no extra text):\n"
        '{"passed": true/false, "next_action": "end"|"writer"|"research", "critique": "one sentence"}\n\n'
        "Rules:\n"
        "  passed=true  → next_action must be 'end'\n"
        "  passed=false + answer is wrong or incomplete → next_action='writer'\n"
        "  passed=false + context is insufficient to answer → next_action='research'"
    )

    passed, next_action, critique = False, "writer", result.strip()
    try:
        match = re.search(r'\{.*?\}', result, re.DOTALL)
        if match:
            data       = json.loads(match.group())
            passed     = bool(data.get("passed", False))
            next_action = data.get("next_action", "writer")
            critique   = data.get("critique", result.strip())
    except (json.JSONDecodeError, AttributeError):
        passed = result.strip().upper().startswith("PASS")

    if passed:
        next_action = "end"
        memory_store(state["question"], state["answer"])
        print("[critic] PASS — stored to long-term memory")
    else:
        print(f"[critic] FAIL — next_action={next_action}")

    return {"passed": passed, "critique": critique, "next_action": next_action}


# ── Routing ────────────────────────────────────────────────────────────────────
def route_after_critic(state: MultiAgentState) -> str:
    if state["passed"]:
        return "end"
    next_action = state.get("next_action", "writer")
    if next_action == "research" and state["research_count"] < 2:
        return "research"
    if next_action == "writer" and state["writer_count"] < 2:
        return "writer"
    return "end"


# ── Graph Builder ──────────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(MultiAgentState)
    g.add_node("research", node_research_agent)
    g.add_node("writer",   node_writer_agent)
    g.add_node("critic",   node_critic_agent)

    g.set_entry_point("research")
    g.add_edge("research", "writer")
    g.add_edge("writer",   "critic")
    g.add_conditional_edges(
        "critic",
        route_after_critic,
        {"end": END, "writer": "writer", "research": "research"},
    )
    return g.compile()


# ── FAISS index builder ────────────────────────────────────────────────────────
def build_index() -> None:
    global _embed_model, _index, _chunks

    all_chunks, doc_count = [], 0
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for path in sorted(pathlib.Path(DOCS_DIR).rglob("*")):
        if path.suffix == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
        elif path.suffix == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception:
                continue
        else:
            continue
        doc_count += 1
        for i in range(0, len(text), step):
            chunk = text[i : i + CHUNK_SIZE]
            if chunk.strip():
                all_chunks.append(f"[Source: {path.name}]\n{chunk}")

    if not all_chunks:
        raise RuntimeError(f"No .txt or .pdf files found in '{DOCS_DIR}'.")

    _chunks = all_chunks
    print(f"Indexed {len(_chunks)} chunks from {doc_count} file(s)")

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
    print("Multi-agent RAG ready.")
    yield


app = FastAPI(title="Scholarship RAG (Multi-Agent)", lifespan=lifespan)


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
        "question":           req.question,
        "rewritten_question": "",
        "context":            [],
        "answer":             "",
        "critique":           "",
        "passed":             False,
        "next_action":        "",
        "writer_count":       0,
        "research_count":     0,
    })
    return AskResponse(answer=result.get("answer") or "No answer generated.")


# ── CLI mode ───────────────────────────────────────────────────────────────────
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
            "question":           question,
            "rewritten_question": "",
            "context":            [],
            "answer":             "",
            "critique":           "",
            "passed":             False,
            "next_action":        "",
            "writer_count":       0,
            "research_count":     0,
        })
        print(f"\nAnswer:\n{result.get('answer', 'No answer generated.')}\n")
