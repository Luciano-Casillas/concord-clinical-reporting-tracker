-- ================================================================
-- Concord Clinical Network -- Reporting & QA Tracker
-- SQL Analysis File
-- Author: Luciano Casillas
-- Table: concord_clinical_network (grain: one row per campaign segment
--        per reporting week)
-- Dialect: standard ANSI SQL, compatible with PostgreSQL and BigQuery
-- ================================================================


-- ============================================================
-- Section 1: Data Quality and Overview
-- ============================================================

-- 1.1 Row count and escalation-rate baseline
-- Why it matters: confirms table load completeness and establishes the
-- baseline QA-escalation rate every other query and the dashboard compare
-- against -- the first number pulled at the start of any reporting cycle.
SELECT
    COUNT(*) AS total_reports,
    COUNT(DISTINCT campaign_id) AS total_campaigns,
    COUNT(DISTINCT client_name) AS total_clients,
    SUM(flagged_for_qa_escalation) AS total_escalations,
    ROUND(1.0 * SUM(flagged_for_qa_escalation) / COUNT(*), 4) AS escalation_rate,
    ROUND(AVG(qa_risk_score), 2) AS avg_qa_risk_score
FROM concord_clinical_network;

-- 1.2 Null / missing value check across key operational columns
-- Why it matters: reporting packages break silently on unexpected nulls --
-- this is the first check run before any client-facing package goes out.
SELECT
    SUM(CASE WHEN avg_time_on_content_seconds IS NULL THEN 1 ELSE 0 END) AS null_time_on_content,
    SUM(CASE WHEN impressions IS NULL THEN 1 ELSE 0 END) AS null_impressions,
    SUM(CASE WHEN pacing_pct IS NULL THEN 1 ELSE 0 END) AS null_pacing_pct,
    SUM(CASE WHEN client_name IS NULL THEN 1 ELSE 0 END) AS null_client_name,
    ROUND(100.0 * SUM(CASE WHEN avg_time_on_content_seconds IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
        AS pct_missing_telemetry
FROM concord_clinical_network;

-- 1.3 Duplicate report-row detection
-- Why it matters: this is the exact defect a double-loaded ad-serving feed
-- produces -- the same campaign/specialty/region/week reported twice. Left
-- uncaught, it double-counts impressions and inflates every downstream KPI.
SELECT
    campaign_id,
    physician_specialty,
    region,
    report_week,
    COUNT(*) AS row_count,
    SUM(impressions) AS combined_impressions
FROM concord_clinical_network
GROUP BY campaign_id, physician_specialty, region, report_week
HAVING COUNT(*) > 1
ORDER BY combined_impressions DESC;

-- 1.4 Week-over-week reconciliation: reported vs. recomputed deliverable value
-- Why it matters: recomputes actual_deliverable_value_usd from its source
-- fields (impressions x CPM) and flags any row where the stored value
-- doesn't reconcile within a cent -- the same checkpoint that catches a
-- broken upstream calculation before a client sees the number.
SELECT
    report_id,
    campaign_id,
    actual_deliverable_value_usd AS reported_value,
    ROUND(impressions * cpm_usd / 1000.0, 2) AS recomputed_value,
    ROUND(actual_deliverable_value_usd - (impressions * cpm_usd / 1000.0), 2) AS variance_usd
FROM concord_clinical_network
WHERE ABS(actual_deliverable_value_usd - (impressions * cpm_usd / 1000.0)) > 0.01
ORDER BY variance_usd DESC;


-- ============================================================
-- Section 2: Segmentation Analysis
-- ============================================================

-- 2.1 Engagement performance by therapeutic area
-- Why it matters: directly answers which therapeutic areas are delivering
-- the strongest HCP engagement, the core client-facing comparison.
SELECT
    therapeutic_area,
    COUNT(*) AS reports,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 3) AS ctr_pct,
    ROUND(AVG(pacing_pct), 2) AS avg_pacing_pct
FROM concord_clinical_network
GROUP BY therapeutic_area
ORDER BY ctr_pct DESC;

-- 2.2 Performance by physician specialty and campaign format
-- Why it matters: surfaces whether underperformance is a format problem,
-- a specialty-targeting problem, or both -- shapes where creative or
-- targeting changes go next cycle.
SELECT
    physician_specialty,
    campaign_format,
    COUNT(*) AS reports,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 3) AS ctr_pct,
    ROUND(AVG(avg_time_on_content_seconds), 1) AS avg_time_on_content_seconds
