import os, re
import pandas as pd

YEAR_RE = re.compile(r"(19|20)\d{2}")

def _df() -> pd.DataFrame:
    csv = os.environ["CUSTOMERS_CSV"]
    # small robustness: keep strings, handle BOM, don't turn blanks into NaN
    return pd.read_csv(csv, dtype=str, keep_default_na=False, encoding="utf-8-sig")

def get_customer(customer_id: str) -> dict:
    df = _df()

    # derive effective_year if missing, but don't crash on mixed date formats
    if "effective_year" not in df.columns:
        df["effective_year"] = pd.to_datetime(
            df.get("effective_date", ""), errors="coerce"
        ).dt.year

    # match case-insensitively
    row = df[df["customer_id"].astype(str).str.upper() == str(customer_id).upper()]
    if row.empty:
        raise KeyError("Customer not found")
    r = row.iloc[0].to_dict()

    # fallback: try to infer year from policy_doc like LHG_Silver_TX_2025.txt
    y = r.get("effective_year")
    if (y is None or str(y).strip() == "") and r.get("policy_doc"):
        m = YEAR_RE.search(str(r["policy_doc"]))
        if m:
            y = int(m.group())

    return {
        "id":         str(r.get("customer_id", "")).upper(),
        "first_name": str(r.get("first_name", "")),
        "last_name":  str(r.get("last_name", "")),
        "email":      str(r.get("email", "")),
        "plan":       str(r.get("plan", "")).title(),
        "state":      str(r.get("state", "")).upper(),
        "effective_year": int(float(y)) if str(y).strip() else 2025,   # same default as yours
        "policy_file":   os.path.basename(str(r.get("policy_doc", ""))),  # <- needed for RAG filter
    }
