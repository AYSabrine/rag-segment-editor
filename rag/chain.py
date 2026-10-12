"""
chain.py — the RAG text-to-config chain.
NL request  ->  retrieve context  ->  LLM proposes a structured change (JSON).
The change is NOT applied here; it is returned for validation + simulation.
"""
import os, json
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma

from engine import load_rules, rules_summary, EDITABLE
from settings import load_env

load_env()

HERE   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(HERE, "chroma_db")

SYSTEM = """You are a segmentation rule editor for a telecom Next Best Offer engine.
Translate the user's request into ONE structured change to the rules table.

You may only change these fields: {editable}.
You must NOT invent new fields or new variables.

Return ONLY a JSON object:
{{"segment_id": "...", "field": "...", "new_value": "...", "reason": "..."}}

If the request names a segment that is not in CURRENT RULES, asks for a new
variable, or cannot be expressed as one change to an editable field, do NOT
guess: return {{"segment_id": null, "field": null, "new_value": null,
"reason": "<why no change can be proposed>"}}.

Allowed values:
- offer_intensity: NONE < NORMAL < AGGRESSIVE < VERY_AGGRESSIVE
- is_active: Y or N
- roaming_rule: ANY (ignore roaming), N (exclude roamers), Y (only roamers)
- risk_combos: ANY, or the FULL pipe-delimited list of SLOPE-CHURN items,
  SLOPE in POS/FLAT/NEG and CHURN in LOW/MED/HIGH, e.g. |POS-LOW|FLAT-HIGH|.
  To add items, repeat every existing item and append the new ones.
- bounds (tenure, renew, late_days min/max): integers, min inclusive, max exclusive.

Guidance from the knowledge base:
- "more aggressive" -> raise offer_intensity one level; "less aggressive" -> lower it one level.
- "disable / remove a segment" -> field is_active, new_value N.
- "widen / extend a band" -> change the relevant min/max bound.
- "target high churn" -> add POS-HIGH / FLAT-HIGH / NEG-HIGH to risk_combos.
Use the retrieved context and the current rules to pick the right segment_id."""

def get_retriever(k=5):
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    return Chroma(persist_directory=DB_DIR, embedding_function=emb).as_retriever(search_kwargs={"k": k})

def retrieve_context(request, k_rules=4, k_docs=2):
    """Retrieve from both sources: the closest rules AND the closest variable
    definitions (so the model always sees the allowed values it needs)."""
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    store = Chroma(persist_directory=DB_DIR, embedding_function=emb)
    return (store.similarity_search(request, k=k_rules, filter={"source": "rule"})
            + store.similarity_search(request, k=k_docs, filter={"source": "variables.md"}))

def propose_change(request, retriever=None):
    """Return the proposed change dict (RAG: retrieve -> generate)."""
    ctx_docs  = retriever.invoke(request) if retriever else retrieve_context(request)
    context   = "\n".join(d.page_content for d in ctx_docs)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0,
                     model_kwargs={"response_format": {"type": "json_object"}})
    prompt = (SYSTEM.format(editable=", ".join(EDITABLE))
              + "\n\n### RETRIEVED CONTEXT\n" + context
              + "\n\n### CURRENT RULES\n" + rules_summary(load_rules())
              + "\n\n### USER REQUEST\n" + request)
    resp = llm.invoke(prompt)
    change = json.loads(resp.content)
    # traceability: which documents the answer was grounded on
    change["retrieved"] = [d.metadata.get("segment_id", d.metadata.get("source")) for d in ctx_docs]
    return change

if __name__ == "__main__":
    print(propose_change("make the Regular Nudge segment more aggressive"))
