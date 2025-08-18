from pinecone import Pinecone
import os

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(os.environ["PINECONE_INDEX"])
stats = index.describe_index_stats()

# Show namespace counts if available
ns_counts = getattr(stats, "namespaces", {}) or {}
print("Namespaces:", ns_counts.keys())
print("Vector count (if exposed):", ns_counts.get("policies", {}).get("vector_count", "n/a"))
