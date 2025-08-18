from langchain.prompts import ChatPromptTemplate

qa_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are HomeShield AI. Answer ONLY using the provided context from policy documents. "
               "Return STRICT JSON with keys: answer: string, citations: list of {source, page, quote}."),
    ("human", "Question: {question}\n\nContext:\n{context}")
])

extract_prompt = ChatPromptTemplate.from_messages([
    ("system", "Extract claim fields from text. Return STRICT JSON with keys: "
               "appliance: string, issue: string, failure_date: string | null."),
    ("human", "{message}")
])

decision_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a coverage validator. Use ONLY the provided context. "
               "Return STRICT JSON: {decision: covered|partial|denied|ambiguous, "
               "reasons: list[string], citations: list[{source, page, quote}]}"),
    ("human", "Customer plan: {plan}, {state}, {year}\n"
              "Appliance: {appliance}\nIssue: {issue}\nFailure date: {failure_date}\n\n"
              "Context:\n{context}")
])
