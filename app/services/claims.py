# app/services/claims.py
"""
Claim evaluation with exclusion-first logic and a structured LLM fallback.
Ensures the boolean `covered` and the natural-language `reason` are consistent.
"""

import re
import json
from .rag import retrieve_chunks, format_citations
from ..vectorstore import chat_client

# Regex patterns for quick heuristic (exclusions win)
EXCLUDED_PATTERNS = [
    r"\bnot\s+covered\b",
    r"\bno\s+coverage\b",
    r"\bdoes\s+not\s+cover\b",
    r"\bwe\s+do\s+not\s+cover\b",
    r"\bexcluded\b",
    r"\bexclusions?\b",
    r"\boutside\s+scope\b",
]
COVERED_PATTERNS = [
    r"\bis\s+covered\b",
    r"\bare\s+covered\b",
    r"\bwe\s+cover\b",
    r"\b(includes?|provides?)\s+coverage\b",
    r"\bcovers\b",
]


def _any_match(patterns, text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in patterns)


def _structured_llm_verdict(issue: str, docs):
    """
    Ask the model for a single JSON object:
      {"covered":"yes|no|uncertain","reason":"..."}
    Robustly extracts the first {...} block even if the model adds extra text.
    """
    llm = chat_client(temperature=0)

    context = "\n\n---\n\n".join(
        f"{d.metadata.get('source', '')}, p.{int(d.metadata.get('page', 0))}\n{d.page_content}"
        for d in docs
    )

    system_msg = (
        "You are an insurance adjudicator for a HOME WARRANTY policy. "
        "Decide coverage STRICTLY from the provided policy context. "
        "If ANY exclusion applies, the outcome is NOT covered. "
        "If context is insufficient, respond 'uncertain'. "
        "Output ONLY a minified JSON object with keys: "
        "{\"covered\":\"yes|no|uncertain\",\"reason\":\"<short one-sentence rationale>\"}."
    )
    user_msg = f"Issue:\n{issue}\n\nPolicy context:\n{context}"

    raw = llm.invoke([
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]).content.strip()

    # Extract the first JSON object to be resilient to extra text/wrapping
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        return False, "Unable to determine from the context with high confidence."

    try:
        data = json.loads(m.group(0))
    except Exception:
        return False, "Unable to determine from the context with high confidence."

    covered_str = str(data.get("covered", "")).lower().strip()
    if covered_str in ("yes", "true"):
        covered = True
    elif covered_str in ("no", "false"):
        covered = False
    else:
        # Treat 'uncertain' (or anything else) as not covered for safety,
        # or change to `None` if you prefer tri-state handling in the UI.
        covered = False

    reason = (data.get("reason") or "").strip()
    return covered, reason


def evaluate_claim(issue: str, plan: str, state: str, year: int) -> dict:
    """
    Evaluate a claim-like user statement against the policy corpus
    for the given (plan, state, year).
    """
    docs = retrieve_chunks(issue, plan, state, year, k=8)
    if not docs:
        return {
            "covered": False,
            "reason": "No relevant policy clauses found.",
            "citations": [],
        }

    joined = " ".join(d.page_content for d in docs)

    has_exclusion = _any_match(EXCLUDED_PATTERNS, joined)
    has_coverage = _any_match(COVERED_PATTERNS, joined)

    # Exclusions win; if both appear, it's ambiguous → defer to LLM verdict.
    if has_exclusion and not has_coverage:
        covered = False
        reason = "Policy clauses indicate an explicit exclusion for this issue."
    elif has_coverage and not has_exclusion:
        covered = True
        reason = "Policy clauses indicate this issue is covered."
    else:
        covered, reason = _structured_llm_verdict(issue, docs)

    return {
        "covered": covered,
        "reason": reason,
        "citations": format_citations(docs),
    }
