"""
main.py — Streamlit interface for the RAG Segment Editor.
Flow: natural-language request -> RAG proposes a change -> validate -> simulate
impact -> (if valid) apply automatically. The AI never edits the data directly.
Every request, applied or rejected, is written to the audit log (rag/audit.py).
Run:  streamlit run app/main.py
"""
import os, sys
import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rag"))
from engine import (load_rules, load_subscribers, save_rules, reset_rules, validate_change,
                    apply_change, simulate_impact, check_impact, impact_warnings,
                    assign_segments)
from settings import load_env
import audit

load_env()

st.set_page_config(page_title="RAG Segment Editor", page_icon="🎯", layout="wide")
st.title("🎯 NBO Segment Editor — RAG")
st.caption("Edit the segmentation rules in plain English. "
           "The assistant retrieves the current rules, proposes a change, "
           "validates it and simulates its impact — then applies it automatically if valid. "
           "Synthetic data only.")

rules = load_rules()
subs  = load_subscribers()

def show_audit_trail():
    st.markdown("---")
    st.subheader("📜 Audit trail")
    log = audit.load_log()
    if log.empty:
        st.caption("No change requested yet.")
        return
    cols = [c for c in ["change_id", "timestamp_utc", "request", "segment_id", "field",
                        "old_value", "new_value", "decision", "reasons", "offer_changed"]
            if c in log.columns]
    if "offer_changed" in log.columns:
        log["offer_changed"] = log["offer_changed"].astype("Int64")
    view = log[cols].iloc[::-1].astype(object)
    st.dataframe(view.where(view.notna(), "").astype(str), hide_index=True, height=280)
    st.caption(f"Full log: data/audit/change_log.jsonl · rule versions: data/audit/rules_versions/")

def finish(entry):
    """Record the decision, show the audit trail, end this run."""
    audit.record(entry)
    show_audit_trail()
    st.stop()

with st.expander("📊 Segments & data — how the NBO engine assigns each customer", expanded=False):
    seg = assign_segments(subs, rules)
    by_seg = (seg.value_counts().rename_axis("segment_id").reset_index(name="customers")
              .merge(rules[["segment_id", "segment_name", "offer_intensity"]], how="left")
              .sort_values("segment_id"))
    by_seg["share"] = (by_seg.customers / len(subs) * 100).round(1).astype(str) + " %"
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Subscribers", f"{len(subs):,}")
    k2.metric("Active segments", int((rules.is_active == "Y").sum()))
    k3.metric("Without a segment", int((seg == "UNASSIGNED").sum()))
    k4.metric("In two segments", int((seg == "MULTIPLE").sum()))

    st.markdown("**Rule grid** — one row per segment (min inclusive, max exclusive)")
    st.dataframe(rules, hide_index=True)
    d1, d2 = st.columns([3, 2])
    with d1:
        st.markdown("**Customers per segment**")
        st.bar_chart(by_seg.set_index("segment_id")["customers"])
        st.dataframe(by_seg[["segment_id", "segment_name", "offer_intensity", "customers", "share"]],
                     hide_index=True)
    with d2:
        st.markdown("**Customers per offer intensity**")
        st.dataframe(by_seg.groupby("offer_intensity", dropna=False)["customers"].sum()
                     .reindex(["NONE", "NORMAL", "AGGRESSIVE", "VERY_AGGRESSIVE"]).dropna()
                     .astype(int).rename_axis("offer_intensity").reset_index())
        st.markdown("**Sample subscribers → assigned segment (the Next Best Offer)**")
        sample = subs.head(12).assign(segment_id=seg.reindex(subs.subscriber_id.head(12)).values)
        sample = sample.merge(rules[["segment_id", "segment_name", "offer_intensity"]], how="left")
        st.dataframe(sample, hide_index=True)

col1, col2 = st.columns([1, 1])
with col1:
    st.subheader("Current rules")
    st.dataframe(rules[["segment_id","segment_name","offer_intensity","is_active"]],
                 hide_index=True, height=565)

