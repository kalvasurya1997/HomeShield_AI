import os, time
from pathlib import Path
from typing import List
from tqdm import tqdm

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader

from ..config import settings
from ..vectorstore import embeddings_client, pinecone_index


def _parse_meta_from_filename(path: str):
    """
    Expect names like: LHG_<Plan>_<STATE>_<YEAR>.txt
    Adds 'policy_file' so RAG can filter to a single document.
    """
    p = Path(path)
    stem = p.stem
    parts = stem.split("_")
    meta = {"policy_file": p.name}  # <-- critical, store the filename as a key

    if len(parts) >= 4 and parts[0] == "LHG":
        _, plan, state, year = parts[:4]
        # normalize for consistency with your CSV and queries
        meta["plan"] = str(plan).title()
        meta["state"] = str(state).upper()
        try:
            meta["effective_year"] = int(year)
        except Exception:
            pass
    return meta


def load_and_chunk(policy_dir: str):
    raw = []
    for p in Path(policy_dir).glob("*.txt"):
        raw.extend(TextLoader(str(p), encoding="utf-8").load())

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=120,
        add_start_index=True
    )
    docs = splitter.split_documents(raw)

    for i, d in enumerate(docs):
        src = d.metadata.get("source", "")
        # add/normalize metadata
        meta = _parse_meta_from_filename(src or "")
        d.metadata.update(meta)

        # ensure friendly, consistent fields
        src_name = Path(src).name if src else meta.get("policy_file", "unknown.txt")
        d.metadata.setdefault("source", src_name)
        d.metadata.setdefault("policy_file", src_name)  # ensure it's always present
        d.metadata.setdefault("page", (i // 5) + 1)
        d.metadata.setdefault("section", "policy")
        d.metadata.setdefault("chunk_id", f"{src_name}-{i:04d}")

    return docs


def upsert_documents(docs):
    emb = embeddings_client()
    index = pinecone_index()
    ns = settings.PINECONE_NAMESPACE

    BATCH = 64
    for i in tqdm(range(0, len(docs), BATCH), desc="Upserting"):
        batch = docs[i:i + BATCH]
        vecs = emb.embed_documents([d.page_content for d in batch])

        vectors = []
        for j, d in enumerate(batch):
            vectors.append({
                "id": f"hs-{i + j:08d}",
                "values": vecs[j],
                "metadata": {
                    **d.metadata,
                    "text": d.page_content,   # keep raw text in metadata
                },
            })

        index.upsert(vectors=vectors, namespace=ns)
        time.sleep(0.5)


def ingest_all():
    docs = load_and_chunk(settings.POLICY_DIR)
    upsert_documents(docs)
