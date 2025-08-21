# app/services/claims.py
from __future__ import annotations
import json
from .rag import retrieve_chunks, format_citations
from ..vectorstore import chat_client

def _structured_llm_verdict(issue: str, docs):
    """Single JSON verdict from policy context only."""
    llm = chat_client(temperature=0)
    context = "\n\n---\n\n".join(
        f"{d.metadata.get('source','')}, p.{int(d.metadata.get('page',0))}\n{d.page_content}"
        for d in docs
    )
    sys = (
        "You are an adjudicator for a HOME WARRANTY policy. "
        "Decide coverage STRICTLY from the provided policy context. "
        "If any exclusion applies or the context is insufficient, the outcome is NOT covered. "
        "Output ONLY minified JSON: "
        "{\"covered\":\"yes|no|uncertain\",\"reason\":\"<short one sentence>\"}."
    )
    user = f"Issue:\n{issue}\n\nPolicy context:\n{context}"
    raw = llm.invoke([{"role": "system", "content": sys},
                      {"role": "user", "content": user}]).content.strip()

    # strip optional code fences
    raw = raw.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        data = json.loads(raw)
        covered_str = str(data.get("covered", "")).lower()
        if covered_str in ("yes", "true"):
            covered = True
        elif covered_str in ("no", "false"):
            covered = False
        else:  # 'uncertain' -> treat as not covered (conservative)
            covered = False
        reason = (data.get("reason") or "").strip()
        return covered, reason
    except Exception:
        return False, "Unable to determine from the context with high confidence."

def evaluate_claim(issue: str, plan: str, state: str, year: int) -> dict:
    docs = retrieve_chunks(issue, plan, state, year, k=8)
    if not docs:
        return {"covered": False, "reason": "No relevant policy clauses found.", "citations": []}
    covered, reason = _structured_llm_verdict(issue, docs)
    return {"covered": covered, "reason": reason, "citations": format_citations(docs)}
