import os
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.services.customers import get_customer
from app.services.rag import retrieve_chunks, answer_with_context, format_citations
from app.services.claims import evaluate_claim

# ----------------------- Setup -----------------------
load_dotenv()  # read .env at project root
st.set_page_config(page_title="HomeShield – Chat", page_icon="🛡️", layout="wide")
st.title("🛡️ HomeShield – Coverage Chat")

# --------------------- Helpers -----------------------
def normalize_reason(covered: bool, reason: str) -> str:
    """
    Strip leading 'Covered'/'Not covered' from model text so it doesn't duplicate the badge.
    Keep the sentence clean and capitalized.
    """
    r = re.sub(r"^\s*(?:not\s+)?covered[:\-\s]*", "", reason, flags=re.I).strip()
    return (r[0].upper() + r[1:]) if r else reason

def try_load_customer(customer_id: str):
    """Return (customer_dict, error_message_or_None)."""
    try:
        if not customer_id or not customer_id.strip():
            return None, "Please enter a Customer ID in the sidebar."
        cust = get_customer(customer_id.strip())
        return cust, None
    except Exception as e:
        return None, str(e)

def customer_badge_row(cust: dict | None):
    if not cust:
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Plan", str(cust.get("plan", "")))
    c2.metric("State", str(cust.get("state", "")))
    c3.metric("Effective Year", str(int(cust.get("effective_year", 0))))

# ---------------- Sidebar: typed Customer ID ----------
default_id = os.environ.get("HOMESHIELD_CUSTOMER_ID", "CUST-001")
customer_id = st.sidebar.text_input("Customer ID", value=default_id, help="Type the customer ID (e.g., C00001).")
st.sidebar.caption("The chat will use this ID for all answers.")

# Cache the customer lookup each rerun
cust, cust_err = try_load_customer(customer_id)
if cust_err:
    st.warning(f"Customer not found or CSV issue: {cust_err}")
else:
    customer_badge_row(cust)

# ---------------- Conversation memory -----------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I’m HomeShield. Ask about your coverage — e.g., “Does my policy cover AC repair?”"}
    ]

# Keep the last user issue so the user (or a button) can evaluate it
if "pending_issue" not in st.session_state:
    st.session_state.pending_issue = ""

# Reset button (optional utility)
st.sidebar.markdown("---")
if st.sidebar.button("Reset conversation"):
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I’m HomeShield. Ask about your coverage — e.g., “Does my policy cover AC repair?”"}
    ]
    st.session_state.pending_issue = ""
    st.experimental_rerun()

# ---------------- Render history ----------------------
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        meta = m.get("meta") or {}
        cites = meta.get("citations") or []
        if cites:
            with st.expander("Citations"):
                for i, c in enumerate(cites, 1):
                    st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                    st.code(c["text"])

# ---------------- Chat input --------------------------
prompt = st.chat_input("Type your message and press Enter…")

if prompt:
    # Store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant flow
    with st.chat_message("assistant"):
        try:
            # Require a valid customer before answering
            if not cust:
                msg = "I couldn’t find that Customer ID. Please enter a valid ID in the sidebar and try again."
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            else:
                # Treat the user's message as the issue/question for RAG
                issue = prompt
                st.session_state.pending_issue = issue  # keep for claim evaluation

                docs = retrieve_chunks(issue, cust["plan"], cust["state"], cust["effective_year"])
                if not docs:
                    msg = "I couldn't find relevant clauses for your policy."
                    st.error(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                else:
                    # Provide an agent-like answer with citations
                    answer = answer_with_context(issue, docs)
                    meta = {"citations": format_citations(docs)}
                    st.markdown(answer)

                    # Save assistant answer
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "meta": meta
                    })

        except Exception as e:
            err = f"Sorry — I couldn't complete that. {e}"
            st.error(err)
            st.session_state.messages.append({"role": "assistant", "content": err})

# -------------- Conversational Claim Eval --------------
st.divider()
st.subheader("Evaluate the last user issue as a claim")

if not cust:
    st.info("Enter a valid Customer ID in the sidebar to enable claim evaluation.")
else:
    # Use the last user's message as the default issue text
    last_user_msg = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), "")
    default_issue = st.session_state.pending_issue or last_user_msg or "AC stopped cooling"
    issue_text = st.text_area("Issue description", value=default_issue, help="You can edit this before evaluation.")

    if st.button("Evaluate Claim", type="primary", use_container_width=True):
        try:
            result = evaluate_claim(issue_text, cust["plan"], cust["state"], cust["effective_year"])
            badge = "✅ Covered" if result["covered"] else "❌ Not Covered"
            reason = normalize_reason(result["covered"], result["reason"])
            content = f"**{badge}** — {reason}"

            # GREEN for covered, RED for not covered
            (st.success if result["covered"] else st.error)(content)

            # Record into chat history, with citations
            st.session_state.messages.append({
                "role": "assistant",
                "content": content,
                "meta": {"citations": result.get("citations", [])}
            })

            # Render citations inline right away
            if result.get("citations"):
                with st.expander("Citations"):
                    for i, c in enumerate(result["citations"], 1):
                        st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                        st.code(c["text"])

            # Keep the evaluated issue as the new pending issue
            st.session_state.pending_issue = issue_text

        except Exception as e:
            st.error(f"Claim evaluation failed: {e}")

# -------------- Footer note ---------------------------
st.caption("This is a multi-turn conversation. Ask follow-up questions, change the Customer ID, or evaluate the last issue as a claim at any time.")
