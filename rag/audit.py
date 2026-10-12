"""
audit.py — traceability of every rule-change request.
Each request (applied OR rejected) is appended to data/audit/change_log.jsonl:
who asked what, what the RAG retrieved, what the LLM proposed, what the
guardrails decided and why, and the simulated impact. Every applied change also
stores a snapshot of the rules before and after, so any change can be audited
or rolled back.
"""
import os, json, uuid
from datetime import datetime, timezone
import pandas as pd

HERE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(HERE, "data", "audit")
LOG_FILE  = os.path.join(AUDIT_DIR, "change_log.jsonl")
SNAP_DIR  = os.path.join(AUDIT_DIR, "rules_versions")

# decisions
APPLIED            = "APPLIED"
REJECTED_LLM       = "REJECTED_NO_CHANGE"      # assistant found no valid change
REJECTED_VALIDATION = "REJECTED_VALIDATION"
REJECTED_IMPACT    = "REJECTED_IMPACT"
LLM_ERROR          = "LLM_ERROR"
RESET              = "RESET"

def new_entry(request):
    now = datetime.now(timezone.utc)
    return {
        "change_id": now.strftime("CHG-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4],
        "timestamp_utc": now.isoformat(timespec="seconds"),
        "request": request,
    }

def snapshot_rules(rules, change_id, tag):
    """Save a full copy of the rules grid; returns the file name."""
    os.makedirs(SNAP_DIR, exist_ok=True)
    name = f"{change_id}_{tag}.csv"
    rules.to_csv(os.path.join(SNAP_DIR, name), index=False)
    return name

def record(entry):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry

def load_log():
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame()
    with open(LOG_FILE, encoding="utf-8") as f:
        return pd.DataFrame([json.loads(l) for l in f if l.strip()])
