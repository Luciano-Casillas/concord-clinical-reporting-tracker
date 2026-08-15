# Entity-Relationship Diagram

Source-system schema behind the analysis-ready `data/concord_clinical_network.csv`
extract. See `table_definitions.md` in this directory for column-level detail and
the join logic.

```mermaid
erDiagram
    CLIENTS ||--o{ CAMPAIGNS : "runs"
    CAMPAIGNS ||--o{ CAMPAIGN_SEGMENTS : "targets"
    CAMPAIGNS ||--|| CONTRACT_TERMS : "priced by"
    CAMPAIGN_SEGMENTS ||--o{ DELIVERY_LOG : "reports weekly"
    DELIVERY_LOG ||--|| QA_REVIEW : "scored by"

    CLIENTS {
        string client_id PK
        string client_name
        string primary_therapeutic_area
    }
    CAMPAIGNS {
        string campaign_id PK
        string client_id FK
        string therapeutic_area
        string campaign_format
        date launch_date
        integer campaign_length_weeks
    }
    CONTRACT_TERMS {
        string campaign_id FK
        float cpm_usd
        integer contracted_impressions_weekly
    }
    CAMPAIGN_SEGMENTS {
        string segment_id PK
        string campaign_id FK
        string physician_specialty
        string region
    }
    DELIVERY_LOG {
        string report_id PK
        string segment_id FK
        date report_week
        integer weeks_since_launch
        integer impressions
        integer clicks
        integer content_engagements
        float avg_time_on_content_seconds
        integer specialty_verified_reach
        integer follow_up_actions
    }
    QA_REVIEW {
        string report_id FK
        float qa_risk_score
        string qa_risk_tier
        boolean missing_data_flag
        boolean pacing_deviation_flag
        integer flagged_for_qa_escalation
        float escalation_risk_score
        integer escalation_risk_decile
    }
```

`DELIVERY_LOG.report_id` carries a small number of intentional duplicate business
keys (`segment_id` + `report_week` appearing twice) -- a simulated double-loaded
feed from the ad-serving system, the kind of defect the QA/data-quality SQL
section is built to catch. See `data/data_dictionary.md` for full column
definitions and leakage notes on the escalation-risk model.