with col2:
    st.subheader("Ask for a change")
    req = st.text_input("e.g. make the Regular Nudge segment more aggressive")
    go  = st.button("Propose & simulate", type="primary")
    if st.button("Reset rules to original"):
        entry = audit.new_entry("reset rules to original")
        entry["rules_before"] = audit.snapshot_rules(rules, entry["change_id"], "before")
        reset_rules()
        entry.update(decision=audit.RESET,
                     rules_after=audit.snapshot_rules(load_rules(), entry["change_id"], "after"))
        audit.record(entry)
        st.rerun()

if go and req:
    entry = audit.new_entry(req)
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Set OPENAI_API_KEY to use the RAG assistant.")
        st.stop()
    try:
        from chain import propose_change
        with st.spinner("Retrieving context and proposing a change..."):
            change = propose_change(req)
    except Exception as e:
        st.error(f"LLM error: {e}")
        finish({**entry, "decision": audit.LLM_ERROR, "reasons": str(e)})

    entry.update(proposal=change, retrieved=change.get("retrieved"),
                 segment_id=change.get("segment_id"), field=change.get("field"),
                 new_value=change.get("new_value"), llm_reason=change.get("reason"))

    st.markdown("### Proposed change")
    st.caption(f"Change ID: {entry['change_id']}")
    st.json(change)

    ok, errs = validate_change(rules, change)
    if not ok:
        st.error("❌ Change rejected — not applied:")
        for e in errs:
            st.write(f"- {e}")
        declined = not change.get("segment_id") and not change.get("field")
        finish({**entry, "decision": audit.REJECTED_LLM if declined else audit.REJECTED_VALIDATION,
                "reasons": " | ".join(errs)})

    old_value = rules.loc[rules.segment_id == change["segment_id"], change["field"]].iloc[0]
    entry["old_value"] = old_value
    st.success(f"✅ Validation passed — {change['segment_id']} · {change['field']}: "
               f"{old_value} → {change['new_value']}")

    new_rules = apply_change(rules, change)
    imp = simulate_impact(subs, rules, new_rules)
    entry.update({k: imp[k] for k in ["offer_changed", "moved", "unassigned", "multiple",
                                      "unassigned_before", "multiple_before"]},
                 migration=imp["migration"].to_dict("records"))

    st.markdown("### Impact simulation")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers whose offer changes", f"{imp['offer_changed']:,}")
    c2.metric("Customers moved segment", f"{imp['moved']:,}")
    c3.metric("Without a segment", f"{imp['unassigned']:,}",
              delta=imp["unassigned"] - imp["unassigned_before"], delta_color="inverse")
    c4.metric("In two segments", f"{imp['multiple']:,}",
              delta=imp["multiple"] - imp["multiple_before"], delta_color="inverse")

    st.markdown("**Migration (who moves, from → to)**")
    st.dataframe(imp["migration"], height=220)

    st.caption("Reason given by the assistant: " + str(change.get("reason", "")))

    ok, errs = check_impact(imp)
    if not ok:
        st.error("❌ Change rejected by the impact check — not applied:")
        for e in errs:
            st.write(f"- {e}")
        finish({**entry, "decision": audit.REJECTED_IMPACT, "reasons": " | ".join(errs)})

    warns = impact_warnings(imp)
    for w in warns:
        st.warning("⚠️ " + w)

    # automatic apply once validated and impact-checked (no manual promotion in this demo)
    entry["rules_before"] = audit.snapshot_rules(rules, entry["change_id"], "before")
    save_rules(new_rules)
    entry["rules_after"] = audit.snapshot_rules(new_rules, entry["change_id"], "after")
    st.success("✅ Change validated, impact-checked and applied automatically. "
               f"{imp['offer_changed']:,} customers affected.")
    finish({**entry, "decision": audit.APPLIED, "reasons": " | ".join(warns)})

show_audit_trail()
