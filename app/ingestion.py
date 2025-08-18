import time
from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from .embeddings import get_embeddings
from .vectorstore import get_index
from .config import settings

def parse_meta_from_filename(path_str: str):
    stem = Path(path_str).stem  # LHG_<Plan>_<STATE>_<YEAR>.txt
    parts = stem.split("_")
    if len(parts) >= 4 and parts[0] == "LHG":
        _, plan, state, year = parts[:4]
        try: year = int(year)
        except: return {}
        return {"plan": plan, "state": state, "effective_year": year}
    return {}

def load_and_chunk(policy_dir: Path):
    raw_docs = []
    for p in policy_dir.glob("*.txt"):
        raw_docs.extend(TextLoader(str(p), encoding="utf-8").load())
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120, add_start_index=True)
    chunks = splitter.split_documents(raw_docs)
    for i, d in enumerate(chunks):
        src = d.metadata.get("source","")
        meta = parse_meta_from_filename(src)
        d.metadata.update(meta)
        d.metadata["source"] = Path(src).name or "unknown.txt"
        d.metadata["page"] = int((i // 5) + 1)
        d.metadata["section"] = "policy"
        d.metadata["chunk_id"] = f"{d.metadata['source']}-{i:04d}"
        d.metadata["text"] = d.page_content  # crucial for LangChain <-> Pinecone
    return chunks

def clear_namespace_if_exists():
    index = get_index()
    try:
        stats = index.describe_index_stats()
        namespaces = set((stats.namespaces or {}).keys()) if hasattr(stats, "namespaces") else set()
        if settings.NAMESPACE in namespaces:
            index.delete(delete_all=True, namespace=settings.NAMESPACE)
            return True
        return False
    except Exception:
        # If the client version doesn't expose namespaces, attempt delete anyway
        try:
            index.delete(delete_all=True, namespace=settings.NAMESPACE)
            return True
        except Exception:
            return False

def upsert_chunks(chunks, batch=64, base_sleep=3.0, max_retries=6):
    index = get_index()
    emb = get_embeddings()

    def embed_texts(texts): return emb.embed_documents(texts)

    def upsert_batch(batch_docs, start_id):
        texts = [d.page_content for d in batch_docs]
        vecs = embed_texts(texts)
        vectors = []
        for j, d in enumerate(batch_docs):
            vectors.append({
                "id": f"hs-{start_id + j:08d}",
                "values": vecs[j],
                "metadata": d.metadata
            })
        index.upsert(vectors=vectors, namespace=settings.NAMESPACE)

    for i in range(0, len(chunks), batch):
        b = chunks[i:i+batch]
        delay = base_sleep
        for attempt in range(1, max_retries+1):
            try:
                upsert_batch(b, start_id=i)
                time.sleep(base_sleep)
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg or "Too Many Requests" in msg or "rate" in msg.lower():
                    delay = min(delay * 1.8, 30.0)
                    time.sleep(delay)
                else:
                    raise
