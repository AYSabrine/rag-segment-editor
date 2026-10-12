"""
Synthetic data generator for the RAG Segment Editor (telco NBO segmentation).
100% synthetic and fictional — this grid is designed for the portfolio and does
not reproduce any real operator's segmentation. Produces:
  - segment_rules.csv   : the config-driven rules (what RAG edits)
  - subscribers.csv     : fake subscribers (for impact simulation)

The grid follows the usual NBO logic (tenure → loyalty → lifecycle stage → risk /
roaming refinements → offer intensity) and covers every profile exactly once:
no gaps, no overlaps.
"""
import csv, random, os

random.seed(2026)
HERE = os.path.dirname(__file__)

# ---------------------------------------------------------------------------
# 1) SEGMENT RULES  (fictional NBO grid, prepaid telco)
#    bounds are [min, max)  — min inclusive, max exclusive
#    tenure:  Welcome [0,60) · Onboarding [60,150) · mature 150+
#    renewals (6 months): Champions 6+ · Regulars 4-5 · Occasionals 1-3 · Silent 0
#    days late: Active <4 · Slipping 4-14 · Lapsed 15-45 · Lost 46+
# ---------------------------------------------------------------------------
HEALTHY = "|POS-LOW|POS-MED|FLAT-LOW|"
AT_RISK = "|POS-HIGH|FLAT-MED|FLAT-HIGH|NEG-LOW|NEG-MED|NEG-HIGH|"
RULES = [
  # id    name                    family        stage                 tenure      renewals   days late   roam   risk     offer              active
    ("C01","Welcome Journey",     "WELCOME",    "ANY",                0,    60,   0, 99,  -999, 999, "ANY","ANY",   "NONE",            "Y"),
    ("C02","Onboarding Boost",    "ONBOARDING", "ANY",               60,   150,   0, 99,  -999, 999, "ANY","ANY",   "NORMAL",          "Y"),
    ("C03","Champion Upsell",     "CHAMPION",   "ACTIVE",           150, 99999,   6, 99,  -999,   4, "ANY",HEALTHY, "NORMAL",          "Y"),
    ("C04","Champion Protect",    "CHAMPION",   "ACTIVE",           150, 99999,   6, 99,  -999,   4, "ANY",AT_RISK, "AGGRESSIVE",      "Y"),
    ("C05","Champion Nudge",      "CHAMPION",   "SLIPPING",         150, 99999,   6, 99,     4,  15, "ANY","ANY",   "NORMAL",          "Y"),
    ("C06","Champion Recovery",   "CHAMPION",   "LAPSED_OR_LOST",   150, 99999,   6, 99,    15, 999, "ANY","ANY",   "AGGRESSIVE",      "Y"),
    ("C07","Regular Grow",        "REGULAR",    "ACTIVE",           150, 99999,   4,  6,  -999,   4, "ANY","ANY",   "NORMAL",          "Y"),
    ("C08","Regular Nudge",       "REGULAR",    "SLIPPING",         150, 99999,   4,  6,     4,  15, "ANY","ANY",   "AGGRESSIVE",      "Y"),
    ("C09","Regular Win-back",    "REGULAR",    "LAPSED_OR_LOST",   150, 99999,   4,  6,    15, 999, "N",  "ANY",   "AGGRESSIVE",      "Y"),
    ("C10","Regular Traveller",   "REGULAR",    "LAPSED_OR_LOST",   150, 99999,   4,  6,    15, 999, "Y",  "ANY",   "NONE",            "Y"),
    ("C11","Occasional Activate", "OCCASIONAL", "ACTIVE_OR_SLIPPING",150, 99999,  1,  4,  -999,  15, "ANY","ANY",   "NORMAL",          "Y"),
    ("C12","Occasional Win-back", "OCCASIONAL", "LAPSED_OR_LOST",   150, 99999,   1,  4,    15, 999, "ANY","ANY",   "VERY_AGGRESSIVE", "Y"),
    ("C13","Silent Reactivate",   "SILENT",     "ACTIVE_OR_SLIPPING",150, 99999,  0,  1,  -999,  15, "ANY","ANY",   "AGGRESSIVE",      "Y"),
    ("C14","Silent Last Call",    "SILENT",     "LAPSED_OR_LOST",   150, 99999,   0,  1,    15, 999, "ANY","ANY",   "VERY_AGGRESSIVE", "Y"),
]
RULE_COLS = ["segment_id","segment_name","renewal_group","lapse_group",
             "tenure_min","tenure_max","renew_min","renew_max",
             "late_days_min","late_days_max","roaming_rule","risk_combos",
             "offer_intensity","is_active"]
with open(os.path.join(HERE,"segment_rules.csv"),"w",newline="") as f:
    w=csv.writer(f); w.writerow(RULE_COLS); w.writerows(RULES)

# ---------------------------------------------------------------------------
# 2) SUBSCRIBERS  — generated to land inside the grid (realistic coverage)
# ---------------------------------------------------------------------------
N = 6000
slopes = ["POS","FLAT","NEG"]; churns = ["LOW","MED","HIGH"]
rows = []
for i in range(N):
    bucket = random.choices(["welcome","onboarding","mature"], weights=[0.07,0.11,0.82])[0]
    if bucket == "welcome":
        tenure = random.randint(0,59);    renew = random.randint(0,1)
    elif bucket == "onboarding":
        tenure = random.randint(60,149);  renew = random.randint(0,4)
    else:
        tenure = random.randint(150,3600)
        renew  = random.choices(range(10),
                 weights=[0.14,0.07,0.09,0.10,0.12,0.12,0.11,0.10,0.08,0.07])[0]
    late = random.choices([random.randint(-30,3), random.randint(4,14),
                           random.randint(15,45), random.randint(46,150)],
                          weights=[0.52,0.18,0.17,0.13])[0]
    roamer = random.choices(["Y","N"], weights=[0.08,0.92])[0]
    risk   = f"{random.choice(slopes)}-{random.choice(churns)}"
    rows.append([f"SUB{i:06d}", tenure, renew, late, roamer, risk])

with open(os.path.join(HERE,"subscribers.csv"),"w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["subscriber_id","tenure_days","renewals_6m","late_days","roamer_flag","risk_code"])
    w.writerows(rows)

print(f"segment_rules.csv : {len(RULES)} rules")
print(f"subscribers.csv   : {N} subscribers")
