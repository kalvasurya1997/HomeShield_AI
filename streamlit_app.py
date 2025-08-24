# streamlit_app.py
import os
import inspect
import streamlit as st
from dotenv import load_dotenv

from app.services.customers import get_customer
import app.services.rag as rag              # import the module (safer for optional helpers)
from app.services.claims import evaluate_claim
from app.vectorstore import chat_client     # for simple intent routing & chitchat

load_dotenv()

# ------------------------------- Page setup -----------------------------------
st.set_page_config(
    page_title="HomeShield – Coverage Chat",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
      .block-container {max-width: 920px; padding-top: 1.25rem;}
      header {visibility: hidden;}
      .hs-title {display:flex; align-items:center; gap:10px; font-size:1.55rem; font-weight:700}
      .hs-title .logo {font-size:1.35rem}
      .hs-chip {display:inline-block; padding:6px 10px; border-radius:16px;
                background:#eef3ff; color:#1f3b8f; font-size:0.90rem; margin-right:8px;}
      .hs-muted {color:#6b7280; font-size:0.95rem}
      .stChatMessage p {font-size: 1.02rem; line-height: 1.5;}
      .stChatMessage [data-testid="stMarkdownContainer"] ul {margin-top:0.25rem}
      .stButton>button {border-radius:999px}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------- Helpers --------------------------------------
def _init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant",
            "content": "Hi! I’m HomeShield. Ask about your coverage — e.g., “Does my policy cover AC repair?”",
        }]
    st.session_state.setdefault("customer_id", "")
    st.session_state.setdefault("last_issue", "")   # memory: last resolved coverage question
    st.session_state.setdefault("last_docs", [])
    st.session_state.setdefault("policy_source", None)

def _pill(label: str, value: str):
    st.markdown(f'<span class="hs-chip"><b>{label}:</b> {value}</span>', unsafe_allow_html=True)

def _render_citations(docs_or_cites):
    """
    Accepts either a list[Document] or already-formatted list[dict] with keys (source,page,text).
    """
    if not docs_or_cites:
        return
    # Detect if we received Documents (have attribute 'page_content')
    cites = None
    first = docs_or_cites[0] if isinstance(docs_or_cites, list) else None
    if first is not None and hasattr(first, "page_content"):
        cites = rag.format_citations(docs_or_cites)
    elif isinstance(first, dict):
        cites = docs_or_cites
    else:
        return

    if not cites:
        return
    with st.expander("Citations", expanded=False):
        for i, c in enumerate(cites, 1):
            st.markdown(f"**{i}.** `{c.get('source','unknown.txt')}` p.{c.get('page','')}")
            st.code(c.get("text",""))

def _load_customer(cid: str):
    try:
        return get_customer(cid.strip())
    except Exception:
        return None

def _route_intent(user_msg: str, history) -> str:
    """
    Returns: coverage | clarification | claim_process | chitchat | not_sure
    """
    llm = chat_client(temperature=0)
    hist = "\n".join(
        f"{m['role']}:{m['content']}" for m in (history[-8:] if history else [])
        if m.get("content")
    )
    sys = (
        "Classify the user's latest message for a home-warranty chat, considering the last turns. "
        "Return only one label (lowercase word only):\n"
        "- coverage: asking if something is covered or comparing coverage\n"
        "- clarification: modifies/adds facts about the last coverage topic (e.g., 'not pre-existing', 'what about slab repair?')\n"
        "- claim_process: how to file/apply, service fee, dispatch, portal/phone\n"
        "- chitchat: greetings/thanks\n"
        "- not_sure: anything else"
    )
    user = f"History:\n{hist}\n\nLatest:\n{user_msg}"
    out = llm.invoke(
        [{"role": "system", "content": sys}, {"role": "user", "content": user}]
    ).content.strip().lower()
    if "clarification" in out: return "clarification"
    if "claim_process" in out: return "claim_process"
    if "coverage" in out: return "coverage"
    if "chitchat" in out: return "chitchat"
    return "not_sure"

def _answer_chitchat(user_msg: str) -> str:
    llm = chat_client(temperature=0.3)
    sys = (
        "You are a friendly, concise HomeShield concierge. Respond in 1–2 sentences. "
        "If the user asked a policy question, do not decide coverage; invite them to ask specifically."
    )
    return llm.invoke(
        [{"role": "system", "content": sys}, {"role": "user", "content": user_msg}]
    ).content.strip()

# Optional helpers from rag (present in newer versions)
rewrite_to_standalone = getattr(rag, "rewrite_to_standalone", None)
answer_claim_process = getattr(rag, "answer_claim_process", None)

# -------------------------------- Header --------------------------------------
_init_state()
with st.container():
    cols = st.columns([1, 7, 2])
    with cols[0]:
        st.markdown('<div class="hs-title"><span class="logo">🛡️</span>HomeShield</div>', unsafe_allow_html=True)
    with cols[2]:
        if st.button("Reset", use_container_width=True):
            st.session_state.clear()
            _init_state()
            st.rerun()

# ---------------------------- Customer context --------------------------------
cid = st.text_input("Customer ID", value=st.session_state.get("customer_id", ""), placeholder="e.g., C00182")
cust = None
if cid.strip():
    cust = _load_customer(cid)
    st.session_state["customer_id"] = cid

# Store the policy source (doc filename) for retrieval filtering
if cust:
    policy_src = os.path.basename(str(cust.get("policy_doc") or cust.get("policy_file") or ""))
    st.session_state["policy_source"] = policy_src if policy_src else None

if cust:
    chip_cols = st.columns([1, 1, 1, 3])
    with chip_cols[0]:
        _pill("Plan", str(cust.get("plan", "")))
    with chip_cols[1]:
        _pill("State", str(cust.get("state", "")))
    with chip_cols[2]:
        year_val = cust.get("effective_year")
        try:
            year_str = "—" if year_val in (None, "") else str(int(float(year_val)))
        except Exception:
            year_str = "—"
        _pill("Year", year_str)
    with chip_cols[3]:
        if st.session_state.get("policy_source"):
            _pill("Doc", st.session_state["policy_source"])
else:
    st.markdown('<div class="hs-muted">Enter a valid Customer ID to load plan/state/year.</div>', unsafe_allow_html=True)

st.divider()

# ------------------------------ Chat history ----------------------------------
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        _render_citations(m.get("meta", {}).get("citations"))

# ------------------------------- Chat input -----------------------------------
prompt = st.chat_input("Message HomeShield…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not cust:
            msg = "Please enter a valid Customer ID so I can check the correct plan/state/year."
            st.warning(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
        else:
            try:
                intent = _route_intent(prompt, st.session_state.messages)

                if intent == "chitchat":
                    ans = _answer_chitchat(prompt)
                    st.markdown(ans)
                    st.session_state.messages.append({"role": "assistant", "content": ans})

                elif intent == "claim_process" and callable(answer_claim_process):
                    # Dedicated answer for claim process (if available in rag)
                    ans, docs = answer_claim_process(
                        prompt,
                        cust["plan"],
                        cust["state"],
                        cust.get("effective_year")
                    )
                    st.markdown(ans)
                    meta = {"citations": rag.format_citations(docs)}
                    st.session_state.messages.append({"role": "assistant", "content": ans, "meta": meta})
                    _render_citations(docs)

                else:
                    # coverage / clarification / not_sure -> rewrite with memory (if helper available)
                    if callable(rewrite_to_standalone):
                        resolved_q = rewrite_to_standalone(
                            user_msg=prompt,
                            history=st.session_state.messages,
                            plan=cust["plan"],
                            state=cust["state"],
                            year=cust.get("effective_year"),
                            last_issue=st.session_state.get("last_issue") or "",
                        )
                    else:
                        resolved_q = prompt  # fallback

                    docs = rag.retrieve_chunks(
                        resolved_q,
                        cust["plan"],
                        cust["state"],
                        cust.get("effective_year"),
                        policy_source=st.session_state.get("policy_source")  # <<--- IMPORTANT
                    )

                    if not docs:
                        msg = "I couldn't find policy text for that under your plan/state/year."
                        st.error(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                    else:
                        ans = rag.answer_with_context(resolved_q, docs)
                        st.markdown(ans)
                        meta = {"citations": rag.format_citations(docs)}
                        st.session_state.messages.append({"role": "assistant", "content": ans, "meta": meta})
                        _render_citations(docs)
                        # remember the resolved issue
                        st.session_state["last_issue"] = resolved_q
                        st.session_state["last_docs"] = meta["citations"]

            except Exception as e:
                err = f"Sorry — I couldn't complete that. {e}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})

# -------------------- Optional quick adjudication (button) --------------------
with st.expander("⚖️  Quick evaluate a specific issue (yes/no with reason)", expanded=False):
    issue = st.text_input(
        "Issue summary (e.g., 'Main sewer line backup at 35ft; roots; slab break required')",
        key="issue_input",
    )
    run_eval = st.button(
        "Evaluate",
        type="primary",
        use_container_width=True,
        disabled=not (cust and issue.strip())
    )
    if run_eval and cust:
        try:
            cust_year = cust.get("effective_year")
            # Build kwargs dynamically to stay compatible with your current evaluate_claim signature
            sig = inspect.signature(evaluate_claim)
            kwargs = {}
            if "last_issue" in sig.parameters:
                kwargs["last_issue"] = st.session_state.get("last_issue") or ""
            if "history" in sig.parameters:
                kwargs["history"] = st.session_state.messages
            if "policy_source" in sig.parameters:
                kwargs["policy_source"] = st.session_state.get("policy_source")

            result = evaluate_claim(
                issue,
                cust["plan"],
                cust["state"],
                cust_year,
                **kwargs
            )

            covered_raw = result.get("covered_raw")
            covered_bool = result.get("covered")
            badge = "✅ Covered" if covered_bool else ("⚠️ Unclear" if covered_raw == "uncertain" else "❌ Not Covered")
            st.markdown(f"**{badge}** — {result.get('reason','')}")
            _render_citations(result.get("citations"))
            # push into chat history + remember
            st.session_state.messages.append({"role": "user", "content": issue})
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"**{badge}** — {result.get('reason','')}",
                "meta": {"citations": result.get("citations", [])},
            })
            st.session_state["last_issue"] = result.get("resolved_question", issue)
            st.session_state["last_docs"] = result.get("citations", [])
        except Exception as e:
            st.error(f"Claim evaluation failed: {e}")
