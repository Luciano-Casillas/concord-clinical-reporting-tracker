"""
Synthetic data generator for Concord Clinical Network -- Reporting & QA Tracker.

Produces the analysis-ready reporting table under data/:
  concord_clinical_network.csv

Grain: one row per (pharma client campaign) x (physician specialty x region
segment) x (reporting week). Simulates a physician-reach media network's
weekly client reporting feed, including the messiness a reporting-QA analyst
actually has to catch: duplicate report rows from double-loaded feeds,
missing telemetry fields, and pacing/variance swings.

Two QA signals are generated, deliberately kept distinct:
  qa_risk_score / qa_risk_tier   -- rule-based, same-week, fully auditable.
                                     This is the checkpoint a reporting analyst
                                     can explain line-by-line to a client.
  escalation_risk_score/decile   -- a small LogisticRegression model that
                                     combines the rule score with campaign/
                                     client/format context to help prioritize
                                     a long escalation queue. It never
                                     overrides the rule -- it ranks within it.

Reproducible via numpy.random.default_rng(42).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
RNG = np.random.default_rng(SEED)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

TARGET_ROWS = 350_000
WINDOW_WEEKS = 104  # 2-year reporting window

# most recent Monday on/before "today" for the synthetic window's end
TODAY = pd.Timestamp("2026-08-14")
WINDOW_END = TODAY - pd.Timedelta(days=int(TODAY.dayofweek))
WINDOW_START = WINDOW_END - pd.Timedelta(weeks=WINDOW_WEEKS)

CLIENTS_TO_AREA = {
    "Kestrel Biosciences": "Oncology",
    "Larchmont Biotech": "Oncology",
    "Alderbrook Pharmaceuticals": "Cardiology",
    "Cairnwell Therapeutics": "Cardiology",
    "Thornfield Therapeutics": "Immunology",
    "Rosewood Health Sciences": "Endocrinology",
    "Brackenridge Pharma": "Neurology",
}
CLIENTS = list(CLIENTS_TO_AREA.keys())

PHYSICIAN_SPECIALTIES = [
    "Medical Oncology", "Cardiology", "Endocrinology", "Neurology",
    "Rheumatology", "Pulmonology", "Dermatology", "Gastroenterology",
    "Psychiatry", "Nephrology",
]

REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
REGION_WEIGHTS = [0.24, 0.20, 0.19, 0.16, 0.21]

CAMPAIGN_FORMATS = ["Sponsored Content", "Native Display", "Video", "Email"]
FORMAT_WEIGHTS = [0.34, 0.24, 0.22, 0.20]

FORMAT_CPM = {"Sponsored Content": 42.0, "Native Display": 26.0, "Video": 68.0, "Email": 35.0}
FORMAT_CTR_RANGE = {
    "Sponsored Content": (0.022, 0.045),
    "Native Display": (0.007, 0.018),
    "Video": (0.010, 0.022),
    "Email": (0.035, 0.070),
}
FORMAT_TIME_ON_CONTENT = {
    "Sponsored Content": (25, 90),
    "Native Display": (8, 28),
    "Video": (55, 190),
    "Email": (5, 22),
}

VALUE_PER_FOLLOWUP = {
    "Oncology": 130.0, "Neurology": 95.0, "Cardiology": 75.0,
    "Immunology": 85.0, "Endocrinology": 65.0,
}

N_CAMPAIGNS = 2420


def gen_campaigns(n: int) -> pd.DataFrame:
    client_idx = RNG.integers(0, len(CLIENTS), size=n)
    clients = [CLIENTS[i] for i in client_idx]
    areas = [CLIENTS_TO_AREA[c] for c in clients]
    formats = RNG.choice(CAMPAIGN_FORMATS, size=n, p=FORMAT_WEIGHTS)

    max_launch_week = WINDOW_WEEKS - 8  # leave room for a minimum 8-week campaign
    launch_week = RNG.integers(0, max_launch_week, size=n)
    raw_length = RNG.integers(8, 53, size=n)  # 8-52 weeks
    length = np.minimum(raw_length, WINDOW_WEEKS - launch_week)

    n_specialties = RNG.integers(2, 6, size=n)   # specialties targeted per campaign
    n_regions = RNG.integers(2, 5, size=n)       # regions targeted per campaign

    return pd.DataFrame({
        "campaign_id": [f"CMP-{100000 + i}" for i in range(n)],
        "client_name": clients,
        "therapeutic_area": areas,
        "campaign_format": formats,
        "launch_week_offset": launch_week,
        "campaign_length_weeks": length,
        "n_specialties": n_specialties,
        "n_regions": n_regions,
    })


def build_segments(campaigns: pd.DataFrame) -> list[pd.DataFrame]:
    """Expand each campaign into (specialty, region) segments x reporting weeks."""
    frames = []
    for row in campaigns.itertuples(index=False):
        specialties = RNG.choice(PHYSICIAN_SPECIALTIES, size=row.n_specialties, replace=False)
        regions = RNG.choice(REGIONS, size=row.n_regions, replace=False,
                              p=None)  # sub-selection, uniform among chosen regions

        segment_pairs = [(s, r) for s in specialties for r in regions]
        max_segments = min(len(segment_pairs), 9)
        min_segments = min(3, len(segment_pairs))
        n_segments = RNG.integers(min_segments, max_segments + 1)
        chosen = RNG.choice(len(segment_pairs), size=n_segments, replace=False)
        chosen_segments = [segment_pairs[i] for i in chosen]

        weeks = np.arange(1, row.campaign_length_weeks + 1)
        n_weeks = len(weeks)

        for specialty, region in chosen_segments:
            base_volume = RNG.lognormal(mean=7.1, sigma=0.6)  # base weekly impressions scale
            seg_df = pd.DataFrame({
                "campaign_id": row.campaign_id,
                "client_name": row.client_name,
                "therapeutic_area": row.therapeutic_area,
                "campaign_format": row.campaign_format,
                "physician_specialty": specialty,
                "region": region,
                "campaign_length_weeks": row.campaign_length_weeks,
                "weeks_since_launch": weeks,
                "report_week": WINDOW_START + pd.to_timedelta(
                    (row.launch_week_offset + weeks - 1) * 7, unit="D"
                ),
                "base_volume": base_volume,
            })
            frames.append(seg_df)
    return frames


def simulate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    formats = df["campaign_format"].values
    areas = df["therapeutic_area"].values

    # ramp: impressions build over the first ~6 weeks, then plateau with noise
    ramp = np.minimum(df["weeks_since_launch"].values / 6.0, 1.0)
    noise = RNG.normal(1.0, 0.18, size=n).clip(0.4, 1.9)
    impressions = np.round(df["base_volume"].values * ramp * noise).astype(int)
    impressions = np.maximum(impressions, 50)

    ctr_lo = np.array([FORMAT_CTR_RANGE[f][0] for f in formats])
    ctr_hi = np.array([FORMAT_CTR_RANGE[f][1] for f in formats])
    ctr = RNG.uniform(ctr_lo, ctr_hi)
    clicks = np.round(impressions * ctr).astype(int)

    engagement_rate = RNG.uniform(0.45, 0.65, size=n)
    content_engagements = np.round(clicks * engagement_rate).astype(int)

    time_lo = np.array([FORMAT_TIME_ON_CONTENT[f][0] for f in formats])
    time_hi = np.array([FORMAT_TIME_ON_CONTENT[f][1] for f in formats])
    avg_time_on_content = RNG.uniform(time_lo, time_hi)

    verify_rate = RNG.uniform(0.55, 0.80, size=n)
    specialty_verified_reach = np.round(content_engagements * verify_rate).astype(int)

    followup_rate = RNG.uniform(0.10, 0.30, size=n)
    follow_up_actions = np.round(specialty_verified_reach * followup_rate).astype(int)

    cpm = np.array([FORMAT_CPM[f] for f in formats])
    contracted_ratio = RNG.normal(1.0, 0.12, size=n).clip(0.6, 1.6)
    contracted_impressions = np.round(impressions / np.maximum(contracted_ratio, 0.05)).astype(int)
    contracted_impressions = np.maximum(contracted_impressions, 1)

    contracted_deliverable_value_usd = contracted_impressions * cpm / 1000.0
    actual_deliverable_value_usd = impressions * cpm / 1000.0
    pacing_pct = np.round(100.0 * actual_deliverable_value_usd / contracted_deliverable_value_usd, 2)

    value_per_followup = np.array([VALUE_PER_FOLLOWUP[a] for a in areas])
    attributed_roi = np.round(
        (follow_up_actions * value_per_followup) / np.maximum(actual_deliverable_value_usd, 1.0), 2
    )

    out = df.copy()
    out["impressions"] = impressions
    out["clicks"] = clicks
    out["ctr_pct"] = np.round(100.0 * clicks / impressions, 3)
    out["content_engagements"] = content_engagements
    out["avg_time_on_content_seconds"] = np.round(avg_time_on_content, 1)
    out["specialty_verified_reach"] = specialty_verified_reach
    out["follow_up_actions"] = follow_up_actions
    out["contracted_impressions"] = contracted_impressions
    out["cpm_usd"] = cpm
    out["contracted_deliverable_value_usd"] = np.round(contracted_deliverable_value_usd, 2)
    out["actual_deliverable_value_usd"] = np.round(actual_deliverable_value_usd, 2)
    out["pacing_pct"] = pacing_pct
    out["attributed_roi"] = attributed_roi
    return out.drop(columns=["base_volume"])


def inject_messiness(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ~4% missing telemetry -- a real client feed with an incomplete field
    missing_idx = RNG.choice(df.index, size=int(len(df) * 0.04), replace=False)
    df.loc[missing_idx, "avg_time_on_content_seconds"] = np.nan
    df["missing_data_flag"] = df["avg_time_on_content_seconds"].isna()

    # ~0.35% duplicate report rows -- same business key, double-loaded feed
    dup_idx = RNG.choice(df.index, size=int(len(df) * 0.0035), replace=False)
    dup_rows = df.loc[dup_idx].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)

    df["report_id"] = [f"RPT-{1_000_000 + i}" for i in range(len(df))]
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True)


def compute_qa_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["campaign_id", "physician_specialty", "region", "report_week"]).copy()

    grp = df.groupby(["campaign_id", "physician_specialty", "region"])["actual_deliverable_value_usd"]
    variance_pct = grp.pct_change().fillna(0.0) * 100.0
    df["reported_metric_variance_pct"] = np.round(variance_pct, 2)

    df["pacing_deviation_flag"] = (df["pacing_pct"] < 80) | (df["pacing_pct"] > 120)

    n = len(df)
    score = (
        0.35 * np.minimum(df["reported_metric_variance_pct"].abs().values, 100)
        + 30.0 * df["missing_data_flag"].values.astype(float)
        + 25.0 * df["pacing_deviation_flag"].values.astype(float)
        + RNG.normal(0, 5, size=n)
    )
    df["qa_risk_score"] = np.round(np.clip(score, 0, 100), 1)

    df["qa_risk_tier"] = pd.cut(
        df["qa_risk_score"], bins=[-0.1, 40, 70, 100.1], labels=["Low", "Medium", "High"]
    ).astype(str)

    # probabilistic escalation target -- correlated with the score but not
    # a deterministic threshold, so a downstream model has real signal to add
    prob = 1.0 / (1.0 + np.exp(-(df["qa_risk_score"].values - 60) / 8.0))
    flagged = RNG.random(n) < prob
    flagged = flagged | (df["qa_risk_score"].values >= 85)   # always-escalate ceiling
    flagged = flagged & ~((df["qa_risk_score"].values < 15) & (RNG.random(n) < 0.98))  # hard floor
    df["flagged_for_qa_escalation"] = flagged.astype(int)

    return df.reset_index(drop=True)


def train_escalation_model(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import confusion_matrix, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    model_df = df.copy()
    model_df["missing_data_flag"] = model_df["missing_data_flag"].astype(int)
    model_df["pacing_deviation_flag"] = model_df["pacing_deviation_flag"].astype(int)

    cat_features = ["client_name", "therapeutic_area", "campaign_format", "physician_specialty", "region"]
    num_features = [
        "weeks_since_launch", "campaign_length_weeks", "pacing_pct",
        "reported_metric_variance_pct", "missing_data_flag", "pacing_deviation_flag",
        "qa_risk_score",
    ]
    target = "flagged_for_qa_escalation"

    X = model_df[cat_features + num_features]
    y = model_df[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )

    preprocess = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_features),
    ], remainder="passthrough")

    pipe = Pipeline([
        ("prep", preprocess),
        ("clf", LogisticRegression(max_iter=1000)),
    ])
    pipe.fit(X_train, y_train)

    test_proba = pipe.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, test_proba)
    test_pred = (test_proba >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, test_pred).ravel()

    model_df["escalation_risk_score"] = pipe.predict_proba(X)[:, 1]
    model_df["escalation_risk_decile"] = (
        pd.qcut(-model_df["escalation_risk_score"], 10, labels=False, duplicates="drop") + 1
    )

    decile1_flags = model_df.loc[model_df["escalation_risk_decile"] == 1, target].sum()
    total_flags = model_df[target].sum()
    lift = (decile1_flags / max(total_flags, 1)) / 0.10

    metadata = {
        "seed": SEED,
        "n_rows": int(len(model_df)),
        "window_start": str(WINDOW_START.date()),
        "window_end": str(WINDOW_END.date()),
        "n_campaigns": N_CAMPAIGNS,
        "model": {
            "algorithm": "LogisticRegression",
            "purpose": "Escalation-queue prioritization -- ranks within the rule-based QA flag, never replaces it",
            "features": cat_features + num_features,
            "target": target,
            "test_auc": round(float(auc), 4),
            "decile1_lift": round(float(lift), 2),
            "overall_escalation_rate": round(float(y.mean()), 4),
            "confusion_matrix_test": {
                "true_negative": int(tn), "false_positive": int(fp),
                "false_negative": int(fn), "true_positive": int(tp),
            },
        },
    }
    return model_df, metadata


def main():
    print(f"Generating Concord Clinical Network reporting data (seed={SEED})...")
    campaigns = gen_campaigns(N_CAMPAIGNS)
    frames = build_segments(campaigns)
    df = pd.concat(frames, ignore_index=True)
    print(f"  raw segment-weeks before trim: {len(df):,}")

    if len(df) > TARGET_ROWS:
        df = df.sample(n=TARGET_ROWS, random_state=SEED).reset_index(drop=True)
    df = simulate_metrics(df)
    df = inject_messiness(df)
    df = compute_qa_signals(df)
    df, metadata = train_escalation_model(df)

    df["report_week"] = pd.to_datetime(df["report_week"]).dt.date

    col_order = [
        "report_id", "campaign_id", "client_name", "therapeutic_area", "campaign_format",
        "physician_specialty", "region", "report_week", "weeks_since_launch", "campaign_length_weeks",
        "impressions", "clicks", "ctr_pct", "content_engagements", "avg_time_on_content_seconds",
        "specialty_verified_reach", "follow_up_actions",
        "contracted_impressions", "cpm_usd", "contracted_deliverable_value_usd",
        "actual_deliverable_value_usd", "pacing_pct", "attributed_roi",
        "reported_metric_variance_pct", "missing_data_flag", "pacing_deviation_flag",
        "qa_risk_score", "qa_risk_tier", "flagged_for_qa_escalation",
        "escalation_risk_score", "escalation_risk_decile",
    ]
    df = df[col_order]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_DIR / "concord_clinical_network.csv", index=False)
    (DATA_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"  final rows: {len(df):,} -> data/concord_clinical_network.csv")
    print(f"  campaigns: {df['campaign_id'].nunique():,}  clients: {df['client_name'].nunique()}")
    print(f"  escalation rate: {metadata['model']['overall_escalation_rate']:.2%}")
    print(f"  model: LogisticRegression AUC={metadata['model']['test_auc']:.3f}, "
          f"decile-1 lift={metadata['model']['decile1_lift']:.2f}x -> data/metadata.json")


if __name__ == "__main__":
    main()
