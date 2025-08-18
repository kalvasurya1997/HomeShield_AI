import pandas as pd
from uuid import uuid4
from .chains import coverage_query, extract_fields, coverage_decision
from .rules import apply_waiting_period
from .config import settings

def ask_coverage(question: str, plan=None, state=None, year=None, customer_id=None) -> dict:
    if customer_id:
        df = pd.read_csv(settings.CUSTOMERS_CSV)
        row = df.loc[df["customer_id"] == customer_id]
        if row.empty:
            return {"error": f"customer_id {customer_id} not found"}
        r = row.iloc[0]
        plan, state, year = r["plan"], r["state"], int(str(r["effective_date"])[:4])
    if not (plan and state and year):
        return {"error": "Provide plan/state/year or customer_id."}
    return coverage_query(question, plan, state, year)

def submit_claim(customer_id: str, message: str) -> dict:
    df = pd.read_csv(settings.CUSTOMERS_CSV)
    row = df.loc[df["customer_id"] == customer_id]
    if row.empty:
        return {"error": f"customer_id {customer_id} not found"}
    r = row.iloc[0]
    plan, state, eff = r["plan"], r["state"], r["effective_date"]
    year = int(str(eff)[:4])

    fx = extract_fields(message)
    dec = coverage_decision(fx.get("appliance"), fx.get("issue"), fx.get("failure_date"),
                            plan, state, year)
    final = apply_waiting_period(dec, eff)
    return {
        "claim_id": f"CLM-{uuid4().hex[:8]}",
        "extraction": fx,
        "decision": final.get("decision","ambiguous"),
        "reasons": final.get("reasons", []),
        "citations": final.get("citations", []),
    }
