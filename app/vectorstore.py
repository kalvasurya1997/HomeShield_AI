# app/vectorstore.py
# ─────────────────────────────────────────────────────────────────────────────
# Pinecone index + LangChain VectorStore helpers
# - Uses new pinecone SDK (pip install pinecone>=5)
# - Assumes ingestion stored raw chunk text in metadata under key "text"
# - Namespace comes from .env (default: "policies")
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # ensure .env is loaded before reading settings

from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore

from .embeddings import get_embeddings
from .config import settings


def get_index():
    """
    Return a live Pinecone index handle using env/config.
    """
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    return pc.Index(settings.PINECONE_INDEX)


def get_vectorstore(text_key: str | None = None) -> PineconeVectorStore:
    """
    Return a LangChain VectorStore bound to the Pinecone index/namespace.

    Parameters
    ----------
    text_key : str | None
        If you stored the raw chunk text under a non-default key in metadata,
        set this to that key. Our ingestion stores under "text", which is what
        langchain_pinecone expects by default, so you can leave this None.
    """
    emb = get_embeddings()
    kwargs = {}
    if text_key:
        kwargs["text_key"] = text_key  # only needed if you changed the metadata key

    return PineconeVectorStore(
        index_name=settings.PINECONE_INDEX,
        embedding=emb,
        namespace=settings.NAMESPACE,
        **kwargs
    )
