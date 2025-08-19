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
    """
    stem = Path(path).stem
    parts = stem.split("_")
    meta = {}
    if len(parts) >= 4 and parts[0] == "LHG":
        _, plan, state, year = parts[:4]
        meta["plan"] = plan
        meta["state"] = state
        try:
            meta["effective_year"] = int(year)
        except:
            pass
    return meta

def load_and_chunk(policy_dir: str):
    raw = []
    for p in Path(policy_dir).glob("*.txt"):
        raw.extend(TextLoader(str(p), encoding="utf-8").load())
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120, add_start_index=True)
    docs = splitter.split_documents(raw)
    for i, d in enumerate(docs):
        src = d.metadata.get("source", "")
        meta = _parse_meta_from_filename(src)
        d.metadata.update(meta)
        d.metadata.setdefault("source", Path(src).name or "unknown.txt")
        d.metadata.setdefault("page", (i // 5) + 1)
        d.metadata.setdefault("section", "policy")
        d.metadata.setdefault("chunk_id", f"{d.metadata['source']}-{i:04d}")
    return docs

def upsert_documents(docs):
    emb = embeddings_client()
    index = pinecone_index()
    ns = settings.PINECONE_NAMESPACE

    BATCH = 64
    for i in tqdm(range(0, len(docs), BATCH), desc="Upserting"):
        batch = docs[i:i+BATCH]
        vectors = []
        vecs = emb.embed_documents([d.page_content for d in batch])
        for j, d in enumerate(batch):
            vectors.append({
                "id": f"hs-{i+j:08d}",
                "values": vecs[j],
                "metadata": {**d.metadata, "text": d.page_content}
            })
        index.upsert(vectors=vectors, namespace=ns)
        time.sleep(0.5)

def ingest_all():
    docs = load_and_chunk(settings.POLICY_DIR)
    upsert_documents(docs)
