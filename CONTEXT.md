# CONTEXT — read me first (full project brief for Claude Code)

> Read this entire file before doing anything. It explains the WHOLE project:
> the business problem, the architecture, the decisions, what is done, and what
> you (Claude Code) are asked to help with — including a **presentation and a
> demo video**.

---

## 0. Environment notes (important)
- On this machine, **Python is `py -3.11`** (NOT `python` or `py` alone).
  - run a script:  `py -3.11 script.py`
  - pip:           `py -3.11 -m pip install -r requirements.txt`  (already done)
  - streamlit:     `py -3.11 -m streamlit run app/main.py`
- The **OpenAI API key** is provided by the user as an environment variable
  `OPENAI_API_KEY` in the terminal. NEVER put it in a file or commit it.
- Everything here is **100% synthetic**. No real operator data, table name,
  schema or credential may ever appear in this project.

---

## 1. The story / business problem (use this for the presentation)
A prepaid telecom operator has **millions of subscribers**. Each one should
receive the **Next Best Offer (NBO)** — the right bundle, at the right level of
aggressiveness, at the right lifecycle moment.

The old way: targeting logic was **hard-coded**. Every rule change needed a
**developer and a release** — slow, risky, no visibility on impact.

This project removes the developer from the loop: the **business owns the rules**,
changes them in **plain English**, sees the **impact before applying**, and the
system applies them automatically once all checks pass.

*(Origin line for slides: "Inspired by a real NBO system the author built for a
telecom operator; all data here is synthetic.")*

---

## 2. Architecture — 3 levels (the spine of the presentation)

### LEVEL 1 — NBO Segmentation Engine (data engineering)
For each subscriber, behavioural variables are computed (datamart):
- **tenure** (days since activation)
- **renewals_6m** (main-bundle renewals in 180 days → loyalty level)
- **lapse band** (how late on the bundle: Active → Slipping → Lapsed → Lost)
- **spend slope** (spending trend up/flat/down)
- **churn band** (churn probability Low/Med/High)
- **roaming** (is a late customer just travelling)

The engine matches each subscriber against a **rule grid** (a TABLE, not code):
```
tenure ∈ [min,max] AND renewals ∈ [min,max] AND lapse ∈ [min,max]
AND roaming compatible AND risk (slope+churn) ∈ allowed combinations
→ exactly one segment → one offer intensity (NONE/NORMAL/AGGRESSIVE/VERY_AGGRESSIVE)
```
The **Next Best Offer = the matched segment's offer**. Changing the strategy =
changing a **row in the table**, not the code. (Implemented in rag/engine.py.)

### LEVEL 2 — Self-service governance
A rule change is **validated** (guardrails: bounds, enums, risk format, no new
variable) and **impact-simulated** (how many subscribers move, segment by
segment). If all checks pass → applied automatically; if a check fails →
rejected with the reason. (Implemented in rag/engine.py: validate_change,
simulate_impact.)

### LEVEL 3 — RAG natural-language editor (the AI part)
```
User: "make the Regular Nudge segment more aggressive"
  → RAG RETRIEVES current rules + variable knowledge base (vector store)
  → LLM GENERATES a structured change JSON
       {"segment_id":"C08","field":"offer_intensity","new_value":"VERY_AGGRESSIVE"}
  → VALIDATED + IMPACT-SIMULATED (Level 2) → applied if valid
```
Why it is genuine RAG: the LLM does NOT know the rules; it retrieves them first,
then generates a change grounded in that context. The AI only PROPOSES; the
deterministic engine VERIFIES and applies. (rag/ingest.py builds the store,
rag/chain.py is the chain.)

---

## 3. Tech stack
Python · LangChain · OpenAI (`gpt-4o-mini` LLM + `text-embedding-3-small`
embeddings) · Chroma (local vector store) · Streamlit (UI) · pandas.
Provider-agnostic by design: the LLM/embeddings could be swapped for a local
model (Ollama / sentence-transformers) for a fully on-premise, no-data-leaves
deployment — a relevant point for sensitive telecom data.

---

## 4. Files
- data/generate_synthetic_data.py -> segment_rules.csv (14 fictional rules) + subscribers.csv (6000)
- docs/variables.md               -> RAG knowledge base (indexed)
- rag/engine.py                   -> deterministic NBO: assign / validate / simulate
- rag/ingest.py                   -> build the Chroma vector store (needs OPENAI_API_KEY)
- rag/chain.py                    -> RAG text-to-config chain (needs OPENAI_API_KEY)
- app/main.py                     -> Streamlit UI
- README.md                       -> portfolio showcase (already written)
- CONTEXT.md                      -> this file

---

## 5. Status — what is already done
- Deterministic logic fully tested (engine, validation, simulation): 15/15 passed.
- Synthetic data tuned so the engine assigns ~100% of subscribers (0 UNASSIGNED,
  0 MULTIPLE) — a clean, realistic coverage for a demo.
- README is the portfolio showcase (NBO + governance + RAG, with a Mermaid diagram).
- The LLM/embeddings calls were NOT run yet (needs the API key on this machine).

---

## 6. What to help the user with (tasks)
1. **Run it**: `py -3.11 rag/ingest.py`, then `py -3.11 -m streamlit run app/main.py`.
   Fix any LangChain import/version mismatch (packages drift: langchain-openai,
   langchain-chroma, langchain-text-splitters). Keep the code clean.
2. **Verify the demo**: try requests like
   - "make the Regular Nudge segment more aggressive"
   - "disable the Silent Last Call segment"
   - "target high churn customers in Champion Upsell"
   and confirm: proposed change (JSON) → validation → impact simulation → applied.
3. **Prepare a project PRESENTATION** (slides). Structure suggestion:
   - problem (business) → NBO engine → governance → RAG → architecture diagram
     → results/impact → tech stack & skills. Keep it value-first, anonymized.
4. **Prepare a DEMO VIDEO script + recording plan**: a 2–3 min walkthrough —
   show the problem, type a natural-language request, show the proposed change,
   the impact simulation, and the automatic apply. Provide a shot-by-shot script
   and suggested narration.
5. (Optional) Add screenshots to the README; then help publish to GitHub
   (git init/add/commit/push). .gitignore already protects the key and chroma_db/.

---

## 7. Hard rules
- NEVER commit the API key; it stays in the environment / .env.
- Keep everything synthetic — no real operator data, names, schemas, credentials.
- The AI proposes; the deterministic engine validates and applies. Do not let the
  LLM write directly to the data.
