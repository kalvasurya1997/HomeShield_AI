# app/services/claims.py
from __future__ import annotations
import json
from typing import Dict, Any, List, Optional

from .rag import retrieve_chunks, format_citations
from ..vectorstore import chat_client

SYSTEM_ADJUDICATE = (
    "You are an insurance adjudicator for a HOME WARRANTY policy. "
    "Decide coverage STRICTLY from the provided policy context.\n"
    "Rules:\n"
    "- If a clause explicitly covers the item/condition, mark covered=yes.\n"
    "- If ANY exclusion applies, covered=no.\n"
    "- If the context is insufficient/ambiguous, covered=uncertain.\n"
    "- Keep the reason one sentence, refer to the clause by paraphrase.\n"
    "Return ONLY minified JSON: "
    "{\"covered\":\"yes|no|uncertain\",\"reason\":\"...\",\"resolved_question\":\"...\"}"
)

def _structured_llm_verdict(issue: str, docs) -> Dict[str, Any]:
    llm = chat_client(temperature=0)
    context = "\n\n---\n\n".join(
        f"{d.metadata.get('source','')}, p.{int(d.metadata.get('page',0))}\n{d.page_content}"
        for d in (docs or [])
    )
    user = f"Issue:\n{issue}\n\nPolicy context:\n{context}"
    raw = llm.invoke([
        {"role": "system", "content": SYSTEM_ADJUDICATE},
        {"role": "user", "content": user}
    ]).content.strip()

    raw = raw.strip().replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        data = {"covered": "uncertain", "reason": "Unable to determine from context.", "resolved_question": issue}

    covered_str = str(data.get("covered", "uncertain")).lower().strip()
    if covered_str in ("yes", "true"):
        covered = True
    elif covered_str in ("no", "false"):
        covered = False
    else:
        covered = False  # treat uncertain as not covered for UI badge, but expose raw
    return {
        "covered": covered,
        "covered_raw": covered_str,
        "reason": (data.get("reason") or "Unable to determine from context.").strip(),
        "resolved_question": (data.get("resolved_question") or issue).strip(),
    }

def evaluate_claim(issue: str, plan: str, state: str, year: int,
                   last_issue: Optional[str] = None,
                   history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Conversation-aware strict adjudication:
    - Retrieve policy chunks with metadata filters
    - Ask LLM for a JSON verdict (yes/no/uncertain)
    - Return boolean + reason + citations
    """
    docs = retrieve_chunks(issue, plan, state, int(year), k=8)
    if not docs:
        return {
            "covered": False,
            "covered_raw": "uncertain",
            "reason": "No relevant policy clauses found.",
            "resolved_question": issue,
            "citations": []
        }

    verdict = _structured_llm_verdict(issue, docs)
    verdict["citations"] = format_citations(docs)
    return verdict
