"""
engine.py — deterministic NBO logic (Level 1 & 2).
Loads the synthetic rules + subscribers, assigns each subscriber to one segment
(the Next Best Offer), validates a proposed rule change, and simulates its impact.
No LLM here: this is the part the AI must NEVER bypass.
"""
import os, re, shutil
import pandas as pd

HERE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_CSV = os.path.join(HERE, "data", "segment_rules.csv")
BASELINE_CSV = os.path.join(HERE, "data", "segment_rules_baseline.csv")
SUBS_CSV  = os.path.join(HERE, "data", "subscribers.csv")

NUM_COLS   = ["tenure_min","tenure_max","renew_min","renew_max","late_days_min","late_days_max"]
EDITABLE   = NUM_COLS + ["roaming_rule","risk_combos","offer_intensity","is_active"]
INTENSITY  = ["NONE","NORMAL","AGGRESSIVE","VERY_AGGRESSIVE"]
RISK_RE    = re.compile(r"^(\|(POS|FLAT|NEG)-(LOW|MED|HIGH))+\|$")

# ---------------------------------------------------------------- load
def load_rules(path=RULES_CSV):
    df = pd.read_csv(path, dtype=str)
    for c in NUM_COLS:
        df[c] = df[c].astype(int)
    return df

def load_subscribers(path=SUBS_CSV):
    return pd.read_csv(path)

def save_rules(df, path=RULES_CSV):
    # keep the original grid once, so a demo can always be reset
    if path == RULES_CSV and not os.path.exists(BASELINE_CSV):
        shutil.copyfile(RULES_CSV, BASELINE_CSV)
    df.to_csv(path, index=False)

def reset_rules():
    """Restore the original rules grid (undo every applied change)."""
    if os.path.exists(BASELINE_CSV):
        shutil.copyfile(BASELINE_CSV, RULES_CSV)

# ---------------------------------------------------------------- NBO matching
def assign_segments(subs, rules):
    """Return a Series (index = subscriber_id) with the assigned segment,
    or 'UNASSIGNED' / 'MULTIPLE'."""
    active = rules[rules["is_active"] == "Y"]
    s = subs.assign(_k=1)
    r = active.assign(_k=1)
    m = s.merge(r, on="_k").drop(columns="_k")

    cond = (
        (m.tenure_days >= m.tenure_min) & (m.tenure_days < m.tenure_max) &
        (m.renewals_6m >= m.renew_min)  & (m.renewals_6m < m.renew_max)  &
        (m.late_days   >= m.late_days_min) & (m.late_days < m.late_days_max) &
        ((m.roaming_rule == "ANY") | (m.roaming_rule == m.roamer_flag))
    )
    m = m[cond]
    risk_ok = (m.risk_combos == "ANY") | m.apply(
        lambda x: ("|" + str(x.risk_code) + "|") in str(x.risk_combos), axis=1)
    m = m[risk_ok]

    g = m.groupby("subscriber_id")["segment_id"]
    out = g.agg(["count", "first"])
    res = out.apply(lambda x: x["first"] if x["count"] == 1 else "MULTIPLE", axis=1)
    # subscribers with no match
    res = res.reindex(subs["subscriber_id"]).fillna("UNASSIGNED")
    return res

