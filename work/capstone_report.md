# Capstone Report — Refresh / Content Opportunity Scoring

- **Author:** Vignesh Kumar U
- **Lane:** Refresh / Content Opportunity Scoring (which existing content to review/refresh first)
- **Repo:** https://github.com/viki22uied/ML
- **Date:** 2026-09-28

## 0. Abstract

Which of thousands of existing content pages should an editor review first? This project builds
a decline-risk / refresh-priority score for individual content items, using FlyRank's 30,000-row
anonymized starter dataset (32 clients) plus, for the earlier modeling stage, a `month=2026-03`
cut of the gated warehouse release. A five-feature Random Forest, evaluated on a client-grouped
holdout (so no client's pages leak between train and test), separated review-worthy pages from
healthy ones clearly better than a transparent hand-written baseline rule (warehouse-stage run:
AUC 0.846 vs. 0.684; starter-dataset reference pipeline: AUC 0.750 vs. 0.627 baseline). The
output is a ranked, reason-coded action queue — decision-support for a human reviewer's
prioritization, not an automated publishing or ranking-prediction system.

## 1. Problem framing

**Unit of analysis:** one content item (page). **Output:** a decline-risk / refresh-priority
score (0–1) plus a small set of human-readable reason codes (e.g. `stale_visible_page`,
`low_ctr_visible_page`, `declining_with_demand`). **Action a human takes:** an editor reads the
top of the ranked queue during a review cycle and decides whether to refresh, expand, or leave a
page alone — the model never edits or publishes anything itself. **Cost of a wrong call:** a false
positive wastes editorial time reviewing a page that was actually fine; a false negative lets a
genuinely declining, still-visible page keep losing traffic un-reviewed. Both costs are bounded
and recoverable (nobody loses money or safety from a mis-ranked page), which is why a
precision-at-top-K framing — "is the top of the queue worth a look" — fits better than a
strict accuracy target. ML helps here because the portfolio is too large (30,000+ pages) for
manual triage, and a handful of simple, transparent signals (impressions, position, age,
freshness) turn out to carry real, measurable signal about which pages are worth a look first.

## 2. Data safety

**Data used:** `data/raw/content_refresh_anonymized.csv` (30,000 pseudonymized content items, 32
clients, trailing-90-day metrics) for the reference-pipeline stage (baseline, w06, w07 in this
report); a `month=2026-03` cut of the gated Hugging Face warehouse release
(`hf://datasets/FlyRank/internship-warehouse`) for the earlier w04/w05 modeling stage. Both are
pseudonymized at the client/content level — no client names, URLs, or raw queries appear
anywhere in `work/`.

**Deliberately excluded:** `trend_direction` and `trend_pct` are never features — the reference
pipeline's label (`is_declining_label`) is derived directly from `trend_direction`, so including
either would leak the answer into the inputs (confirmed clean in `work/notebooks/w06_validation_audit.ipynb`,
section 3). `client_id` / `content_id` are used only to group the train/test split, never as
model features. `ctr_march` / `clk_march` were excluded from the ML-08 warehouse-stage model for
the same reason: they are the label's own inputs (`needs_review_label` is a percentile of
`ctr_march`).

**Confirmed:** no client-identifying details appear anywhere in `work/` — every reference is to
`client_id`/`content_id` hashes.

## 3. Baseline

Two transparent, rule-based baselines were built and beaten fairly (same data, same split, same
metric as the model in each case):

- **Reference-pipeline baseline** (`scripts/02_baseline_score.py`): a weighted score
  (`0.40*visibility + 0.30*freshness_risk + 0.25*position_opportunity + 0.05*depth_gap`), all
  built from raw, pre-computed metrics — no model. On the client-holdout split: **ROC AUC 0.627,
  Precision@50 0.240**.
- **ML-07 baseline rule** (warehouse stage): `imp_march × ctr_gap × stale_boost` — ranks by
  estimated extra clicks if a page were fixed. On the same client-grouped holdout used for the
  model: **ROC AUC 0.684, Precision@50 0.08**.

Both are fair comparisons: same rows, same split, same metric as the model that follows.

## 4. Model / analysis

**Warehouse stage (ML-08, `work/notebooks/w05_model.ipynb`):** Random Forest (200 trees, max
depth 8), compared against Logistic Regression and a depth-4 Decision Tree. Label
`needs_review_label = 1` if `ctr_march` is at or below the bottom-30th-percentile CTR for March
(base rate 43.1%). Features: `imp_march`, `avg_pos_march`, `content_age_days`, `search_volume`,
`keyword_token_count` — five features, all knowable at the March 31 decision moment.

