# HomeShield AI – Dataset Stats (Augmented)

- Policies: 300 TXT docs (50 states × 3 plans × 2 years)
- Addenda: 5 TXT docs
- Customers: 2,000
- Claims: 20,000
- Invoices: 12,000
- Technicians: 1,000
- Coverage Questions: 500
- Eval Pairs: 200

## Key Files
- policies/: policy text files per state/plan/year
- customers.csv, claims.csv, invoices.csv, technicians.csv
- coverage_questions.jsonl — prompts you can feed to /coverage/query
- evaluation_pairs.jsonl — gold set for smoke testing
- rag_gold.jsonl — (from earlier) broader RAG evaluation set