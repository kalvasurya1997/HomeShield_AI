# tests/test_smoke2.py
import sys
from pathlib import Path

# add project root to sys.path so "app.*" imports work when running this file directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")  # safe even if already loaded

from app.retrieval import retrieve_mmr, format_context

if __name__ == "__main__":
    hits = retrieve_mmr("HVAC compressor coverage", "Gold", "PA", 2025)
    print("hits:", len(hits))
    if hits:
        print(format_context(hits)[:1200])
