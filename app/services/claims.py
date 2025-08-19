from .rag import retrieve_chunks, format_citations, answer_with_context

def evaluate_claim(issue: str, plan: str, state: str, year: int) -> dict:
    docs = retrieve_chunks(issue, plan, state, year, k=8)
    if not docs:
        return {"covered": False, "reason": "No relevant policy clauses found.", "citations": []}
    # Simple heuristic: look for denial keywords vs coverage keywords
    joined = " ".join(d.page_content.lower() for d in docs)
    covered_kw = any(k in joined for k in ["covered", "we cover", "included"])
    excluded_kw = any(k in joined for k in ["not covered", "excluded", "exclusion"])
    if excluded_kw and not covered_kw:
        covered = False
        reason = "Policy clauses indicate exclusions."
    else:
        covered = True
        reason = answer_with_context(f"Is this issue covered? {issue}", docs)
    return {"covered": covered, "reason": reason, "citations": format_citations(docs)}
