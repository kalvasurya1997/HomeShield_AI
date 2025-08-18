import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.claims import submit_claim

if __name__ == "__main__":
    res = submit_claim("C00001", "My AC stopped cooling yesterday, thermostat shows E1.")
    print(res)
