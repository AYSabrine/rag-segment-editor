"""
ingest.py — build the RAG vector store.
Indexes the variable knowledge base (docs/variables.md) and each segment rule
so the assistant can RETRIEVE relevant context before proposing a change.
Run once:  python rag/ingest.py
"""
import os
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter

from engine import load_rules
from settings import load_env

load_env()

HERE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_MD = os.path.join(HERE, "docs", "variables.md")
DB_DIR  = os.path.join(HERE, "chroma_db")

def build_documents():
    docs = []
    # 1) variable knowledge base (chunked)
    with open(DOCS_MD, encoding="utf-8") as f:
        md = f.read()
    for chunk in MarkdownTextSplitter(chunk_size=500, chunk_overlap=50).split_text(md):
        docs.append(Document(page_content=chunk, metadata={"source": "variables.md"}))
    # 2) one document per rule (so the model can resolve names -> ids)
    rules = load_rules()
    for _, r in rules.iterrows():
        txt = (f"Segment {r.segment_id} '{r.segment_name}': renewal_group={r.renewal_group}, "
               f"lapse_group={r.lapse_group}, offer_intensity={r.offer_intensity}, "
               f"roaming_rule={r.roaming_rule}, risk_combos={r.risk_combos}, "
               f"tenure [{r.tenure_min},{r.tenure_max}), renewals [{r.renew_min},{r.renew_max}), "
               f"late_days [{r.late_days_min},{r.late_days_max}), is_active={r.is_active}.")
        docs.append(Document(page_content=txt, metadata={"source": "rule", "segment_id": r.segment_id}))
    return docs

def main():
    docs = build_documents()
    emb  = OpenAIEmbeddings(model="text-embedding-3-small")
    # rebuild from scratch: re-running must not duplicate documents
    Chroma(persist_directory=DB_DIR, embedding_function=emb).delete_collection()
    Chroma.from_documents(docs, emb, persist_directory=DB_DIR)
    print(f"Indexed {len(docs)} documents into {DB_DIR}")

if __name__ == "__main__":
    main()
