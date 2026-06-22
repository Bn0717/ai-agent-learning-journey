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
  Research Agent   rewrites question → ONE tool_executor("research") call
      ↓
  Writer Agent     generates answer from context (+ critique on retry)
      ↓
  Critic Agent     evaluates grounding; returns {passed, critique} only
      ├─ passed=true         → END  (stores to long-term memory)
      ├─ writer_count < 2    → Writer retry
      ├─ research_count < 2  → Research retry → Writer → Critic
      └─ else                → END
  END

── Tool layer (Phase 7) ─────────────────────────────────────────────────────────
  retrieve_tool(query)    FAISS top-k cosine-similarity search
  search_tool(query)      stub delegating to retrieve_tool
  memory_tool(query)      FAISS memory index semantic lookup
  research_tool(query)    combined: retrieve + memory (single agent entry point)
  tool_executor(name, q)  single entry point — agents call only this

── Memory layer (Phase 8) ───────────────────────────────────────────────────────
  short_term_memory   context + critique in LangGraph state (per request)
  long_term_memory    FAISS IndexFlatIP memory index + parallel answer list
                      O(n) exact cosine search — consistent with main index
                      supports rephrased/paraphrased questions (threshold=0.75)
                      grows dynamically: one entry added per PASS verdict
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
MEMORY_THRESHOLD = 0.75

LLM_MODEL   = os.environ.get("VERTEX_MODEL", "claude-sonnet-4-6")
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GCP_REGION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")

if not GCP_PROJECT:
    raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set.")

_embed_model: Optional[SentenceTransformer] = None
_index:       Optional[faiss.IndexFlatIP]   = None   # main doc index
_chunks:      List[str]                     = []
_graph                                      = None

# ── Memory Layer (Phase 8) — FAISS-based ──────────────────────────────────────
# Uses a dedicated FAISS index for semantic retrieval — same infrastructure as
# the doc index. _mem_answers is a parallel array: index i → stored answer i.
_mem_index:   Optional[faiss.IndexFlatIP] = None
_mem_answers: List[str]                   = []


def memory_store(question: str, answer: str) -> None:
    global _mem_index
    vec = _embed_model.encode([question.strip()], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(vec)
    if _mem_index is None:
        _mem_index = faiss.IndexFlatIP(vec.shape[1])
    _mem_index.add(vec)
    _mem_answers.append(answer)
    print(f"[memory] stored: {question.strip()[:60]}")


def memory_retrieve(question: str) -> Optional[str]:
    """FAISS nearest-neighbour search over stored question embeddings."""
    if _mem_index is None or _mem_index.ntotal == 0:
        return None
    q_vec = _embed_model.encode([question.strip()], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_vec)
    scores, indices = _mem_index.search(q_vec, 1)
    score = float(scores[0][0])
    if score >= MEMORY_THRESHOLD:
        print(f"[memory] hit (score={score:.3f}): {question.strip()[:60]}")
        return _mem_answers[int(indices[0][0])]
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
    """FAISS cosine-similarity search over doc index."""
    q_vec = _embed_model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_vec)
    _, indices = _index.search(q_vec, TOP_K)
    results = [_chunks[i] for i in indices[0] if i < len(_chunks)]
    print(f"[retrieve_tool] {len(results)} chunks for: {query[:60]}")
    return results


def search_tool(query: str) -> List[str]:
    """Stub search tool — delegates to retrieve_tool."""
    return retrieve_tool(query)


def memory_tool(query: str) -> List[str]:
    """FAISS memory index lookup — returns past answer wrapped as context chunk."""
    result = memory_retrieve(query)
    return [f"[Long-term Memory]\n{result}"] if result else []


def research_tool(query: str) -> List[str]:
    """Combined entry point: FAISS doc retrieval + memory lookup in one call."""
    return retrieve_tool(query) + memory_tool(query)


TOOLS: Dict[str, Callable[[str], List[str]]] = {
    "retrieve": retrieve_tool,
    "search":   search_tool,
    "memory":   memory_tool,
    "research": research_tool,
}


def tool_executor(tool_name: str, query: str) -> List[str]:
    """Single entry point for all tool calls. Agents must use only this."""
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool '{tool_name}'. Available: {list(TOOLS)}")
    return TOOLS[tool_name](query)


# ── Graph State ────────────────────────────────────────────────────────────────
# next_action removed — routing is derived in route_after_critic(), not stored.
class MultiAgentState(TypedDict):
    question:           str
    rewritten_question: str       # rewritten query used for retrieval
    context:            List[str] # short_term_memory: retrieved chunks
    answer:             str
    critique:           str       # short_term_memory: critic feedback for Writer retry
    passed:             bool      # explicit Critic verdict (not inferred from strings)
    writer_count:       int       # Writer runs at most twice (max 1 retry)
    research_count:     int       # Research can be re-triggered at most once


# ── Agent Nodes ────────────────────────────────────────────────────────────────
def node_research_agent(state: MultiAgentState) -> dict:
    """Research Agent: rewrites question, makes ONE tool call — no generation, no routing."""
    question = state["question"]
    critique = state.get("critique", "")

    rewrite_prompt = (
        "Rewrite this question to be more specific for searching a scholarship knowledge base.\n"
        "Return only the rewritten question, nothing else.\n\n"
        f"Question: {question}"
    )
    if critique:
        rewrite_prompt += (
            f"\n\nPrevious search was insufficient. Critique: {critique}\n"
            "Adjust the query to find more relevant information."
        )

    rewritten = llm(rewrite_prompt).strip() or question
    print(f"[research] rewritten: {rewritten[:80]}")

    # Single tool call — research_tool combines retrieval + memory internally
    context = tool_executor("research", rewritten)

    return {
        "context":            context,
        "rewritten_question": rewritten,
        "research_count":     state["research_count"] + 1,
    }


def node_writer_agent(state: MultiAgentState) -> dict:
    """Writer Agent: generates answer from context only — no tools, no routing."""
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
    """Critic Agent: evaluates answer, returns {passed, critique} only — routing is Python's job."""
    context_text = "\n\n---\n\n".join(state["context"])
    result = llm(
        "Evaluate the answer strictly against the context below.\n"
        "Check: (1) Is it fully grounded in the context? (2) Is it correct and complete?\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {state['question']}\n"
        f"Answer: {state['answer']}\n\n"
        "Reply with ONLY valid JSON (no extra text):\n"
        '{"passed": true/false, "critique": "one sentence explaining the verdict"}'
    )

    passed, critique = False, result.strip()
    try:
        match = re.search(r'\{.*?\}', result, re.DOTALL)
        if match:
            data     = json.loads(match.group())
            passed   = bool(data.get("passed", False))
            critique = data.get("critique", result.strip())
    except (json.JSONDecodeError, AttributeError):
        passed = result.strip().upper().startswith("PASS")

    if passed:
        memory_store(state["question"], state["answer"])
        print("[critic] PASS — stored to long-term memory")
    else:
        print(f"[critic] FAIL — {critique[:80]}")

    return {"passed": passed, "critique": critique}


# ── Routing (single source of truth) ──────────────────────────────────────────
def route_after_critic(state: MultiAgentState) -> str:
    if state["passed"]:
        return "end"
    if state["writer_count"] < 2:
        return "writer"       # improve the answer first
    if state["research_count"] < 2:
        return "research"     # writer exhausted — retry with fresh context
    return "end"              # both retries exhausted


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
            "writer_count":       0,
            "research_count":     0,
        })
        print(f"\nAnswer:\n{result.get('answer', 'No answer generated.')}\n")
