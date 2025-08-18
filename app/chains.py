import json, re
from langchain.schema.output_parser import StrOutputParser
from .embeddings import get_llm
from .retrieval import retrieve_mmr, format_context
from .prompts import qa_prompt, extract_prompt, decision_prompt

def _json(t: str) -> dict:
    try: return json.loads(t)
    except Exception:
        return json.loads(re.sub(r"^```json|```$", "", t.strip(), flags=re.MULTILINE))

def coverage_query(question: str, plan: str, state: str, year: int) -> dict:
    llm = get_llm()
    docs = retrieve_mmr(question, plan, state, year, k=8, fetch_k=24)
    if not docs:
        return {"answer": "No relevant policy text found.", "citations": []}
    ctx = format_context(docs)
    out = (qa_prompt | llm | StrOutputParser()).invoke({"question": question, "context": ctx})
    return _json(out)

def extract_fields(message: str) -> dict:
    llm = get_llm()
    out = (extract_prompt | llm | StrOutputParser()).invoke({"message": message})
    return _json(out)

def coverage_decision(appliance: str, issue: str, failure_date: str|None,
                      plan: str, state: str, year: int) -> dict:
    llm = get_llm()
    query = " ".join([appliance or "", issue or ""]).strip() or "coverage"
    docs = retrieve_mmr(query, plan, state, year, k=8, fetch_k=24)
    ctx = format_context(docs)
    out = (decision_prompt | llm | StrOutputParser()).invoke({
        "plan": plan, "state": state, "year": year,
        "appliance": appliance, "issue": issue, "failure_date": failure_date or "null",
        "context": ctx
    })
    return _json(out)
