import os
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.services.customers import get_customer
from app.services.rag import retrieve_chunks, answer_with_context, format_citations
from app.services.claims import evaluate_claim

# ---------- Setup ----------
load_dotenv()  # read .env at project root
st.set_page_config(page_title="HomeShield – Chat", page_icon="🛡️", layout="wide")
st.title("🛡️ HomeShield – Coverage Chat")

# ---------- Helpers ----------
@st.cache_data(show_spinner=False)
def load_customer_ids_from_env() -> list[str]:
    """
    Load customer IDs from CUSTOMERS_CSV (if available), so users pick valid IDs.
    """
    csv = os.environ.get("CUSTOMERS_CSV")
    if not csv or not os.path.exists(csv):
        return []
    try:
        df = pd.read_csv(csv)
        col = "customer_id" if "customer_id" in df.columns else df.columns[0]
        return df[col].astype(str).tolist()
    except Exception:
        return []

def normalize_reason(covered: bool, reason: str) -> str:
    """
    Strip leading 'Covered'/'Not covered' from model text so it doesn't duplicate the badge.
    Keep the sentence clean and capitalized.
    """
    r = re.sub(r"^\s*(?:not\s+)?covered[:\-\s]*", "", reason, flags=re.I).strip()
    return (r[0].upper() + r[1:]) if r else reason

def customer_badge_row(cust: dict | None):
    if not cust:
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Plan", str(cust.get("plan", "")))
    c2.metric("State", str(cust.get("state", "")))
    c3.metric("Effective Year", str(int(cust.get("effective_year", 0))))


# ---------- Sidebar: Customer selection ----------
all_ids = load_customer_ids_from_env()
default_id = os.environ.get("HOMESHIELD_CUSTOMER_ID", (all_ids[0] if all_ids else "CUST-001"))

if all_ids:
    customer_id = st.sidebar.selectbox("Customer ID", options=all_ids, index=0)
else:
    customer_id = st.sidebar.text_input("Customer ID", value=default_id)

# ---------- Try to load customer to show plan/state/year chips ----------
cust = None
cust_err = None
try:
    cust = get_customer(customer_id)
except Exception as e:
    cust_err = str(e)

if cust_err:
    st.warning(f"Customer not found or CSV missing: {cust_err}")
else:
    customer_badge_row(cust)

st.caption("Answers are derived strictly from your policy documents. If a clause is not present, the app will say so.")

# ---------- Chat history ----------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! Ask about your coverage — e.g., ‘Does my policy cover AC repair?’"}
    ]

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

# ---------- Chat input ----------
prompt = st.chat_input("Type your question and press Enter…")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            if not cust:
                raise RuntimeError("Please select a valid Customer ID first.")
            docs = retrieve_chunks(prompt, cust["plan"], cust["state"], cust["effective_year"])
            if not docs:
                msg = "I couldn't find relevant clauses for your policy."
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            else:
                ans = answer_with_context(prompt, docs)
                meta = {"citations": format_citations(docs)}
                st.markdown(ans)
                st.session_state.messages.append({"role": "assistant", "content": ans, "meta": meta})
        except Exception as e:
            err = f"Sorry — I couldn't complete that. {e}"
            st.error(err)
            st.session_state.messages.append({"role": "assistant", "content": err})

# ---------- Claim Evaluation ----------
st.divider()
st.subheader("Evaluate last message as a claim")

last_user = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), "")
issue = st.text_area("Issue description", value=last_user or "AC stopped cooling")

disabled = not (customer_id and customer_id.strip() and cust)
if st.button("Evaluate Claim", type="primary", use_container_width=True, disabled=disabled):
    try:
        if not cust:
            raise RuntimeError("Please select a valid Customer ID first.")

        result = evaluate_claim(issue, cust["plan"], cust["state"], cust["effective_year"])

        badge = "✅ Covered" if result["covered"] else "❌ Not Covered"
        reason = normalize_reason(result["covered"], result["reason"])
        content = f"**{badge}** — {reason}"

        # GREEN for covered, RED for not covered
        (st.success if result["covered"] else st.error)(content)

        # Save to history with citations
        st.session_state.messages.append({
            "role": "assistant",
            "content": content,
            "meta": {"citations": result.get("citations", [])}
        })

        # Show citations inline
        if result.get("citations"):
            with st.expander("Citations"):
                for i, c in enumerate(result["citations"], 1):
                    st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                    st.code(c["text"])

    except Exception as e:
        st.error(f"Claim evaluation failed: {e}")
