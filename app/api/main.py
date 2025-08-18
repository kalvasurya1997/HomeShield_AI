from fastapi import FastAPI
from ..schemas import QARequest, QAResponse, ClaimRequest, ClaimResponse
from ..service import ask_coverage, submit_claim
from ..ingestion import load_and_chunk, upsert_chunks, clear_namespace_if_exists
from ..config import settings

app = FastAPI(title="HomeShield AI")

@app.get("/health")
def health():
    return {"status": "ok", "namespace": settings.NAMESPACE}

@app.post("/qa", response_model=QAResponse)
def qa(req: QARequest):
    res = ask_coverage(
        question=req.question,
        plan=req.plan, state=req.state, year=req.year,
        customer_id=req.customer_id
    )
    return res

@app.post("/claim", response_model=ClaimResponse)
def claim(req: ClaimRequest):
    return submit_claim(req.customer_id, req.message)

@app.post("/reindex")
def reindex():
    # (re)build vectors from POLICY_DIR
    cleared = clear_namespace_if_exists()
    chunks = load_and_chunk(settings.POLICY_DIR)
    upsert_chunks(chunks)
    return {"cleared": cleared, "chunks": len(chunks), "namespace": settings.NAMESPACE}
