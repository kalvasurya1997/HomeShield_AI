from datetime import date

def apply_waiting_period(decision: dict, effective_date: str) -> dict:
    out = dict(decision)
    try:
        year = int(str(effective_date)[:4])
        eff = date(year, 1, 1)
        if (date.today() - eff).days < 30:
            out["decision"] = "denied"
            out.setdefault("reasons", []).append("Waiting period (<30 days from effective date).")
    except Exception:
        pass
    return out