FROM concord_clinical_network
GROUP BY physician_specialty, campaign_format
ORDER BY physician_specialty, ctr_pct DESC;

-- 2.3 Top and bottom 5 specialty/region segments by CTR
-- (minimum volume threshold applied so low-volume segments don't distort the ranking)
-- Why it matters: this is the exact "top and bottom driver segments" cut a
-- client review or internal QBR asks for.
WITH segment_perf AS (
    SELECT
        physician_specialty,
        region,
        SUM(impressions) AS impressions,
        ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 3) AS ctr_pct
    FROM concord_clinical_network
    GROUP BY physician_specialty, region
    HAVING SUM(impressions) >= 5000
),
ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY ctr_pct DESC) AS rank_top,
        RANK() OVER (ORDER BY ctr_pct ASC) AS rank_bottom
    FROM segment_perf
)
SELECT physician_specialty, region, impressions, ctr_pct,
       CASE WHEN rank_top <= 5 THEN 'Top 5' ELSE 'Bottom 5' END AS segment_tier
FROM ranked
WHERE rank_top <= 5 OR rank_bottom <= 5
ORDER BY ctr_pct DESC;


-- ============================================================
-- Section 3: Financial Impact
-- ============================================================

-- 3.1 Contracted vs. actual deliverable value and pacing, by client
-- Why it matters: converts a delivery metric (impressions) into the dollar
-- figure client and commercial leadership actually track against contract.
SELECT
    client_name,
    ROUND(SUM(contracted_deliverable_value_usd), 2) AS contracted_value_usd,
    ROUND(SUM(actual_deliverable_value_usd), 2) AS actual_value_usd,
    ROUND(100.0 * SUM(actual_deliverable_value_usd) / NULLIF(SUM(contracted_deliverable_value_usd), 0), 2)
        AS overall_pacing_pct
FROM concord_clinical_network
GROUP BY client_name
ORDER BY actual_value_usd DESC;

-- 3.2 Attributed ROI by therapeutic area
-- Why it matters: the dollar-value follow-through leadership wants alongside
-- raw engagement -- which areas are converting reach into attributed value.
SELECT
    therapeutic_area,
    ROUND(SUM(actual_deliverable_value_usd), 2) AS spend_usd,
    SUM(follow_up_actions) AS follow_up_actions,
    ROUND(AVG(attributed_roi), 2) AS avg_attributed_roi
FROM concord_clinical_network
GROUP BY therapeutic_area
ORDER BY avg_attributed_roi DESC;

-- 3.3 Campaigns furthest off pace (under- and over-delivery)
-- Why it matters: this is the list a reporting analyst hands to the account
-- team before a pacing conversation with the client.
SELECT
    campaign_id,
    client_name,
    ROUND(AVG(pacing_pct), 2) AS avg_pacing_pct,
    SUM(CASE WHEN pacing_deviation_flag THEN 1 ELSE 0 END) AS weeks_off_pace,
    COUNT(*) AS weeks_reported
FROM concord_clinical_network
GROUP BY campaign_id, client_name
HAVING SUM(CASE WHEN pacing_deviation_flag THEN 1 ELSE 0 END) >= 3
ORDER BY avg_pacing_pct ASC;


-- ============================================================
-- Section 4: Cohort and Behavioral Analysis
-- ============================================================

-- 4.1 Week-over-week engagement trend, by therapeutic area and quarter
-- Why it matters: the recurring trend view a client expects in every
-- reporting cycle -- is engagement improving, flat, or declining.
SELECT
    therapeutic_area,
    EXTRACT(YEAR FROM report_week) AS report_year,
    EXTRACT(QUARTER FROM report_week) AS report_quarter,
    SUM(impressions) AS impressions,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 3) AS ctr_pct
FROM concord_clinical_network
GROUP BY therapeutic_area, EXTRACT(YEAR FROM report_week), EXTRACT(QUARTER FROM report_week)
ORDER BY therapeutic_area, report_year, report_quarter;

-- 4.2 Cumulative reach growth by campaign tenure cohort
-- Why it matters: shows how quickly a typical campaign ramps to full reach,
-- used to set expectations with clients launching a new campaign.
SELECT
    weeks_since_launch,
    COUNT(*) AS segment_weeks,
    ROUND(AVG(specialty_verified_reach), 1) AS avg_specialty_verified_reach,
    SUM(specialty_verified_reach) AS total_specialty_verified_reach
