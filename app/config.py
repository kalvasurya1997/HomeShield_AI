import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

def env(name: str) -> str:
    v = os.getenv(name)
    if not v: raise RuntimeError(f"Missing env var: {name}")
    return v
