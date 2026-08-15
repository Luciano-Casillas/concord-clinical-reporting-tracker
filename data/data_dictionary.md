# Data Dictionary -- Concord Clinical Network Reporting & QA Tracker

## `data/concord_clinical_network.csv` (351,225 rows)

Grain: one row per (pharma client campaign) x (physician specialty x region
segment) x (reporting week). This is the table `app.py`, the SQL analysis
file, and the escalation-risk model all read.

| Column | Type | Description | Business meaning |
|---|---|---|---|
| report_id | string | Unique report-row identifier | Primary key. ~0.35% of rows share a business key with another row (`campaign_id` + `physician_specialty` + `region` + `report_week`) -- an intentional duplicate-feed defect, see Business Question 1 |
| campaign_id | string | Campaign identifier | |
| client_name | categorical | Fictional pharma client reported through Concord Clinical Network | |
| therapeutic_area | categorical | Oncology, Cardiology, Immunology, Endocrinology, Neurology | **Escalation-risk feature** |
| campaign_format | categorical | Sponsored Content, Native Display, Video, Email | **Escalation-risk feature** |
| physician_specialty | categorical | Targeted HCP specialty for this segment | **Escalation-risk feature** |
| region | categorical | Northeast, Southeast, Midwest, Southwest, West | **Escalation-risk feature** |
| report_week | date | Monday of the reporting week | |
| weeks_since_launch | integer | Week index within the campaign (1 = launch week) | **Escalation-risk feature** |
| campaign_length_weeks | integer | Contracted campaign duration | **Escalation-risk feature** |
| impressions | integer | Delivered impressions this segment-week | |
| clicks | integer | Clicks on delivered creative | |
| ctr_pct | float | `clicks / impressions * 100` | Derived, dashboard display only |
| content_engagements | integer | Clicks that engaged with landing content | |
| avg_time_on_content_seconds | float | Average engaged time on content | ~4% null -- simulated incomplete telemetry, drives `missing_data_flag` |
| specialty_verified_reach | integer | Engaged HCPs with verified specialty match | Funnel step: impression -> click -> content engagement -> specialty-verified reach -> follow-up action |
| follow_up_actions | integer | Verified HCPs completing a follow-up action | Final funnel step |
| contracted_impressions | integer | Weekly impression delivery target | Dashboard only -- not a model feature |
| cpm_usd | float | Contracted cost per thousand impressions, by format | Dashboard only -- not a model feature |
| contracted_deliverable_value_usd | float | `contracted_impressions * cpm_usd / 1000` | Dashboard only -- not a model feature |
| actual_deliverable_value_usd | float | `impressions * cpm_usd / 1000` | Dashboard only -- not a model feature |
| pacing_pct | float | `actual_deliverable_value_usd / contracted_deliverable_value_usd * 100` | **Escalation-risk feature** |
| attributed_roi | float | `follow_up_actions * value_per_followup(therapeutic_area) / actual_deliverable_value_usd` | Dashboard only -- illustrative attribution, not a model feature |
| reported_metric_variance_pct | float | Week-over-week % change in `actual_deliverable_value_usd` within the same segment; 0 on a segment's first reporting week | **Escalation-risk feature**. QA input |
| missing_data_flag | boolean | 1 = `avg_time_on_content_seconds` is null this row | **Escalation-risk feature**. QA input |
| pacing_deviation_flag | boolean | 1 = `pacing_pct` outside the 80-120% tolerance band | **Escalation-risk feature**. QA input |
| qa_risk_score | float (0-100) | **Rule-based**, same-week QA risk score -- see formula below | **Escalation-risk feature.** The auditable, explainable checkpoint |
| qa_risk_tier | categorical | Low (<40) / Medium (40-70) / High (>70), derived from `qa_risk_score` | Display only -- redundant with `qa_risk_score`, never a separate model feature |
| flagged_for_qa_escalation | integer (0/1) | **Primary model target.** 1 = this report required QA correction/escalation | JD-authentic target -- not a churn/propensity proxy |
| escalation_risk_score | float (0-1) | Model-predicted probability of `flagged_for_qa_escalation` | Model output -- see Model Notes below |
| escalation_risk_decile | integer (1-10) | Decile rank of `escalation_risk_score` (1 = highest risk) | Model output |

## Rule-based QA risk score (NOT a trained model)

```
qa_risk_score = clip(
    0.35 * min(abs(reported_metric_variance_pct), 100)
  + 30   * missing_data_flag
  + 25   * pacing_deviation_flag
  + noise,
  0, 100
)
```

This score is deterministic and fully explainable from the same-week fields
that produced it -- a reporting analyst can walk a client through exactly why
a report scored the way it did, with no model in the loop. It is the primary
QA checkpoint the dashboard's Overview and Escalation Queue tabs are built
around.

## Escalation-risk model (LogisticRegression) -- what it is and is not

A small model is trained on top of the rule-based score, **not as a
replacement for it**. Its only job is to help prioritize a long escalation
queue on a busy day, by combining `qa_risk_score` with categorical/behavioral
context the rule alone doesn't weigh (which client, which format, how far
into the campaign). It never overrides the rule and is never shown to a
client -- it is an internal triage aid.

- **Features:** `client_name`, `therapeutic_area`, `campaign_format`,
  `physician_specialty`, `region`, `weeks_since_launch`,
  `campaign_length_weeks`, `pacing_pct`, `reported_metric_variance_pct`,
  `missing_data_flag`, `pacing_deviation_flag`, `qa_risk_score`.
- **Target:** `flagged_for_qa_escalation`.
- **Never used as a feature:** `report_id` / `campaign_id` (identifiers),
  `qa_risk_tier` (redundant with `qa_risk_score`), `escalation_risk_score` /
  `escalation_risk_decile` (model outputs, never fed back in).
- **Deliberate, documented overlap -- not accidental leakage:** `qa_risk_score`
  and its three inputs (`reported_metric_variance_pct`, `missing_data_flag`,
  `pacing_deviation_flag`) are intentionally included as model features. The
  model is designed to sit *on top of* the rule, so reusing the rule's own
  inputs is the point, not a data-leakage bug. See `scripts/01_generate_data.py`
  for the exact target-generation logic (a logistic function of `qa_risk_score`
  plus independent random noise, so the target is not a deterministic
  threshold of the score -- there is genuine signal left for the model to add).
- **Metrics:** see `data/metadata.json` for the current run's test AUC,
  decile-1 lift, and confusion matrix. Verify every hardcoded number in the
  dashboard/README against this file -- never estimate and hardcode.

## Financial columns -- dashboard-only vs. model-training-input

All financial columns (`contracted_impressions`, `cpm_usd`,
`contracted_deliverable_value_usd`, `actual_deliverable_value_usd`,
`attributed_roi`) are dashboard-display fields only. The single exception is
`pacing_pct`, which is also an escalation-risk model feature (listed above).
`attributed_roi` uses an illustrative, per-therapeutic-area dollar value per
follow-up action -- documented as illustrative, not a claimed real-world
pharma valuation.
