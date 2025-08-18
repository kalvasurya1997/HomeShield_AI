# app/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..schemas import QARequest, QAResponse, ClaimRequest, ClaimResponse
from ..service import ask_coverage, submit_claim
from ..ingestion import load_and_chunk, upsert_chunks, clear_namespace_if_exists
from ..config import settings

app = FastAPI(title="HomeShield AI")

# Allow local file / localhost testing (relax for POC; tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # e.g., ["http://localhost:3000", "http://127.0.0.1:5500"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "name": "HomeShield AI",
        "health": "/health",
        "qa": "/qa",
        "claim": "/claim",
        "reindex": "/reindex",
        "namespace": settings.NAMESPACE,
    }

@app.get("/health")
def health():
    return {"status": "ok", "namespace": settings.NAMESPACE}

@app.post("/qa", response_model=QAResponse)
def qa(req: QARequest):
    res = ask_coverage(
        question=req.question,
        plan=req.plan, state=req.state, year=req.year,
        customer_id=req.customer_id,
    )
    return res

@app.post("/claim", response_model=ClaimResponse)
def claim(req: ClaimRequest):
    return submit_claim(req.customer_id, req.message)

@app.post("/reindex")
def reindex():
    cleared = clear_namespace_if_exists()
    chunks = load_and_chunk(settings.POLICY_DIR)
    upsert_chunks(chunks)
    return {"cleared": cleared, "chunks": len(chunks), "namespace": settings.NAMESPACE}
