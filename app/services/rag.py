from ..vectorstore import vectorstore, chat_client

SYSTEM = (
  "You are HomeShield AI. Answer strictly from the provided policy chunks. "
  "Cite specific clauses. If not covered, say 'Not covered' and why."
)

def retrieve_chunks(query: str, plan: str, state: str, year: int, k=8):
    vs = vectorstore()
    meta_filter = {
        "$and": [
            {"plan": {"$eq": plan}},
            {"state": {"$eq": state}},
            {"effective_year": {"$in": [int(year), float(year)]}},
        ]
    }
    return vs.max_marginal_relevance_search(query, k=k, fetch_k=24, lambda_mult=0.5, filter=meta_filter)

def format_citations(docs):
    return [{
        "source": d.metadata.get("source","unknown.txt"),
        "page": int(d.metadata.get("page",0)),
        "text": d.page_content
    } for d in docs]

def answer_with_context(question: str, docs):
    llm = chat_client(temperature=0)
    context = "\n\n---\n\n".join(
        f"{d.metadata.get('source','')}, p.{int(d.metadata.get('page',0))}\n{d.page_content}"
        for d in docs
    )
    msg = [
        {"role":"system","content":SYSTEM},
        {"role":"user","content":f"Question:\n{question}\n\nContext:\n{context}"}
    ]
    return llm.invoke(msg).content.strip()