FROM concord_clinical_network
WHERE weeks_since_launch <= 26
GROUP BY weeks_since_launch
ORDER BY weeks_since_launch;

-- 4.3 Funnel drop-off rates: impression -> click -> engagement -> verified reach -> follow-up
-- Why it matters: the exact funnel the HCP Engagement Funnel tab renders --
-- identifies which stage is leaking the most reach.
SELECT
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 3) AS pct_impression_to_click,
    ROUND(100.0 * SUM(content_engagements) / NULLIF(SUM(clicks), 0), 3) AS pct_click_to_engagement,
    ROUND(100.0 * SUM(specialty_verified_reach) / NULLIF(SUM(content_engagements), 0), 3)
        AS pct_engagement_to_verified,
    ROUND(100.0 * SUM(follow_up_actions) / NULLIF(SUM(specialty_verified_reach), 0), 3)
        AS pct_verified_to_followup
FROM concord_clinical_network;


-- ============================================================
-- Section 5: Reporting Automation and Escalation Queries
-- ============================================================

-- 5.1 Week-over-week pacing delta per segment (window function)
-- Why it matters: the automated check that flags a segment swinging sharply
-- off pace between two consecutive reporting weeks, before a human reviews it.
SELECT
    campaign_id,
    physician_specialty,
    region,
    report_week,
    pacing_pct,
    LAG(pacing_pct) OVER (
        PARTITION BY campaign_id, physician_specialty, region ORDER BY report_week
    ) AS prior_week_pacing_pct,
    ROUND(pacing_pct - LAG(pacing_pct) OVER (
        PARTITION BY campaign_id, physician_specialty, region ORDER BY report_week
    ), 2) AS pacing_delta_pct
FROM concord_clinical_network
QUALIFY ABS(pacing_delta_pct) > 25
ORDER BY ABS(pacing_delta_pct) DESC;

-- 5.1b Portable equivalent of the QUALIFY filter above (standard ANSI SQL)
-- Why it matters: QUALIFY isn't supported everywhere (e.g. vanilla PostgreSQL
-- before 9.x extensions) -- this CTE form runs anywhere.
WITH pacing_deltas AS (
    SELECT
        campaign_id, physician_specialty, region, report_week, pacing_pct,
        LAG(pacing_pct) OVER (
            PARTITION BY campaign_id, physician_specialty, region ORDER BY report_week
        ) AS prior_week_pacing_pct
    FROM concord_clinical_network
)
SELECT *,
       ROUND(pacing_pct - prior_week_pacing_pct, 2) AS pacing_delta_pct
FROM pacing_deltas
WHERE ABS(pacing_pct - prior_week_pacing_pct) > 25
ORDER BY ABS(pacing_pct - prior_week_pacing_pct) DESC;

-- 5.2 Campaign leaderboard, ranked by engagement rate and ROI (window function)
-- Why it matters: powers the Campaign Leaderboard tab -- the ranked view
-- account leads use to decide which campaigns to feature or intervene on.
SELECT
    campaign_id,
    client_name,
    therapeutic_area,
    ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 3) AS ctr_pct,
    ROUND(AVG(attributed_roi), 2) AS avg_attributed_roi,
    RANK() OVER (ORDER BY ROUND(100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0), 3) DESC) AS ctr_rank,
    RANK() OVER (ORDER BY AVG(attributed_roi) DESC) AS roi_rank
FROM concord_clinical_network
GROUP BY campaign_id, client_name, therapeutic_area
HAVING SUM(impressions) >= 5000
ORDER BY ctr_rank;

-- 5.3 QA escalation candidate list -- feeds the dashboard's escalation queue
-- Why it matters: the final, automated output of this whole reporting
-- pipeline -- the ranked list of reports a QA analyst should review first
-- today, combining the auditable rule score with the model's priority rank.
SELECT
    report_id,
    campaign_id,
    client_name,
    report_week,
    qa_risk_score,
    qa_risk_tier,
    missing_data_flag,
    pacing_deviation_flag,
    escalation_risk_score,
    escalation_risk_decile
FROM concord_clinical_network
WHERE flagged_for_qa_escalation = 1
ORDER BY escalation_risk_decile ASC, qa_risk_score DESC;
