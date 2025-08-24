# app/services/coverage.py
import json
from typing import Dict, Any, List
from .rag import retrieve_chunks, format_citations
from ..vectorstore import chat_client

def _coerce_list(x: Any) -> List[str]:
    if not x: return []
    if isinstance(x, str): return [x]
    if isinstance(x, (list, tuple, set)): return [str(i) for i in x if str(i).strip()]
    return [str(x)]

def _limits_to_dict(x: Any) -> Dict[str, str]:
    """
    Normalize limits so the UI can render bullets nicely.
    Accepts dict | list of 'Key: Value' | string.
    """
    out: Dict[str, str] = {}
    if not x:
        return out
    if isinstance(x, dict):
        for k, v in x.items():
            if str(v).strip():
                out[str(k)] = str(v)
        return out
    if isinstance(x, (list, tuple, set)):
        for item in x:
            s = str(item)
            if ":" in s:
                k, v = s.split(":", 1)
                out[k.strip()] = v.strip()
        return out
    # string fallback - try to split by ';' then ':'
    s = str(x)
    for piece in s.split(";"):
        if ":" in piece:
            k, v = piece.split(":", 1)
            out[k.strip()] = v.strip()
    return out

def _needs_clarification(issue: str) -> bool:
    """Heuristic: vague, non-specific issue phrasing."""
    lo = (issue or "").lower()
    vague_terms = ("not working", "got damaged", "broken", "issue", "doesn't work", "stopped working")
    return any(t in lo for t in vague_terms) and not any(
        p in lo for p in ("compressor", "evaporator", "coil", "blower", "thermostat", "breaker")
    )

def _structured_summary(issue: str, docs) -> Dict[str, Any]:
    """
    Ask the model for a neutral coverage overview (not a claim decision).
    """
    llm = chat_client(temperature=0)
    ctx = "\n\n---\n\n".join(
        f"{d.metadata.get('source','')}, p.{int(d.metadata.get('page',0))}\n{d.page_content}"
        for d in docs
    )

    sys = (
        "You explain HOME WARRANTY coverage strictly from the provided policy text. "
        "DO NOT adjudicate an individual claim. Summarize coverage intent and limits. "
        "Return STRICT minified JSON ONLY with keys:\n"
        "{\"status\":\"likely_covered|likely_excluded|depends|uncertain\","
        "\"reason\":\"<one sentence>\","
        "\"what_is_covered\":[],"
        "\"exclusions\":[],"
        "\"limits\":{},"
        "\"follow_ups\":[]}\n"
        "Prefer 'limits' as an object like "
        "{\"Per-Claim Limit\":\"$5000\",\"Service Fee\":\"$60 per service request\",\"Combined Annual Limit\":\"$30000\"}."
    )
    user = f"Item/topic: {issue}\n\nPolicy context:\n{ctx}"
    raw = llm.invoke([{"role":"system","content":sys},{"role":"user","content":user}]).content.strip()
    raw = raw.strip().removeprefix("```json").removesuffix("```").strip()

    data: Dict[str, Any]
    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    # Normalize fields
    status = str(data.get("status", "uncertain")).strip().lower()
    if status not in ("likely_covered","likely_excluded","depends","uncertain"):
        status = "uncertain"

    out = {
        "status": status,
        "reason": str(data.get("reason", "")).strip() or "Insufficient details to summarize precisely.",
        "what_is_covered": _coerce_list(data.get("what_is_covered")),
        "exclusions": _coerce_list(data.get("exclusions")),
        "limits": _limits_to_dict(data.get("limits")),
        "follow_ups": _coerce_list(data.get("follow_ups")),
    }

    # Add clarifying questions if the user’s phrasing is vague
    if _needs_clarification(issue):
        if not out["follow_ups"]:
            out["follow_ups"] = [
                "Which component failed (e.g., compressor, evaporator coil, blower motor)?",
                "Was this a mechanical/electrical failure (not installation or pre-existing)?"
            ]
        if out["status"] == "uncertain":
            out["reason"] = "I need the specific component and failure type to check your coverage."

    return out

def check_coverage(issue: str, plan: str, state: str, year: int, k: int = 8) -> Dict[str, Any]:
    """
    Neutral coverage overview. Not a yes/no claim verdict.
    """
    docs = retrieve_chunks(issue, plan, state, year, k=k)
    if not docs:
        return {
            "status": "uncertain",
            "reason": "No relevant policy clauses found.",
            "what_is_covered": [],
            "exclusions": [],
            "limits": {},
            "follow_ups": [
                "Please specify the exact system/appliance and component (if known).",
                "Any context on cause (mechanical/electrical vs. installation/pre-existing) helps."
            ],
            "citations": [],
        }

    data = _structured_summary(issue, docs)
    data["citations"] = format_citations(docs)
    return data
