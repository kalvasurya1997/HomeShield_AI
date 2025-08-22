# streamlit_app.py
import os
import streamlit as st
from dotenv import load_dotenv

from app.services.customers import get_customer
from app.services.rag import retrieve_chunks, answer_with_context, format_citations
from app.services.claims import evaluate_claim
from app.services.router import classify_message, small_talk_reply

# Optional: if you haven't added upgrades.py yet, this stub keeps the app running
try:
    from app.services.upgrades import suggest_alternative_plans
except Exception:
    def suggest_alternative_plans(**kwargs):
        return []

# ------------------- Setup -------------------
load_dotenv()
st.set_page_config(page_title="HomeShield – Chat", page_icon="🛡️", layout="centered")

# Minimal CSS to tighten spacing & center content like ChatGPT
st.markdown(
    """
    <style>
      .block-container { max-width: 820px; padding-top: 1.5rem; }
      .stChatMessage { padding-bottom: 0.25rem; }
      .topbar { display:flex; gap:0.5rem; align-items:center; }
      .chips { color:#555; font-size:0.9rem; margin-top:-0.25rem; }
      .chip { background:#f5f5f7; border-radius:999px; padding:2px 10px; margin-right:6px; display:inline-block; }
      .msg-meta { font-size:0.85rem; color:#666; margin-top:0.35rem; }
      .cite-box { border:1px solid #eee; background:#fafafa; padding:8px 10px; border-radius:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## 🛡️ HomeShield")

# ------------------- State -------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I’m HomeShield. Ask about your coverage — e.g., “Does my policy cover AC repair?”"}
    ]
if "last_issue" not in st.session_state:
    st.session_state.last_issue = ""
if "last_claim" not in st.session_state:
    st.session_state.last_claim = None

# ------------------- Header (ChatGPT-like top bar) -------------------
default_id = os.environ.get("HOMESHIELD_CUSTOMER_ID", "C00001")
c1, c2 = st.columns([4, 1])
with c1:
    customer_id = st.text_input("Customer ID", value=default_id, label_visibility="collapsed", placeholder="Enter Customer ID (e.g., C00001)")
with c2:
    if st.button("Reset"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Hi! I’m HomeShield. Ask about your coverage — e.g., “Does my policy cover AC repair?”"}
        ]
        st.session_state.last_issue = ""
        st.session_state.last_claim = None
        st.rerun()

# Load customer and show small chips row (like ChatGPT’s model pill)
cust = None
cust_error = None
try:
    if customer_id.strip():
        cust = get_customer(customer_id.strip())
except Exception as e:
    cust_error = str(e)

if cust_error:
    st.warning(f"Customer error: {cust_error}")
elif cust:
    st.markdown(
        f"""<div class="chips">
             <span class="chip">Plan: <b>{cust.get('plan','')}</b></span>
             <span class="chip">State: <b>{cust.get('state','')}</b></span>
             <span class="chip">Year: <b>{int(cust.get('effective_year',0))}</b></span>
           </div>""",
        unsafe_allow_html=True,
    )

st.divider()

# ------------------- Chat history -------------------
def render_message(m):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        meta = m.get("meta") or {}
        cites = meta.get("citations") or []
        if cites:
            with st.expander("Citations"):
                for i, c in enumerate(cites, 1):
                    st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                    st.code(c["text"])

for msg in st.session_state.messages:
    render_message(msg)

# ------------------- Chat input (bottom, like ChatGPT) -------------------
prompt = st.chat_input("Message HomeShield...")

def _normalize_reason(text: str) -> str:
    t = (text or "").strip()
    return (t[:1].upper() + t[1:]) if t else t

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    render_message({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        if not cust:
            reply = "I couldn’t find that Customer ID. Please enter a valid ID and try again."
            st.error(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        else:
            try:
                # LLM intent router steers the conversation (no hard-coded rules)
                route = classify_message(prompt, last_issue=st.session_state.last_issue)
                intent = (route.get("intent") or "other").lower()
                issue  = (route.get("issue") or "").strip()

                if intent == "small_talk":
                    reply = small_talk_reply(prompt)
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

                elif intent == "upgrades":
                    topic = issue or st.session_state.last_issue or prompt
                    suggestions = suggest_alternative_plans(
                        issue=topic,
                        current_plan=cust["plan"],
                        state=cust["state"],
                        year=cust["effective_year"],
                        limit=3,
                    )
                    if not suggestions:
                        msg = "I couldn’t find other plans in your state/year that mention this item."
                        st.warning(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                    else:
                        lines = []
                        for s in suggestions:
                            badge = "✅ Would be Covered" if s["covered"] else "❌ Still Not Covered"
                            reason = _normalize_reason(s["reason"])
                            lines.append(f"- **{badge} — {s['plan']}** — {reason}")
                        summary = "Here’s what I found for other plans:\n\n" + "\n".join(lines)
                        st.markdown(summary)
                        st.session_state.messages.append({"role": "assistant", "content": summary})
                        for s in suggestions:
                            if s.get("citations"):
                                with st.expander(f"Citations – {s['plan']}"):
                                    for i, c in enumerate(s["citations"], 1):
                                        st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                                        st.code(c["text"])
                    if issue:
                        st.session_state.last_issue = issue

                else:
                    # coverage / limits / other -> do RAG QA
                    topic = issue or prompt
                    docs = retrieve_chunks(topic, cust["plan"], cust["state"], cust["effective_year"])
                    if not docs:
                        msg = "I couldn't find relevant clauses for your policy."
                        st.error(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                    else:
                        answer = answer_with_context(prompt, docs)
                        meta = {"citations": format_citations(docs)}
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer, "meta": meta})
                        if issue:
                            st.session_state.last_issue = issue

            except Exception as e:
                err = f"Sorry — I couldn't complete that. {e}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})

# ------------------- One small “ChatGPT-like” action: evaluate last issue -------------------
with st.container():
    if cust and st.session_state.last_issue:
        if st.button("⚖️ Evaluate last issue as a claim"):
            try:
                res = evaluate_claim(st.session_state.last_issue, cust["plan"], cust["state"], cust["effective_year"])
                badge = "✅ Covered" if res["covered"] else "❌ Not Covered"
                reason = _normalize_reason(res["reason"])
                content = f"**{badge}** — {reason}"

                (st.success if res["covered"] else st.error)(content)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": content,
                    "meta": {"citations": res.get("citations", [])}
                })
                if res.get("citations"):
                    with st.expander("Citations"):
                        for i, c in enumerate(res["citations"], 1):
                            st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                            st.code(c["text"])
                st.session_state.last_claim = {"issue": st.session_state.last_issue, "result": res, "cust": cust}
            except Exception as e:
                st.error(f"Claim evaluation failed: {e}")
