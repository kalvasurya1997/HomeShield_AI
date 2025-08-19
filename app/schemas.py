# app/schemas.py
from pydantic import BaseModel, field_validator

class Customer(BaseModel):
    customer_id: str
    plan: str
    state: str
    effective_year: int

    @field_validator("state")
    @classmethod
    def state_upper(cls, v: str) -> str:
        return (v or "").upper()

class CoverageQuestion(BaseModel):
    customer_id: str
    question: str

class ClaimRequest(BaseModel):
    customer_id: str
    issue_description: str
