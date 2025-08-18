# app/chains.py

from __future__ import annotations

import json
import re
from typing import Optional, Dict, Any

from langchain.schema.output_parser import StrOutputParser

from .embeddings import get_llm
from .retrieval import retrieve_mmr, format_context
from .prompts import qa_prompt, extract_prompt, decision_prompt


def _json(text: str) -> Dict[str, Any]:
    """Parse LLM output as JSON, tolerating ```json fences."""
    try:
        return json.loads(text)
    except Exception:
        cleaned = re.sub(r"^\s*```json\s*|\s*```\s*$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE)
        return json.loads(cleaned)


def _ensure_list(obj, key: str) -> None:
    """Ensure response[key] is a list (avoid schema surprises)."""
    if isinstance(obj.get(key), list):
        return
    obj[key] = []


def coverage_query(question: str, plan: str, state: str, year: int) -> Dict[str, Any]:
    llm = get_llm()
    docs = retrieve_mmr(question, plan, state, year, k=8, fetch_k=24)
    if not docs:
        return {"answer": "No relevant policy text found.", "citations": []}

    ctx = format_context(docs)
    out_text = (qa_prompt | llm | StrOutputParser()).invoke({"question": question, "context": ctx})
    res = _json(out_text)
    _ensure_list(res, "citations")
    return res


def extract_fields(message: str) -> Dict[str, Any]:
    llm = get_llm()
    out_text = (extract_prompt | llm | StrOutputParser()).invoke({"message": message})
    return _json(out_text)


def coverage_decision(
    appliance: Optional[str],
    issue: Optional[str],
    failure_date: Optional[str],
    plan: str,
    state: str,
    year: int,
) -> Dict[str, Any]:
    llm = get_llm()
    query = " ".join([appliance or "", issue or ""]).strip() or "coverage"
    docs = retrieve_mmr(query, plan, state, year, k=8, fetch_k=24)
    ctx = format_context(docs)

    out_text = (decision_prompt | llm | StrOutputParser()).invoke({
        "plan": plan,
        "state": state,
        "year": year,
        "appliance": appliance or "",
        "issue": issue or "",
        "failure_date": failure_date or "null",
        "context": ctx,
    })
    res = _json(out_text)
    _ensure_list(res, "reasons")
    _ensure_list(res, "citations")
    return res