# ---------------------------------------------------------------- validation
def validate_change(rules, change):
    """change = {segment_id, field, new_value}. Returns (ok, [errors])."""
    errs = []
    seg, field, val = change.get("segment_id"), change.get("field"), str(change.get("new_value"))

    if not seg and not field:                   # the assistant declined to propose a change
        return False, [f"No applicable change: {change.get('reason', 'request out of scope')}"]

    if seg not in set(rules.segment_id):
        errs.append(f"Unknown segment_id '{seg}'.")
    if field not in EDITABLE:
        errs.append(f"Field '{field}' is not editable (adding a variable is not allowed).")
        return False, errs                      # stop early: no point checking value

    if field in NUM_COLS:
        if not re.fullmatch(r"-?\d+", val):
            errs.append(f"{field} must be an integer, got '{val}'.")
    elif field == "roaming_rule" and val not in ("ANY","Y","N"):
        errs.append("roaming_rule must be ANY, Y or N.")
    elif field == "is_active" and val not in ("Y","N"):
        errs.append("is_active must be Y or N.")
    elif field == "offer_intensity" and val not in INTENSITY:
        errs.append(f"offer_intensity must be one of {INTENSITY}.")
    elif field == "risk_combos" and val != "ANY" and not RISK_RE.match(val):
        errs.append("risk_combos must be ANY or like |POS-LOW|FLAT-MED|.")

    # a change must actually change something
    if not errs and seg in set(rules.segment_id):
        current = str(rules.loc[rules.segment_id == seg, field].iloc[0])
        if current == val:
            errs.append(f"No-op: {seg} {field} is already '{current}'.")

    # bounds coherence after the change
    if not errs and field in NUM_COLS and seg in set(rules.segment_id):
        row = rules[rules.segment_id == seg].iloc[0].copy()
        row[field] = int(val)
        if row.tenure_min >= row.tenure_max or row.renew_min >= row.renew_max \
           or row.late_days_min >= row.late_days_max:
            errs.append("Change would make a MIN >= MAX bound.")
    return (len(errs) == 0), errs

def apply_change(rules, change):
    df = rules.copy()
    idx = df.index[df.segment_id == change["segment_id"]][0]
    val = change["new_value"]
    if change["field"] in NUM_COLS:
        val = int(val)
    df.at[idx, change["field"]] = val
    return df

# ---------------------------------------------------------------- impact
def simulate_impact(subs, rules_old, rules_new):
    before = assign_segments(subs, rules_old)
    after  = assign_segments(subs, rules_new)
    moved  = (before != after)
    dist   = after.value_counts().rename_axis("segment").reset_index(name="customers")
    migration = (pd.DataFrame({"from": before[moved], "to": after[moved]})
                 .value_counts().rename_axis(["from","to"]).reset_index(name="customers"))
    # offer seen by each customer (a segment can keep its customers but change its offer)
    offer_old = before.map(rules_old.set_index("segment_id")["offer_intensity"]).fillna(before)
    offer_new = after.map(rules_new.set_index("segment_id")["offer_intensity"]).fillna(after)
    return {
        "moved": int(moved.sum()),
        "offer_changed": int((offer_old != offer_new).sum()),
        "total": int(len(subs)),
        "distribution": dist,
        "migration": migration,
        "unassigned": int((after == "UNASSIGNED").sum()),
        "multiple": int((after == "MULTIPLE").sum()),
        "unassigned_before": int((before == "UNASSIGNED").sum()),
        "multiple_before": int((before == "MULTIPLE").sum()),
    }

def check_impact(imp):
    """Impact guardrail: a change must not give a customer two segments
    (two conflicting offers). Returns (ok, [errors]).
    Leaving customers without a segment is allowed (e.g. disabling a segment
    is a business decision); it is reported by impact_warnings instead."""
    errs = []
    new_multiple = imp["multiple"] - imp["multiple_before"]
    if new_multiple > 0:
        errs.append(f"{new_multiple:,} customers would match two segments (conflicting offers).")
    return (len(errs) == 0), errs

def impact_warnings(imp):
    """Non-blocking notices shown to the business before the change is applied."""
    warns = []
    new_unassigned = imp["unassigned"] - imp["unassigned_before"]
    if new_unassigned > 0:
        warns.append(f"{new_unassigned:,} customers will no longer receive any offer "
                     "(no active segment covers them).")
    return warns

def rules_summary(rules):
    """Compact text of the rules for the LLM prompt."""
    cols = ["segment_id","segment_name","offer_intensity","renewal_group",
            "lapse_group","roaming_rule","risk_combos","is_active"]
    return rules[cols].to_csv(index=False)

if __name__ == "__main__":
    r = load_rules(); s = load_subscribers()
    print(assign_segments(s, r).value_counts().head())
