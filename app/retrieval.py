from typing import List
from langchain.schema import Document
from .vectorstore import get_vectorstore
from .config import settings

def retrieve_mmr(question: str, plan: str, state: str, year: int,
                 k: int = 8, fetch_k: int = 24, lambda_mult: float = 0.5) -> List[Document]:
    vs = get_vectorstore()
    return vs.max_marginal_relevance_search(
        question,
        k=k, fetch_k=fetch_k, lambda_mult=lambda_mult,
        filter={"plan": plan, "state": state, "effective_year": year}
    )

def format_context(docs: List[Document]) -> str:
    parts = []
    for i, d in enumerate(docs):
        parts.append(f"[{i}] {d.metadata.get('source')} p.{d.metadata.get('page')}\n{d.page_content}")
    return "\n\n---\n\n".join(parts)
