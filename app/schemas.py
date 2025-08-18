from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class QARequest(BaseModel):
    question: str
    plan: Optional[str] = None
    state: Optional[str] = None
    year: Optional[int] = None
    customer_id: Optional[str] = None

class Citation(BaseModel):
    source: str
    page: int
    quote: str

class QAResponse(BaseModel):
    answer: str
    citations: List[Citation] = []

class ClaimRequest(BaseModel):
    customer_id: str
    message: str

class ClaimResponse(BaseModel):
    claim_id: str
    extraction: Dict[str, Any]
    decision: str
    reasons: List[str]
    citations: List[Citation] = []
