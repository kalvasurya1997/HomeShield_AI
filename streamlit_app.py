import os
import streamlit as st
from dotenv import load_dotenv

from app.services.customers import get_customer
from app.services.rag import retrieve_chunks, answer_with_context, format_citations
from app.services.claims import evaluate_claim
from app.services.router import classify_message, small_talk_reply

# optional – only if you added upgrades.py
try:
    from app.services.upgrades import suggest_alternative_plans
except Exception:
    def suggest_alternative_plans(**kwargs):  # fallback stub
        return []

# ----------------------- Setup -----------------------
load_dotenv()
st.set_page_config(page_title="HomeShield – Coverage Chat", page_icon="🛡️", layout="wide")
st.title("🛡️ HomeShield – Coverage Chat")

def normalize_reason(text: str) -> str:
    t = (text or "").strip()
    return t[:1].upper() + t[1:] if t else t

# ---------------- Sidebar: typed Customer ID ----------
default_id = os.environ.get("HOMESHIELD_CUSTOMER_ID", "CUST-001")
customer_id = st.sidebar.text_input("Customer ID", value=default_id, help="Type the customer ID (e.g., C00001).")
st.sidebar.caption("The chat will use this ID for all actions.")

# ---------------- Load customer & show chips ----------
cust = None
try:
    if customer_id.strip():
        cust = get_customer(customer_id.strip())
except Exception as e:
    st.warning(f"Customer not found or CSV error: {e}")

def customer_badge_row(cust):
    if not cust: return
    c1, c2, c3 = st.columns(3)
    c1.metric("Plan", str(cust.get("plan","")))
    c2.metric("State", str(cust.get("state","")))
    c3.metric("Effective Year", str(int(cust.get("effective_year", 0))))

customer_badge_row(cust)

# ---------------- Conversation memory -----------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I’m HomeShield. Ask about your coverage — e.g., “Does my policy cover AC repair?”"}
    ]
if "last_issue" not in st.session_state:
    st.session_state.last_issue = ""
if "last_claim" not in st.session_state:
    st.session_state.last_claim = None

st.sidebar.markdown("---")
if st.sidebar.button("Reset conversation"):
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I’m HomeShield. Ask about your coverage — e.g., “Does my policy cover AC repair?”"}
    ]
    st.session_state.last_issue = ""
    st.session_state.last_claim = None
    st.rerun()

# ---------------- Render history ----------------------
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        meta = (m.get("meta") or {})
        cites = meta.get("citations") or []
        if cites:
            with st.expander("Citations"):
                for i, c in enumerate(cites, 1):
                    st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                    st.code(c["text"])

# ---------------- Chat input --------------------------
prompt = st.chat_input("Type your message and press Enter…")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not cust:
            msg = "I couldn’t find that Customer ID. Please enter a valid ID in the sidebar and try again."
            st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
        else:
            try:
                route = classify_message(prompt, last_issue=st.session_state.last_issue)
                intent = route["intent"]
                issue = (route.get("issue") or "").strip()

                if intent == "small_talk":
                    reply = small_talk_reply(prompt)
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    # do NOT change last_issue
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
                        msg = "I couldn’t find other plan entries for your state/year that mention this item."
                        st.warning(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                    else:
                        lines = []
                        for s in suggestions:
                            badge = "✅ Would be Covered" if s["covered"] else "❌ Still Not Covered"
                            reason = normalize_reason(s["reason"])
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

                    # keep last_issue as topic if extracted
                    if issue:
                        st.session_state.last_issue = issue

                elif intent in ("coverage", "limits", "other"):
                    # Treat coverage/limits/general questions as RAG QA;
                    # update last_issue when we have a concrete one.
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

# -------------- Claim Evaluation panel --------------
st.divider()
st.subheader("Evaluate the last user issue as a claim")

if not cust:
    st.info("Enter a valid Customer ID in the sidebar to enable claim evaluation.")
else:
    default_issue = st.session_state.last_issue or "AC compressor failure"
    issue_text = st.text_area("Issue description", value=default_issue, help="You can edit this before evaluation.")

    if st.button("Evaluate Claim", type="primary", use_container_width=True):
        try:
            result = evaluate_claim(issue_text, cust["plan"], cust["state"], cust["effective_year"])
            badge = "✅ Covered" if result["covered"] else "❌ Not Covered"
            reason = normalize_reason(result["reason"])
            content = f"**{badge}** — {reason}"

            (st.success if result["covered"] else st.error)(content)
            st.session_state.messages.append({
                "role": "assistant",
                "content": content,
                "meta": {"citations": result.get("citations", [])}
            })

            if result.get("citations"):
                with st.expander("Citations"):
                    for i, c in enumerate(result["citations"], 1):
                        st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                        st.code(c["text"])

            st.session_state.last_claim = {"issue": issue_text, "result": result, "cust": cust}
            st.session_state.last_issue = issue_text
        except Exception as e:
            st.error(f"Claim evaluation failed: {e}")

st.caption("This assistant routes your messages with an LLM intent classifier")
