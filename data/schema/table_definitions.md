# Source Table Definitions

The analysis-ready file (`data/concord_clinical_network.csv`) is a flattened,
one-row-per-(campaign-segment)-per-(reporting-week) extract. In a real
deployment this would not exist as a single flat file -- it would be
assembled from separate source systems a Reporting Partnerships analyst
typically has to join: a client/contract system, an ad-serving delivery log,
and a QA review system. This document specifies the grain and join logic
that would produce `concord_clinical_network.csv` from those source tables,
matching how this role actually pulls reporting in production.

## Source Tables

### `clients`
**Grain:** one row per pharma client
**System of record:** Client/contract management system

| Column | Type | Description |
|---|---|---|
| client_id | string (PK) | Unique client identifier |
| client_name | string | Fictional pharma client reported through Concord Clinical Network |
| primary_therapeutic_area | string | Client's primary therapeutic focus |

### `campaigns`
**Grain:** one row per campaign
**System of record:** Client/contract management system

| Column | Type | Description |
|---|---|---|
| campaign_id | string (PK) | Unique campaign identifier |
| client_id | string (FK -> `clients.client_id`) | Client running the campaign |
| therapeutic_area | string | Therapeutic area for this campaign |
| campaign_format | string | Sponsored Content, Native Display, Video, Email |
| launch_date | date | Campaign start date |
| campaign_length_weeks | integer | Contracted campaign duration |

### `contract_terms`
**Grain:** one row per campaign
**System of record:** Client/contract management system

| Column | Type | Description |
|---|---|---|
| campaign_id | string (FK -> `campaigns.campaign_id`) | Campaign this contract covers |
| cpm_usd | float | Contracted cost per thousand impressions, by format |
| contracted_impressions_weekly | integer | Weekly impression delivery target |

### `campaign_segments`
**Grain:** one row per (campaign x physician specialty x region) target
**System of record:** Ad-serving / targeting platform

| Column | Type | Description |
|---|---|---|
| segment_id | string (PK) | Unique segment identifier |
| campaign_id | string (FK -> `campaigns.campaign_id`) | Parent campaign |
| physician_specialty | string | Targeted HCP specialty |
| region | string | Targeted US region |

### `delivery_log`
**Grain:** one row per segment per reporting week
**System of record:** Ad-serving delivery log

| Column | Type | Description |
|---|---|---|
| report_id | string (PK) | Unique report-row identifier |
| segment_id | string (FK -> `campaign_segments.segment_id`) | Segment this report covers |
| report_week | date | Reporting week (Monday) |
| weeks_since_launch | integer | Campaign week index |
| impressions | integer | Delivered impressions |
| clicks | integer | Clicks on delivered creative |
| content_engagements | integer | Clicks that engaged with landing content |
| avg_time_on_content_seconds | float | Average engaged time on content; nullable (incomplete telemetry) |
| specialty_verified_reach | integer | Engaged HCPs with verified specialty match |
| follow_up_actions | integer | Verified HCPs completing a follow-up action |

### `qa_review`
**Grain:** one row per `delivery_log` report
**System of record:** Internal QA review system

| Column | Type | Description |
|---|---|---|
| report_id | string (FK -> `delivery_log.report_id`) | Report being reviewed |
| qa_risk_score | float (0-100) | Rule-based, same-week QA risk score |
| qa_risk_tier | string | Low / Medium / High, derived from `qa_risk_score` |
| missing_data_flag | boolean | 1 = a required telemetry field was null |
| pacing_deviation_flag | boolean | 1 = pacing outside the 80-120% tolerance band |
| flagged_for_qa_escalation | integer (0/1) | Report required QA correction/escalation this cycle |
| escalation_risk_score | float (0-1) | LogisticRegression-predicted probability of escalation, used to prioritize a long queue |
| escalation_risk_decile | integer (1-10) | Decile rank of `escalation_risk_score` (1 = highest risk) |

## Join Logic to Produce `concord_clinical_network.csv`

```sql
SELECT
    d.report_id, cmp.campaign_id, cl.client_name, cmp.therapeutic_area, cmp.campaign_format,
    cs.physician_specialty, cs.region, d.report_week, d.weeks_since_launch, cmp.campaign_length_weeks,
    d.impressions, d.clicks, d.content_engagements, d.avg_time_on_content_seconds,
    d.specialty_verified_reach, d.follow_up_actions,
    ct.contracted_impressions_weekly AS contracted_impressions, ct.cpm_usd,
    q.qa_risk_score, q.qa_risk_tier, q.missing_data_flag, q.pacing_deviation_flag,
    q.flagged_for_qa_escalation, q.escalation_risk_score, q.escalation_risk_decile
FROM delivery_log d
JOIN campaign_segments cs ON d.segment_id = cs.segment_id
JOIN campaigns cmp         ON cs.campaign_id = cmp.campaign_id
JOIN clients cl             ON cmp.client_id = cl.client_id
JOIN contract_terms ct      ON ct.campaign_id = cmp.campaign_id
LEFT JOIN qa_review q       ON q.report_id = d.report_id;
```

`ctr_pct`, `contracted_deliverable_value_usd`, `actual_deliverable_value_usd`,
`pacing_pct`, `attributed_roi`, and `reported_metric_variance_pct` (present in
the analysis-ready file) are derived columns computed from the fields above
rather than stored directly in a source table -- see `data/data_dictionary.md`
for their exact formulas and for leakage notes on the escalation-risk model.
