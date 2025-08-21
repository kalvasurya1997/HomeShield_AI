# app/services/upgrades.py
"""
Suggest alternative plans that might cover an issue.
Searches other plans in the same state/year and reuses the same
coverage decision logic as claims.py (exclusion-first + LLM fallback).
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import os

from .rag import retrieve_chunks, format_citations
from .claims import (
    EXCLUDED_PATTERNS,
    COVERED_PATTERNS,
    _any_match,
    _structured_llm_verdict,
)

# Simple rank to show higher tiers first if present.
PLAN_RANK: Dict[str, int] = {
    "Bronze": 1,
    "Silver": 2,
    "Gold": 3,
    "Platinum": 4,
    "Diamond": 5,
    "Premium": 6,
}

def _root_dir() -> Path:
    # HomeShield_AI/
    return Path(__file__).resolve().parents[2]

def _policy_dir() -> Path:
    return _root_dir() / "policies_docs"

def discover_plans(state: str, year: int, exclude_plan: str | None = None) -> List[str]:
    """
    Try to discover available plans by scanning policy filenames:
      LHG_<Plan>_<STATE>_<YEAR>.txt
    Falls back to a common list if directory scan fails or is empty.
    """
    state = (state or "").upper().strip()
    year = int(year)
    plans = set()

    try:
        policy_dir = _policy_dir()
        pattern = f"LHG_*_{state}_{year}.txt"
        for p in policy_dir.glob(pattern):
            stem = p.stem  # LHG_Plan_ST_YYYY
            parts = stem.split("_")
            if len(parts) >= 4:
                plan = parts[1]
                if not exclude_plan or plan.lower() != exclude_plan.lower():
                    plans.add(plan)
    except Exception:
        pass

    if not plans:
        # Fallback (in case we can't read files in this environment)
        allp = ["Bronze", "Silver", "Gold", "Platinum", "Diamond"]
        if exclude_plan:
            allp = [p for p in allp if p.lower() != exclude_plan.lower()]
        return allp

    return sorted(plans, key=lambda p: PLAN_RANK.get(p, 100))

def suggest_alternative_plans(
    issue: str,
    current_plan: str,
    state: str,
    year: int,
    limit: int = 3,
) -> List[Dict]:
    """
    For the given issue, search other plans (same state/year) and return
    the best candidates that DO cover it, including citations.
    If none are found covered, return top few NOT covered so the UI can explain why.
    """
    candidates: List[Dict] = []
    for plan in discover_plans(state, year, exclude_plan=current_plan):
        docs = retrieve_chunks(issue, plan, state, year, k=8)
        if not docs:
            continue

        joined = " ".join(d.page_content for d in docs)

        has_excl = _any_match(EXCLUDED_PATTERNS, joined)
        has_cov  = _any_match(COVERED_PATTERNS, joined)

        if has_excl and not has_cov:
            covered = False
            reason = "Policy excerpts show an explicit exclusion."
        elif has_cov and not has_excl:
            covered = True
            reason = "Policy excerpts indicate this item is covered."
        else:
            covered, reason = _structured_llm_verdict(issue, docs)

        candidates.append({
            "plan": plan,
            "covered": covered,
            "reason": reason,
            "citations": format_citations(docs),
        })

    if not candidates:
        return []

    # Prefer plans that DO cover, ordered by tier; otherwise show a few counterexamples.
    covered_plans = [c for c in candidates if c["covered"]]
    if covered_plans:
        covered_plans.sort(key=lambda c: PLAN_RANK.get(c["plan"], 100))
        return covered_plans[:limit]

    # None cover → show top few not-covered with reasons (so UI can explain)
    candidates.sort(key=lambda c: PLAN_RANK.get(c["plan"], 100))
    return candidates[:min(limit, len(candidates))]
