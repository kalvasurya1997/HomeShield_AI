# app/services/router.py
import json
from typing import List, Dict
from ..vectorstore import chat_client

INTENTS = ["coverage", "claim_process", "claim_eval", "upgrade", "smalltalk", "other"]

def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if "```" in s[3:] else s
    return s.strip()

def detect_intent(history: List[Dict[str, str]], user_msg: str) -> Dict:
    """
    Classify the current turn.
    Returns: {"intent": <one of INTENTS>, "confidence": 0..1, "reason": "..."}
    """
    llm = chat_client(temperature=0)
    # Keep last few turns for context
    hist = history[-6:]
    hist_txt = "\n".join(f"{m['role']}: {m['content']}" for m in hist)

    sys = (
        "You are an intent router for a HOME WARRANTY assistant. "
        "Choose exactly one intent for the user's latest message:\n"
        "- coverage: asking if something is covered / what plan covers X\n"
        "- claim_process: how to file/apply/submit/next steps/documentation/fees/scheduling\n"
        "- claim_eval: adjudicate a specific issue (is THIS scenario covered? yes/no + reason)\n"
        "- upgrade: compare plans, add-ons, what plan to upgrade to\n"
        "- smalltalk: greetings, thanks, chit-chat not requiring policy context\n"
        "- other: anything else\n"
        "Return strict JSON: {\"intent\":\"<one>\",\"confidence\":<0..1>,\"reason\":\"...\"} "
        "Be decisive; prefer claim_process for 'how do I apply/submit file a claim' questions."
    )
    user = f"Conversation so far:\n{hist_txt}\n\nUser now says:\n{user_msg}\n\nRespond with JSON only."
    raw = llm.invoke([{"role":"system","content":sys},{"role":"user","content":user}]).content
    try:
        data = json.loads(_strip_fences(raw))
        intent = data.get("intent","other")
        if intent not in INTENTS: intent = "other"
        conf = float(data.get("confidence", 0.51))
        reason = data.get("reason","")
        return {"intent": intent, "confidence": conf, "reason": reason}
    except Exception:
        # Safe fallback: very common phrases
        msg = user_msg.lower()
        if any(k in msg for k in ["apply", "file", "submit"]) and "claim" in msg:
            return {"intent":"claim_process","confidence":0.6,"reason":"keyword fallback"}
        if any(k in msg for k in ["upgrade","plan","add-on","add on"]):
            return {"intent":"upgrade","confidence":0.55,"reason":"keyword fallback"}
        if any(k in msg for k in ["thanks","thank you","hello","hi","hey"]):
            return {"intent":"smalltalk","confidence":0.55,"reason":"keyword fallback"}
        return {"intent":"coverage","confidence":0.5,"reason":"default"}
