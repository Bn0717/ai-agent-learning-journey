"""
*** this is the version using langchain + vertexai (claude-sonnet-4-6) but Claude on Vertex AI is NOT a first-class LangChain wrapper, better to use gemini***

*** but now i will use 

run 
.\rag-env\Scripts\Activate.ps1

then 
$env:GOOGLE_CLOUD_PROJECT = "brain-433706"
$env:GOOGLE_CLOUD_LOCATION = "asia-southeast1"
$env:VERTEX_MODEL = "claude-sonnet-4-6"
python rag.py


Scholarship RAG (LangChain) — FastAPI web service for Cloud Run.
Uses LangChain + Vertex AI (Claude Sonnet 4.6) for answer generation.

── Startup (once) ──────────────────────────────────────────────────────────────
  docs/ (.txt / .pdf)
    → DirectoryLoader          read raw text from each file
    → RecursiveCharacterTextSplitter   split into 500-char overlapping chunks
    → HuggingFaceEmbeddings    embed each chunk → float32 vectors (all-MiniLM-L6-v2)
    → FAISS.from_documents()   store vectors in FAISS index

── Per request (POST /ask) ─────────────────────────────────────────────────────
  user question
    → retriever.invoke()       cosine search → top-5 most similar chunks
    → ChatPromptTemplate       format context + question into a prompt
    → RunnableLambda           call AnthropicVertex (Claude Sonnet 4.6)
    → return answer (JSON)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from anthropic import AnthropicVertex


# ── Configuration ──────────────────────────────────────────────────────────────
DOCS_DIR      = "docs"
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50
TOP_K         = 5
EMBED_MODEL   = "all-MiniLM-L6-v2"

LLM_MODEL   = os.environ.get("VERTEX_MODEL", "claude-sonnet-4-6")
GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_REGION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")

_chain = None


# ── Chain builder (runs once at startup) ───────────────────────────────────────
def build_chain():
    # Load .txt and .pdf files from docs/
    txt_docs = DirectoryLoader(DOCS_DIR, glob="**/*.txt", loader_cls=TextLoader).load()
    pdf_docs = DirectoryLoader(DOCS_DIR, glob="**/*.pdf", loader_cls=PyPDFLoader).load()
    all_docs = txt_docs + pdf_docs

    if not all_docs:
        raise RuntimeError(f"No .txt or .pdf files found in '{DOCS_DIR}'.")
    print(f"Loaded {len(all_docs)} document(s)")

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(all_docs)
    print(f"Split into {len(chunks)} chunks")

    # Embed and store in FAISS
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})

    llm = ChatAnthropicVertex(
        model_name=LLM_MODEL,
        project=GCP_PROJECT,
        location=GCP_REGION,
        max_tokens=1024,
    )

    prompt = ChatPromptTemplate.from_template(
        "Answer using only the scholarship information below.\n"
        "If the answer is not found, say 'not found in documents'.\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}"
    )

    def format_docs(docs):
        return "\n\n---\n\n".join(
            f"[Source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
            for doc in docs
        )

    # LCEL chain: retrieve → format → prompt → LLM → parse
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _chain
    _chain = build_chain()
    print("RAG chain ready.")
    yield


app = FastAPI(title="Scholarship RAG (LangChain)", lifespan=lifespan)


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
    answer = _chain.invoke(req.question)
    return AskResponse(answer=answer)

# ── CLI mode: python rag.py ────────────────────────────────────────────────────
if __name__ == "__main__":
    chain = build_chain()
    print("Ready. Type your question or 'quit' to exit.\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() in ("quit", "exit", "q"):
            break
        answer = chain.invoke(question)
        print(f"\nAnswer:\n{answer}\n")
















"""


*** this is with the AnthropicVertex SDK, so it's manually calling the Vertex API in a RunnableLambda instead of using a first-class LangChain Vertex wrapper (which doesn't exist for Claude yet) — better to use gemini which has a native wrapper***


run 
.\rag-env\Scripts\Activate.ps1

then 
$env:GOOGLE_CLOUD_PROJECT = "brain-433706"
$env:GOOGLE_CLOUD_LOCATION = "asia-southeast1"
$env:VERTEX_MODEL = "claude-sonnet-4-6"
python rag.py


Scholarship RAG (LangChain) — FastAPI web service for Cloud Run.
Uses LangChain + Vertex AI (Claude Sonnet 4.6) for answer generation.

── Startup (once) ──────────────────────────────────────────────────────────────
  docs/ (.txt / .pdf)
    → DirectoryLoader          read raw text from each file
    → RecursiveCharacterTextSplitter   split into 500-char overlapping chunks
    → HuggingFaceEmbeddings    embed each chunk → float32 vectors (all-MiniLM-L6-v2)
    → FAISS.from_documents()   store vectors in FAISS index

── Per request (POST /ask) ─────────────────────────────────────────────────────
  user question
    → retriever.invoke()       cosine search → top-5 most similar chunks
    → ChatPromptTemplate       format context + question into a prompt
    → RunnableLambda           call AnthropicVertex (Claude Sonnet 4.6)
    → return answer (JSON)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from anthropic import AnthropicVertex


# ── Configuration ──────────────────────────────────────────────────────────────
DOCS_DIR      = "docs"
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50
TOP_K         = 5
EMBED_MODEL   = "all-MiniLM-L6-v2"

LLM_MODEL   = os.environ.get("VERTEX_MODEL", "claude-sonnet-4-6")
GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_REGION  = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")

_chain = None


# ── Chain builder (runs once at startup) ───────────────────────────────────────
def build_chain():
    # Load .txt and .pdf files from docs/
    txt_docs = DirectoryLoader(DOCS_DIR, glob="**/*.txt", loader_cls=TextLoader).load()
    pdf_docs = DirectoryLoader(DOCS_DIR, glob="**/*.pdf", loader_cls=PyPDFLoader).load()
    all_docs = txt_docs + pdf_docs

    if not all_docs:
        raise RuntimeError(f"No .txt or .pdf files found in '{DOCS_DIR}'.")
    print(f"Loaded {len(all_docs)} document(s)")

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(all_docs)
    print(f"Split into {len(chunks)} chunks")

    # Embed and store in FAISS
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})

    def format_docs(docs):
        return "\n\n---\n\n".join(
            f"[Source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
            for doc in docs
        )

    def call_claude(inputs: dict) -> str:
        client = AnthropicVertex(region=GCP_REGION, project_id=GCP_PROJECT)
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    "Answer using only the scholarship information below.\n"
                    "If the answer is not found, say 'not found in documents'.\n\n"
                    f"Context:\n{inputs['context']}\n\n"
                    f"Question: {inputs['question']}"
                ),
            }],
        )
        return response.content[0].text

    # LCEL chain: retrieve → format context → call Claude → return string
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | RunnableLambda(call_claude)
    )


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _chain
    _chain = build_chain()
    print("RAG chain ready.")
    yield


app = FastAPI(title="Scholarship RAG (LangChain)", lifespan=lifespan)


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
    answer = _chain.invoke(req.question)
    return AskResponse(answer=answer)

# ── CLI mode: python rag.py ────────────────────────────────────────────────────
if __name__ == "__main__":
    chain = build_chain()
    print("Ready. Type your question or 'quit' to exit.\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() in ("quit", "exit", "q"):
            break
        answer = chain.invoke(question)
        print(f"\nAnswer:\n{answer}\n")