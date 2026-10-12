# Segmentation Variables — Knowledge Base
_This document is indexed by the RAG system. It describes every variable the
segmentation rules use, so the assistant can translate natural-language requests
into correct rule changes. All bands are fictional (portfolio grid)._

## Tenure (tenure_days / tenure_min, tenure_max)
Days since line activation. Bands: 0-59 = Welcome, 60-149 = Onboarding,
150+ = mature customers, segmented by loyalty and lifecycle stage.

## Renewals (renewals_6m / renew_min, renew_max)
Number of main-bundle renewals in the last 180 days = the loyalty family.
Families: 6+ = Champion, 4-5 = Regular, 1-3 = Occasional, 0 = Silent.

## Lifecycle stage (late_days / late_days_min, late_days_max)
Days late = days since last bundle minus its validity.
Stages: below 4 = Active, 4-14 = Slipping, 15-45 = Lapsed, 46+ = Lost.

## Roaming (roaming_rule)
ANY = roaming ignored. N = segment excludes recent roamers. Y = only roamers.
Example: lapsed Regulars who are roaming are probably travelling, not churning
(segment Regular Traveller, no aggressive offer).

## Risk (risk_combos)
Combination of spending slope (POS/FLAT/NEG) and churn band (LOW/MED/HIGH).
Format: pipe-delimited list, e.g. |POS-LOW|FLAT-MED| , or ANY for no risk filter.
Active Champions are split by risk: healthy profiles (Champion Upsell) vs
at-risk profiles (Champion Protect).

## Offer intensity (offer_intensity)
How aggressive the offer is: NONE < NORMAL < AGGRESSIVE < VERY_AGGRESSIVE.
"Make a segment more aggressive" = move offer_intensity one level up.

## is_active
Y = segment live. N = segment disabled (its customers become unassigned).
To remove a segment, set is_active = N (never delete).

## Editing guidance
- "more aggressive" -> raise offer_intensity one level.
- "widen / extend a band" -> change the min/max bounds of that variable.
- "target high churn" -> add NEG-HIGH / FLAT-HIGH / POS-HIGH to risk_combos.
- "disable / remove a segment" -> set is_active = N.
