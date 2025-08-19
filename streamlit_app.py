import os, streamlit as st
from dotenv import load_dotenv
from app.services.customers import get_customer
from app.services.rag import retrieve_chunks, answer_with_context, format_citations
from app.services.claims import evaluate_claim

load_dotenv()  # read .env at project root

st.set_page_config(page_title="HomeShield – Chat", page_icon="🛡️", layout="wide")
st.title("🛡️ HomeShield – Coverage Chat (no FastAPI)")

# Sidebar – choose a customer ID (plain text; you can improve by loading IDs)
default_id = os.environ.get("HOMESHIELD_CUSTOMER_ID","CUST-001")
customer_id = st.text_input("Customer ID", value=default_id)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role":"assistant","content":"Hi! Ask about your coverage — e.g., ‘Does my policy cover AC repair?’"}
    ]

# render history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        meta = m.get("meta") or {}
        cites = meta.get("citations") or []
        if cites:
            with st.expander("Citations"):
                for i,c in enumerate(cites,1):
                    st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                    st.code(c["text"])

prompt = st.chat_input("Type your question and press Enter…")

if prompt:
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            cust = get_customer(customer_id)
            docs = retrieve_chunks(prompt, cust["plan"], cust["state"], cust["effective_year"])
            if not docs:
                msg = "I couldn't find relevant clauses for your policy."
                st.error(msg)
                st.session_state.messages.append({"role":"assistant","content":msg})
            else:
                ans = answer_with_context(prompt, docs)
                meta = {"citations": format_citations(docs)}
                st.markdown(ans)
                st.session_state.messages.append({"role":"assistant","content":ans,"meta":meta})
        except Exception as e:
            err = f"Sorry — I couldn't complete that. {e}"
            st.error(err)
            st.session_state.messages.append({"role":"assistant","content":err})

st.divider()
st.subheader("Evaluate last message as a claim")
last_user = next((m["content"] for m in reversed(st.session_state.messages) if m["role"]=="user"), "")
issue = st.text_area("Issue description", value=last_user or "AC stopped cooling")
if st.button("Evaluate Claim", type="primary", use_container_width=True, disabled=not customer_id.strip()):
    try:
        cust = get_customer(customer_id)
        result = evaluate_claim(issue, cust["plan"], cust["state"], cust["effective_year"])
        badge = "✅ Covered" if result["covered"] else "❌ Not Covered"
        content = f"**{badge}** — {result['reason']}"
        st.success(content)
        st.session_state.messages.append({"role":"assistant","content":content,"meta":{"citations":result["citations"]}})
        if result["citations"]:
            with st.expander("Citations"):
                for i,c in enumerate(result["citations"],1):
                    st.markdown(f"**{i}.** `{c['source']}` p.{c['page']}")
                    st.code(c["text"])
    except Exception as e:
        st.error(f"Claim evaluation failed: {e}")
