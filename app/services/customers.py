import os, pandas as pd

def _df():
    csv = os.environ["CUSTOMERS_CSV"]
    return pd.read_csv(csv)

def get_customer(customer_id: str) -> dict:
    df = _df()
    row = df[df["customer_id"].astype(str) == str(customer_id)]
    if row.empty: raise KeyError("Customer not found")
    r = row.iloc[0].to_dict()
    # normalize keys you rely on
    r["first_name"] = str(r.get("first_name"))
    r["plan"] = str(r.get("plan") or r.get("policy_plan"))
    r["state"] = str(r.get("state"))
    r["effective_year"] = int(float(r.get("effective_year", 2025)))
    return r
