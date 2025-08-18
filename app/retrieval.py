# app/retrieval.py

from pathlib import Path
from typing import List
from langchain.schema import Document

from .vectorstore import get_vectorstore


def retrieve_mmr(
    question: str,
    plan: str,
    state: str,
    year: int,
    k: int = 8,
    fetch_k: int = 24,
    lambda_mult: float = 0.5,
) -> List[Document]:
    """
    VectorStore MMR retrieval with strict metadata filters.
    """
    vs = get_vectorstore()
    return vs.max_marginal_relevance_search(
        question,
        k=k,
        fetch_k=fetch_k,
        lambda_mult=lambda_mult,
        filter={"plan": plan, "state": state, "effective_year": year},
    )


def format_context(docs: List[Document]) -> str:
    """
    Render retrieved docs into a single context string with short source names
    and integer page numbers. Safe if pages are floats/strings or missing.
    """
    parts: List[str] = []
    for i, d in enumerate(docs):
        # filename only (strip full path if present)
        src = Path(str(d.metadata.get("source", ""))).name or "unknown.txt"

        # normalize page to int
        page_raw = d.metadata.get("page", 0)
        try:
            page = int(float(page_raw))
        except Exception:
            page = 0

        parts.append(f"[{i}] {src} p.{page}\n{d.page_content}")
    return "\n\n---\n\n".join(parts)
