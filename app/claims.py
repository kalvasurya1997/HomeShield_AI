# app/claims.py

from __future__ import annotations

import json
import re
from uuid import uuid4
from datetime import date
from typing import Dict, Any, Optional

import pandas as pd
from langchain.schema.output_parser import StrOutputParser
from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate

from .retrieval import retrieve_mmr, format_context
from .config import settings


# --------- utils ---------
def _json(text: str) -> Dict[str, Any]:
    """Parse LLM output as JSON, tolerating ```json fences."""
    try:
        return json.loads(text)
    except Exception:
        cleaned = re.sub(r"^\s*```json\s*|\s*```\s*$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE)
        return json.loads(cleaned)


def _get_llm() -> AzureChatOpenAI:
    return AzureChatOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        temperature=0,
    )


# --------- prompts ---------
extract_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Extract claim fields from the user's text. "
     "Return a STRICT JSON object with exactly these keys: "
     "\"appliance\" (string), \"issue\" (string), \"failure_date\" (string or null). "
     "Output JSON only."),
    ("human", "{message}")
])

# Decision: NO curly braces in the schema description
decision_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a coverage validator. Use ONLY the provided context from policy documents. "
     "Return a STRICT JSON object with keys: "
     "\"decision\" (one of: covered, partial, denied, ambiguous), "
     "\"reasons\" (array of strings), "
     "\"citations\" (array of objects, each with keys: \"source\" (string), \"page\" (integer), \"quote\" (string)). "
     "Output JSON only."),
    ("human",
     "Customer plan: {plan}, {state}, {year}\n"
     "Appliance: {appliance}\nIssue: {issue}\nFailure date: {failure_date}\n\n"
     "Context:\n{context}")
])


# --------- chains ---------
def extract_fields(message: str) -> Dict[str, Any]:
    out_text = (extract_prompt | _get_llm() | StrOutputParser()).invoke({"message": message})
    return _json(out_text)


def coverage_decision(
    appliance: Optional[str],
    issue: Optional[str],
    failure_date: Optional[str],
    plan: str,
    state: str,
    year: int,
) -> Dict[str, Any]:
    query = " ".join([appliance or "", issue or ""]).strip() or "coverage"
    docs = retrieve_mmr(query, plan, state, year, k=8, fetch_k=24)
    ctx = format_context(docs)
    out_text = (decision_prompt | _get_llm() | StrOutputParser()).invoke({
        "plan": plan, "state": state, "year": year,
        "appliance": appliance or "", "issue": issue or "", "failure_date": failure_date or "null",
        "context": ctx
    })
    res = _json(out_text)
    if not isinstance(res.get("reasons"), list):   # schema guardrails
        res["reasons"] = []
    if not isinstance(res.get("citations"), list):
        res["citations"] = []
    return res


# --------- rules ---------
def apply_waiting_period(decision_json: Dict[str, Any], effective_date: str) -> Dict[str, Any]:
    out = dict(decision_json)
    try:
        y = int(str(effective_date)[:4])
        eff = date(y, 1, 1)  # synthetic policy effective date = Jan 1 (per our sample data)
        if (date.today() - eff).days < 30:
            out["decision"] = "denied"
            out.setdefault("reasons", []).append("Waiting period (<30 days from effective date).")
    except Exception:
        pass
    return out


# --------- façade used by tests & API ---------
def submit_claim(customer_id: str, message: str) -> Dict[str, Any]:
    # fetch customer plan/state/year from CSV
    df = pd.read_csv(settings.CUSTOMERS_CSV)
    row = df.loc[df["customer_id"] == customer_id]
    if row.empty:
        return {"error": f"customer_id {customer_id} not found"}
    r = row.iloc[0]
    plan, state, eff = r["plan"], r["state"], r["effective_date"]
    year = int(str(eff)[:4])

    # extract → decide → apply rules
    fx = extract_fields(message)
    dec = coverage_decision(fx.get("appliance"), fx.get("issue"), fx.get("failure_date"),
                            plan, state, year)
    final = apply_waiting_period(dec, eff)

    return {
        "claim_id": f"CLM-{uuid4().hex[:8]}",
        "extraction": fx,
        "decision": final.get("decision", "ambiguous"),
        "reasons": final.get("reasons", []),
        "citations": final.get("citations", []),
    }