**Reference-pipeline stage (this report's w06/w07 work):** the same Random Forest family
(`scripts/03_train_model.py`: 200 trees, max depth 10, `class_weight="balanced_subsample"`),
label `is_declining_label = (trend_direction == "down")` (base rate 54.2%), 18 numeric + 8
categorical features (impressions, clicks, sessions, position, CTR, age, freshness, word/char
count, engagement, scroll rate, AI traffic share — see `scripts/ml_utils.py` for the exact list).
`trend_direction`/`trend_pct` excluded as described in section 2.

## 5. Evaluation

**Split:** client-grouped in both stages (`GroupShuffleSplit` / a client-holdout split on
`client_id`) — content items from the same client can share hidden site-level character
(templates, niche, baseline traffic), so a plain random split lets the model memorize a client
instead of learning the general signal. `work/notebooks/w06_validation_audit.ipynb` makes this
concrete on the starter dataset: a naive random 75/25 split (no grouping, 31 clients leaking
across train/test) scored **AUC 0.760, Precision@50 0.92** — a naive-split random forest on the
same features and same label. The honest client-grouped split (zero client overlap) on the same
data scored **AUC 0.606, Precision@50 0.56**. The gap (0.15 AUC, 0.36 Precision@50) is itself the
finding: roughly a third of the naive split's apparent precision was the model recognizing
clients it had already seen, not real discrimination.

| Stage | Split | Model | AUC | AP | P@50 | P@200 |
|---|---|---|---:|---:|---:|---:|
| Warehouse (ML-08) | client-grouped | Random Forest | 0.846 | 0.787 | 0.98 | 0.965 |
| Warehouse (ML-08) | client-grouped | baseline rule | 0.684 | — | 0.08 | — |
| Starter dataset (reference pipeline) | client-holdout | Random Forest | 0.750 | 0.618 | 0.740 | — |
| Starter dataset (reference pipeline) | client-holdout | baseline rule | 0.627 | 0.468 | 0.240 | — |
| Starter dataset (w06, before/after demo) | random (naive) | Random Forest | 0.760 | 0.772 | 0.920 | 0.895 |
| Starter dataset (w06, before/after demo) | client-grouped (honest) | Random Forest | 0.606 | 0.594 | 0.560 | 0.620 |

**Errors:** on the warehouse-stage model, the baseline rule scores low on Precision@50 despite a
respectable 0.684 AUC because it ranks by *estimated extra clicks if fixed* (volume-weighted),
while the label asks a narrower question (worst-30%-CTR tier, independent of volume) —
`imp_march` and the label are negatively correlated (-0.27) in that test slice, so the two
methods answer different, both-legitimate questions. Full false-positive/false-negative case
review is in `work/notebooks/w05_model.ipynb`, section 4.

## 6. Interpretation

**Warehouse-stage model:** `imp_march` dominates feature importance (0.793) — directionally
sensible (lower-CTR-tier pages in this slice differ in impression volume from the top of the
distribution) but a single feature carrying 79% of importance is flagged in `w05_model.ipynb` as
a disclosed limitation, not a hidden one — the model is close to learning one strong feature more
than five features jointly.

**Reference-pipeline model:** importance is spread more evenly — `days_with_impressions` (0.158),
`log_impressions_90d` (0.129), `avg_position` (0.109), `content_age_days` (0.095) lead, with no
single feature over 0.16 (`outputs/model_results.json`), which per the leakage skill's own
heuristic ("suspiciously perfect = probably leakage") is a healthier pattern than the
warehouse-stage model's concentration.

**Negative result worth naming:** the honest client-grouped split on the starter dataset (AUC
0.606) is barely better than a coin flip at ranking content correctly across *unseen clients* —
weaker than either the warehouse-stage model or the reference-pipeline's own client-holdout run
(0.750). The gap between 0.750 (reference pipeline holdout) and 0.606 (this report's independent
re-run with a different random group assignment) shows real split-to-split variance on a
32-client dataset — a caution against treating any single holdout number as precise, and a
reason to prefer averaging across several group splits in a follow-up.

## 7. Recommendation

The ranked, reason-coded action queue (`work/notebooks/w07_action_playbook.ipynb`) supports a
weekly/monthly editorial triage workflow: a reviewer reads from the top of the queue down,
checks the attached reason codes (e.g. `declining_with_demand`, `low_ctr_visible_page`) against
the live page, and decides whether to refresh, expand, or skip. In the top-50 of the reference-
pipeline queue, the declining-label rate is well above the portfolio base rate (lift confirmed in
`w07_action_playbook.ipynb`, section 1) — the queue meaningfully concentrates review-worthy pages
near the top, which is what a triage tool needs to do. **Confidence:** moderate, and
scoped — this is decision-support for prioritization, not a guarantee that refreshing a flagged
page will recover traffic (see the w06 methodology questions on the paper's own refresh-lift
claims), not a client-specific tuned model, and not validated outside the two builds analyzed
here. A human review step and a no-go list for regulated/sensitive content are mandatory before
any action (`w07_action_playbook.ipynb`, section 3).

## 8. Reproducibility

**Random seed:** 42, fixed everywhere (`RANDOM_SEED` / `RANDOM_STATE` in every script and
notebook). **Fresh-clone commands (starter-dataset stage — no gated access needed):**

```bash
pip install -r requirements.txt
python scripts/run_all.py                      # reference pipeline: baseline, model, report, PDF
jupyter nbconvert --to notebook --execute --inplace work/notebooks/w06_validation_audit.ipynb
jupyter nbconvert --to notebook --execute --inplace work/notebooks/w07_action_playbook.ipynb
```

**Warehouse-stage commands** (`work/notebooks/w04_baseline_score.ipynb`, `w05_model.ipynb`)
require an approved Hugging Face token (`HF_TOKEN`) for `hf://datasets/FlyRank/internship-warehouse`
(gated, instant approval per `SETUP.md`) — not needed to reproduce sections 5–7 of this report,
which run entirely on the always-available starter CSV. The receipts for the honest-split claim
in section 5 are committed at `work/outputs/w06_split_comparison.json`; the action-queue lift
claim's receipt is `work/outputs/w07_monitoring_snapshot.json` and the code cell that produces it
in `w07_action_playbook.ipynb` itself (re-run top to bottom to reproduce).

**Environment:** `requirements.txt` — pandas, numpy, scikit-learn, matplotlib, reportlab, duckdb,
huggingface_hub.

## 9. Acknowledgments & data credit

Built on the FlyRank ML Internship dataset — [flyrank.ai](https://flyrank.ai).
