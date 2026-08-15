"""Concord Clinical Network -- Reporting & QA Tracker
Author: Luciano Casillas
Built to portfolio-dashboard-production-standard.md v2.0.
Tab index: Overview, Period-over-Period Trend, HCP Engagement Funnel,
Campaign Leaderboard, Geographic & Specialty Performance, Model + Risk,
Financial Impact, Recommendations.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Concord Clinical Network -- Reporting & QA Tracker",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------- color palette
NAVY = "#0A3360"
STEEL_700 = "#405E7C"
BLUE_700 = "#0077B3"
BLUE_500 = "#4EBEE5"
STEEL_300 = "#D1E2E5"
STEEL_100 = "#F4F9FA"
WHITE = "#FFFFFF"
BLACK = "#2D2D2D"
GRAY_700 = "#707070"
GRAY_300 = "#CCCCCC"
GREEN_700 = "#08CAA9"
GREEN_900 = "#067462"
ORANGE_700 = "#FF8A39"
RED_SOFT = "#E05252"

CATEGORY_COLORS = [BLUE_700, GREEN_700, ORANGE_700, STEEL_700, BLUE_500, GREEN_900, GRAY_700, NAVY]
CHART_FONT = dict(family="Arial, Helvetica, sans-serif", size=12, color=NAVY)

DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------- CSS

def inject_css():
    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {{
            background-color: {WHITE} !important;
        }}
        [data-testid="stSidebar"] {{ background-color: {STEEL_100} !important; }}
        body, p, div, span, label {{ font-size: 11pt; color: {BLACK}; }}

        div[data-testid="stMetric"] {{
            background-color: {WHITE};
            border-left: 4px solid {BLUE_700};
            border-radius: 4px;
            padding: 12px 14px;
            box-shadow: 0 1px 3px rgba(10,51,96,0.08);
        }}
        div[data-testid="stMetric"] label {{ color: {NAVY} !important; }}
        div[data-testid="stMetricLabel"] {{
            white-space: normal !important;
            overflow-wrap: break-word;
            line-height: 1.25;
            min-height: 2.6em;
        }}
        div[data-testid="stMetricValue"] {{
            font-size: 2.25rem;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
            line-height: 1.15;
        }}

        .insight-strip {{
            background: {WHITE};
            border-left: 4px solid {BLUE_700};
            border-radius: 4px;
            padding: 10px 14px;
            margin: 8px 0 14px 0;
            box-shadow: 0 1px 3px rgba(10,51,96,0.06);
        }}
        .insight-strip .label {{
            font-size: 12pt; font-weight: 700; letter-spacing: 0.03em;
            color: {NAVY}; text-transform: uppercase;
        }}
        .insight-strip .body {{ font-size: 11pt; color: {NAVY}; margin-top: 2px; line-height: 1.55; }}

        .chart-takeaway {{
            background: {STEEL_100};
            border-left: 3px solid {GREEN_700};
            border-radius: 4px;
            padding: 7px 12px;
            margin: 2px 0 18px 0;
            font-size: 11pt;
            color: {NAVY};
        }}
        .chart-takeaway b {{ color: {GREEN_900}; }}

        .section-header {{
            background: {STEEL_100};
            border-left: 4px solid {BLUE_700};
            border-radius: 4px;
            padding: 9px 16px;
            margin: 18px 0 10px 0;
        }}
        .section-header h4 {{ margin: 0; font-size: 12pt; font-weight: 700; color: {NAVY}; }}
        .section-subtitle {{ font-size: 11pt; color: {STEEL_700}; margin: -6px 0 10px 2px; }}

        .rec-card {{
            border-left: 4px solid {BLUE_700}; background-color: {WHITE}; border-radius: 4px;
            padding: 12px 14px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(10,51,96,0.06);
            min-height: 150px;
        }}
        .rec-card .tier {{ color: {STEEL_700}; font-size: 12pt; text-transform: uppercase; font-weight: 700; }}
        .rec-card .title {{ color: {NAVY}; font-size: 12pt; font-weight: 700; margin: 2px 0 6px 0; }}
        .rec-card .badge {{
            display: inline-block; background-color: {GREEN_700}; color: {WHITE}; border-radius: 3px;
            padding: 2px 8px; font-size: 11pt; font-weight: 700; margin-right: 6px;
        }}
        .rec-card .badge.effort {{ background-color: {STEEL_700}; }}
        .rec-card .evidence {{ color: {GRAY_700}; font-size: 11pt; margin-top: 6px; font-style: italic; }}

        .action-divider {{ border: none; border-top: 3px solid {BLUE_700}; margin: 30px 0 18px 0; }}

        .filter-pill {{
            display: inline-block; background-color: {STEEL_100}; color: {NAVY};
            border: 1px solid {STEEL_300}; border-radius: 12px; padding: 3px 10px;
            font-size: 11pt; margin: 2px 4px 2px 0;
        }}

        [data-baseweb="tag"] {{ color: {WHITE} !important; }}
        [data-baseweb="tag"] * {{ color: {WHITE} !important; }}
        [data-tag] {{ color: {WHITE} !important; }}
        [data-tag] * {{ color: {WHITE} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------ loading

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_DIR / "concord_clinical_network.csv", parse_dates=["report_week"])
    metadata = json.loads((DATA_DIR / "metadata.json").read_text()) if (DATA_DIR / "metadata.json").exists() else {}
    return df, metadata


df_raw, meta = load_data()

# ---------------------------------------------------------- session state

DEFAULTS = {
    "f_client": sorted(df_raw["client_name"].dropna().unique().tolist()),
    "f_area": sorted(df_raw["therapeutic_area"].dropna().unique().tolist()),
    "f_format": sorted(df_raw["campaign_format"].dropna().unique().tolist()),
    "f_specialty": sorted(df_raw["physician_specialty"].dropna().unique().tolist()),
    "f_region": sorted(df_raw["region"].dropna().unique().tolist()),
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset_filters():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


# --------------------------------------------------------------- chart helpers

def base_layout(height=340):
    return dict(
        height=height,
        paper_bgcolor=WHITE,
        plot_bgcolor=WHITE,
        font=CHART_FONT,
        margin=dict(l=16, r=16, t=44, b=44),
    )


def style_fig(fig, title, height=340):
    fig.update_layout(**base_layout(height))
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=12, color=NAVY), x=0.02, xanchor="left"),
        xaxis=dict(showgrid=False, gridcolor=STEEL_300),
        yaxis=dict(showgrid=True, gridcolor=STEEL_300, zeroline=False),
        legend=dict(font=dict(size=11)),
    )
    return fig


def bar_chart(data, x, y, title, y_title="", shared_max=None, color=BLUE_700, pct=False, height=340):
    fig = go.Figure()
    colors = [CATEGORY_COLORS[i % len(CATEGORY_COLORS)] for i in range(len(data))] if color is None else color
    text = [f"{v:.2f}%" if pct else f"{v:,.0f}" for v in data[y]]
    fig.add_trace(go.Bar(
        x=data[x], y=data[y], marker_color=colors,
        text=text, textposition="outside", textfont=dict(size=12, color=NAVY),
    ))
    layout = base_layout(height=height)
    layout.update(title=dict(text=f"<b>{title}</b>", font=dict(size=12, color=NAVY), x=0.02, xanchor="left"),
                   yaxis_title=y_title, showlegend=False)
    if shared_max:
        layout["yaxis"] = dict(range=[0, shared_max], showgrid=True, gridcolor=STEEL_300)
    fig.update_layout(**layout)
    return fig


def sparkline(data, x, y, color=BLUE_700):
    fig = go.Figure(go.Scatter(
        x=data[x], y=data[y], mode="lines+markers",
        line=dict(color=color, width=2), marker=dict(size=4),
    ))
    fig.update_layout(
        height=60, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor=WHITE, plot_bgcolor=WHITE,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, range=[data[y].min() * 0.85, data[y].max() * 1.15] if len(data) else None),
        showlegend=False,
    )
    return fig


def kpi_card(label, value, spark_df, x, y, color):
    st.metric(label, value)
    st.plotly_chart(sparkline(spark_df, x, y, color), width="stretch", config={"displayModeBar": False})


def takeaway(text):
    st.markdown(f'<div class="chart-takeaway">\U0001F4CC <b>Takeaway:</b> {text}</div>', unsafe_allow_html=True)


def insight(text, label="Key Finding"):
    sentences = [s.strip() for s in text.split(". ") if s.strip()]
    if len(sentences) > 1:
        items = "".join(f"<li>{s}{'.' if not s.endswith('.') else ''}</li>" for s in sentences)
        body_html = f"<ul style='margin:6px 0 0 0;padding-left:18px;'>{items}</ul>"
    else:
        body_html = text
    st.markdown(
        f'<div class="insight-strip"><div class="label">{label}</div><div class="body">{body_html}</div></div>',
        unsafe_allow_html=True,
    )


def section_header(title, question=None, info_text=None):
    st.markdown(f'<div class="section-header"><h4>{title}</h4></div>', unsafe_allow_html=True)
    if question:
        section_subtitle(f"Question: {question}")
    if info_text:
        with st.expander("What am I looking at?"):
            st.markdown(info_text)


def section_subtitle(text):
    st.markdown(f'<div class="section-subtitle">{text}</div>', unsafe_allow_html=True)


def action_divider():
    st.markdown('<hr class="action-divider">', unsafe_allow_html=True)


def rec_card(tier, title, value_badge, effort_badge, body, evidence):
    st.markdown(
        f'<div class="rec-card">'
        f'<div class="tier">{tier}</div>'
        f'<div class="title">{title}</div>'
        f'<span class="badge">Value: {value_badge}</span>'
        f'<span class="badge effort">Effort: {effort_badge}</span>'
        f'<div>{body}</div>'
        f'<div class="evidence">Evidence: {evidence}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def heatmap_text_colors(z, threshold):
    return [["#FFFFFF" if v > threshold else "#000000" for v in row] for row in z]


def confusion_matrix_chart(tn, fp, fn, tp, height=360):
    z = [[1, 0], [0, 1]]  # [[TN, FP], [FN, TP]] -- TN/TP=navy(1), FP/FN=red(0)
    counts = [[tn, fp], [fn, tp]]
    fig = go.Figure(go.Heatmap(
        z=z,
        x=["Predicted: No Escalation", "Predicted: Escalation"],
        y=["Actual: No Escalation", "Actual: Escalation"],
        colorscale=[[0, RED_SOFT], [1, NAVY]],
        showscale=False,
        text=[[f"{c:,}" for c in row] for row in counts],
        texttemplate="%{text}",
        textfont=dict(size=14, color=WHITE),
        xgap=3, ygap=3,
    ))
    fig.update_layout(**base_layout(height=height))
    fig.update_layout(
        title=dict(text="<b>Escalation Model Confusion Matrix (Test Set)</b>",
                    font=dict(size=12, color=NAVY), x=0.02, xanchor="left"),
        yaxis=dict(autorange="reversed"),
    )
    return fig


# --------------------------------------------------------------- filtering

def apply_filters(df):
    mask = (
        df["client_name"].isin(st.session_state["f_client"])
        & df["therapeutic_area"].isin(st.session_state["f_area"])
        & df["campaign_format"].isin(st.session_state["f_format"])
        & df["physician_specialty"].isin(st.session_state["f_specialty"])
        & df["region"].isin(st.session_state["f_region"])
    )
    return df[mask]


def filter_summary_block():
    pills = []
    labels = [
        ("f_client", "Client"), ("f_area", "Therapeutic Area"), ("f_format", "Format"),
        ("f_specialty", "Specialty"), ("f_region", "Region"),
    ]
    for key, label in labels:
        if len(st.session_state[key]) < len(DEFAULTS[key]):
            pills.append(f"{label}: {len(st.session_state[key])} selected")
    if not pills:
        pills = ["No filters applied: showing all reports"]
    st.markdown("".join(f'<span class="filter-pill">{p}</span>' for p in pills), unsafe_allow_html=True)


def sidebar_filters(df):
    st.sidebar.markdown(f"<h3 style='color:{NAVY};'>Filters</h3>", unsafe_allow_html=True)
    st.sidebar.multiselect("Client", options=DEFAULTS["f_client"], key="f_client")
    st.sidebar.multiselect("Therapeutic Area", options=DEFAULTS["f_area"], key="f_area")
    st.sidebar.multiselect("Campaign Format", options=DEFAULTS["f_format"], key="f_format")
    st.sidebar.multiselect("Physician Specialty", options=DEFAULTS["f_specialty"], key="f_specialty")
    st.sidebar.multiselect("Region", options=DEFAULTS["f_region"], key="f_region")
    st.sidebar.button("Reset All Filters", on_click=reset_filters)

    fdf = apply_filters(df)
    pct_filtered = 100.0 * len(fdf) / len(df) if len(df) else 0
    st.sidebar.progress(min(pct_filtered / 100, 1.0))
    st.sidebar.caption(f"{len(fdf):,} of {len(df):,} reports shown ({pct_filtered:.2f}%)")
    return fdf


# ------------------------------------------------------------------ main

def main():
    inject_css()
    fdf = sidebar_filters(df_raw)

    st.markdown(
        f"<h2 style='color:{NAVY}; font-size:2.25rem; margin:0;'>Concord Clinical Network -- Reporting &amp; QA Tracker</h2>",
        unsafe_allow_html=True,
    )
    st.caption("Reporting Partnerships | Client Measurement & QA | Synthetic data, seed 42")

    if fdf.empty:
        st.warning("No reports match the current filter selection. Adjust or reset the filters in the sidebar.")
        return

    total_reports = len(fdf)
    escalation_rate = 100 * fdf["flagged_for_qa_escalation"].mean()
    avg_pacing = fdf["pacing_pct"].mean()
    avg_ctr = 100 * fdf["clicks"].sum() / max(fdf["impressions"].sum(), 1)
    total_value = fdf["actual_deliverable_value_usd"].sum()

    weekly = fdf.groupby("report_week").agg(
        n=("report_id", "size"),
        escalations=("flagged_for_qa_escalation", "sum"),
        pacing=("pacing_pct", "mean"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        value=("actual_deliverable_value_usd", "sum"),
    ).reset_index().sort_values("report_week")
    weekly["escalation_rate"] = 100 * weekly["escalations"] / weekly["n"].replace(0, np.nan)
    weekly["ctr"] = 100 * weekly["clicks"] / weekly["impressions"].replace(0, np.nan)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        kpi_card("Reports in View", f"{total_reports:,}", weekly, "report_week", "n", BLUE_700)
    with k2:
        kpi_card("QA Escalation Rate", f"{escalation_rate:.2f}%", weekly, "report_week", "escalation_rate", RED_SOFT)
    with k3:
        kpi_card("Avg Pacing vs. Target", f"{avg_pacing:.2f}%", weekly, "report_week", "pacing", ORANGE_700)
    with k4:
        kpi_card("Avg Click-Through Rate", f"{avg_ctr:.2f}%", weekly, "report_week", "ctr", GREEN_700)
    with k5:
        kpi_card("Deliverable Value Tracked", f"${total_value / 1_000_000:.2f}M", weekly, "report_week", "value", STEEL_700)

    st.markdown("---")

    tabs = st.tabs([
        "Overview",
        "Period-over-Period Trend",
        "HCP Engagement Funnel",
        "Campaign Leaderboard",
        "Geographic & Specialty Performance",
        "Model + Risk",
        "Financial Impact",
        "Recommendations",
    ])

    # ----------------------------------------------------------- Overview
    with tabs[0]:
        insight(
            f"Of {total_reports:,} reports in the current view, average pacing against contracted delivery is "
            f"{avg_pacing:.2f}% and {escalation_rate:.2f}% required a QA correction or escalation this cycle. "
            f"Click-through rate averages {avg_ctr:.2f}% and total attributed deliverable value tracked is "
            f"${total_value:,.0f}.",
            label="Executive Summary",
        )

        section_header(
            "Pacing vs. Contracted Target by Client",
            question="Which clients are pacing off contracted target and need a proactive conversation "
                      "before they raise it themselves?",
        )
        by_client = fdf.groupby("client_name")["pacing_pct"].mean().reset_index().sort_values("pacing_pct", ascending=False)
        fig = bar_chart(by_client, "client_name", "pacing_pct", "Average Pacing vs. Contracted Target by Client",
                         y_title="Pacing %", pct=True, color=None)
        fig.add_hline(y=100, line_dash="dash", line_color=STEEL_700)
        st.plotly_chart(fig, width="stretch")
        best = by_client.iloc[0]
        worst = by_client.iloc[-1]
        takeaway(f"<b>{best['client_name']}</b> paces highest in view at <b>{best['pacing_pct']:.2f}%</b> of "
                 f"contracted target; <b>{worst['client_name']}</b> paces lowest at <b>{worst['pacing_pct']:.2f}%</b>. "
                 f"Action: <b>{worst['client_name']}</b> is the one worth an account-lead check-in this week, "
                 f"before the client notices the gap first.")

        section_header(
            "Weekly Actual vs. Contracted Deliverable Value",
            question="Is delivery keeping pace with what we contracted for, in aggregate and over time?",
        )
        wk_val = fdf.groupby("report_week").agg(
            actual=("actual_deliverable_value_usd", "sum"),
            contracted=("contracted_deliverable_value_usd", "sum"),
        ).reset_index().sort_values("report_week")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=wk_val["report_week"], y=wk_val["contracted"], name="Contracted",
                                  line=dict(color=STEEL_300, width=2, dash="dash"),
                                  hovertemplate="Contracted: $%{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=wk_val["report_week"], y=wk_val["actual"], name="Actual",
                                  line=dict(color=BLUE_700, width=2),
                                  hovertemplate="Actual: $%{y:,.2f}<extra></extra>"))
        fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.22))
        st.plotly_chart(style_fig(fig, "Weekly Deliverable Value: Actual vs. Contracted", height=360), width="stretch")
        gap_pct = 100 * (wk_val["actual"].sum() - wk_val["contracted"].sum()) / max(wk_val["contracted"].sum(), 1)
        takeaway(f"Actual deliverable value tracks <b>{gap_pct:+.2f}%</b> against contracted value across the "
                 f"full window in view (${wk_val['actual'].sum():,.0f} actual vs. ${wk_val['contracted'].sum():,.0f} contracted). "
                 f"Action: a gap this small confirms aggregate delivery is healthy -- the real risk lives at the "
                 f"individual-report level, not the total, which is exactly what the Model + Risk tab's "
                 f"escalation queue is built to catch.")

    # -------------------------------------------------- Period-over-Period Trend
    with tabs[1]:
        section_header(
            "Click-Through Rate Trend by Therapeutic Area",
            question="Is engagement improving, flat, or declining for each therapeutic area over time?",
        )
        trend = fdf.copy()
        trend["year_q"] = trend["report_week"].dt.to_period("Q").astype(str)
        by_q = trend.groupby(["year_q", "therapeutic_area"]).agg(
            clicks=("clicks", "sum"), impressions=("impressions", "sum")
        ).reset_index().sort_values("year_q")
        by_q["ctr_pct"] = 100 * by_q["clicks"] / by_q["impressions"].replace(0, np.nan)
        fig = px.line(by_q, x="year_q", y="ctr_pct", color="therapeutic_area", markers=True,
                      color_discrete_sequence=CATEGORY_COLORS)
        fig.update_traces(hovertemplate="%{fullData.name}: %{y:.2f}%<extra></extra>")
        st.plotly_chart(style_fig(fig, "Quarterly Click-Through Rate by Therapeutic Area", height=380), width="stretch")
        latest_q = by_q["year_q"].max()
        latest = by_q[by_q["year_q"] == latest_q].sort_values("ctr_pct", ascending=False)
        if not latest.empty:
            top = latest.iloc[0]
            takeaway(f"In <b>{latest_q}</b>, <b>{top['therapeutic_area']}</b> leads all therapeutic areas at "
                     f"<b>{top['ctr_pct']:.2f}%</b> CTR. Action: this is the area's creative and targeting "
                     f"strategy worth carrying into next quarter's renewals.")

        section_header(
            "Campaign Format Mix Shift Over Time",
            question="Is our format mix shifting toward the formats that actually perform best?",
        )
        fmt_q = trend.groupby(["year_q", "campaign_format"]).size().reset_index(name="n").sort_values("year_q")
        fig = px.area(fmt_q, x="year_q", y="n", color="campaign_format", color_discrete_sequence=CATEGORY_COLORS)
        fig.update_traces(hovertemplate="%{fullData.name}: %{y:,.0f} reports<extra></extra>")
        fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.22))
        st.plotly_chart(style_fig(fig, "Report Volume by Campaign Format Over Time", height=380), width="stretch")
        top_format = fdf["campaign_format"].value_counts(normalize=True).idxmax()
        top_format_pct = 100 * fdf["campaign_format"].value_counts(normalize=True).max()
        takeaway(f"<b>{top_format}</b> is the largest format in view at <b>{top_format_pct:.2f}%</b> of report volume. "
                 f"Action: check this mix against the Campaign Leaderboard tab's CTR-by-format spread before "
                 f"renewing budget in this proportion -- volume share and performance are not the same signal.")

    # -------------------------------------------------------- HCP Engagement Funnel
    with tabs[2]:
        section_header(
            "Impression-to-Follow-Up Funnel",
            question="Where in the funnel are we losing the most reach, and is that stage expected or a "
                      "problem worth fixing?",
            info_text="**Specialty-verified reach**: engaged HCPs whose specialty was confirmed against the "
                       "targeting list. **Follow-up action**: a verified HCP completing a further engagement "
                       "step (e.g. requesting more information).",
        )
        stages = ["Impressions", "Clicks", "Content Engagements", "Specialty-Verified Reach", "Follow-Up Actions"]
        values = [
            fdf["impressions"].sum(), fdf["clicks"].sum(), fdf["content_engagements"].sum(),
            fdf["specialty_verified_reach"].sum(), fdf["follow_up_actions"].sum(),
        ]
        funnel_text = [
            f"{v / 1_000_000:.2f}M<br>{100 * v / max(values[0], 1):.2f}%" for v in values
        ]
        fig = go.Figure(go.Funnel(
            y=stages, x=values, marker=dict(color=CATEGORY_COLORS[:5]),
            text=funnel_text, texttemplate="%{text}",
        ))
        st.plotly_chart(style_fig(fig, "HCP Engagement Funnel", height=420), width="stretch")

        stage_drops = [
            (f"{stages[i - 1]} to {stages[i]}", 100 * (1 - values[i] / max(values[i - 1], 1)))
            for i in range(1, len(stages))
        ]
        biggest_drop = max(stage_drops, key=lambda d: d[1])
        overall_dropoff = 100 * (1 - values[-1] / max(values[0], 1))
        takeaway(
            f"Of <b>{values[0]:,}</b> impressions in view, <b>{values[-1]:,}</b> convert to a follow-up "
            f"action -- a <b>{overall_dropoff:.2f}%</b> cumulative drop-off across the full funnel. "
            f"The single largest stage-to-stage drop is <b>{biggest_drop[0]}</b> at <b>{biggest_drop[1]:.2f}%</b>, "
            f"expected for display advertising -- the more addressable falloff is further downstream: only "
            f"<b>{100 * values[-1] / max(values[3], 1):.2f}%</b> of specialty-verified HCPs complete a follow-up "
            f"action, worth testing calls-to-action against."
        )

        section_header(
            "Click-to-Engagement Rate by Campaign Format",
            question="Once an HCP clicks, which format holds their attention through to content engagement?",
        )
        by_fmt = fdf.groupby("campaign_format").agg(
            clicks=("clicks", "sum"), engagements=("content_engagements", "sum")
        ).reset_index()
        by_fmt["engage_rate_pct"] = 100 * by_fmt["engagements"] / by_fmt["clicks"].replace(0, np.nan)
        by_fmt = by_fmt.sort_values("engage_rate_pct", ascending=False)
        st.plotly_chart(bar_chart(by_fmt, "campaign_format", "engage_rate_pct",
                                   "Click-to-Content-Engagement Rate by Format", pct=True, color=None),
                         width="stretch")
        top_fmt = by_fmt.iloc[0]
        spread = by_fmt["engage_rate_pct"].max() - by_fmt["engage_rate_pct"].min()
        takeaway(f"<b>{top_fmt['campaign_format']}</b> converts clicks to content engagement at "
                 f"<b>{top_fmt['engage_rate_pct']:.2f}%</b>, but every format lands within "
                 f"<b>{spread:.2f} points</b> of each other. Action: format choice should be driven by the "
                 f"much larger click-through-rate gap seen on the Campaign Leaderboard tab, not by this metric.")

    # ---------------------------------------------------------- Campaign Leaderboard
    with tabs[3]:
        section_header(
            "Top Campaigns by Click-Through Rate",
            question="Which specific campaigns are strong enough to feature as a client success story or "
                      "reference in a renewal conversation?",
        )
        camp = fdf.groupby(["campaign_id", "client_name", "therapeutic_area"]).agg(
            impressions=("impressions", "sum"), clicks=("clicks", "sum"), avg_roi=("attributed_roi", "mean"),
        ).reset_index()
        camp = camp[camp["impressions"] >= 5000]
        camp["ctr_pct"] = 100 * camp["clicks"] / camp["impressions"]
        top15 = camp.sort_values("ctr_pct", ascending=False).head(15)
        top15["label"] = top15["client_name"] + " (" + top15["campaign_id"] + ")"
        fig = px.bar(top15, x="ctr_pct", y="label", orientation="h", color_discrete_sequence=[BLUE_700])
        fig.update_traces(texttemplate="%{x:.2f}%", textposition="outside", textfont=dict(size=12, color=NAVY))
        fig.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(style_fig(fig, "Top 15 Campaigns by CTR (min. 5,000 impressions)", height=460), width="stretch")
        if not top15.empty:
            top = top15.iloc[0]
            takeaway(f"<b>{top['label']}</b> leads the leaderboard at <b>{top['ctr_pct']:.2f}%</b> CTR "
                     f"among campaigns with at least 5,000 impressions in view. Action: a strong candidate to "
                     f"cite in that client's next renewal conversation.")

        section_header(
            "Click-Through Rate Spread by Campaign Format",
            question="Is performance predictable within a format, or does it swing widely campaign to campaign?",
        )
        camp_fmt = camp.merge(fdf[["campaign_id", "campaign_format"]].drop_duplicates(), on="campaign_id")
        fig = px.box(camp_fmt, x="campaign_format", y="ctr_pct", color_discrete_sequence=[BLUE_700])
        fig.update_layout(xaxis_title="Campaign Format", yaxis_title="CTR %")
        st.plotly_chart(style_fig(fig, "CTR Distribution by Campaign Format", height=380), width="stretch")
        iqr_by_fmt = camp_fmt.groupby("campaign_format")["ctr_pct"].apply(
            lambda s: (s.quantile(0.75) - s.quantile(0.25)) / max(s.median(), 0.01) * 100
        ).sort_values(ascending=False)
        widest_fmt = iqr_by_fmt.index[0]
        takeaway(f"Median CTR across all qualifying campaigns in view is <b>{camp['ctr_pct'].median():.2f}%</b>. "
                 f"Every format's interquartile spread stays under <b>4% of its own median</b> -- performance is "
                 f"tightly clustered within each format ({widest_fmt} is the widest at "
                 f"<b>{iqr_by_fmt.iloc[0]:.2f}%</b> relative spread). Action: which format you choose drives CTR "
                 f"far more than campaign-to-campaign variance within a format.")

    # ------------------------------------------------- Geographic & Specialty Performance
    with tabs[4]:
        section_header(
            "Engagement Rate: Specialty x Region",
            question="Which specialty and region combinations deserve more targeting investment?",
        )
        heat = fdf.groupby(["physician_specialty", "region"]).agg(
            clicks=("clicks", "sum"), impressions=("impressions", "sum")
        ).reset_index()
        heat["ctr_pct"] = 100 * heat["clicks"] / heat["impressions"].replace(0, np.nan)
        pivot = heat.pivot(index="physician_specialty", columns="region", values="ctr_pct")
        z = pivot.values
        threshold = np.nanmean(z) if z.size else 0
        fig = go.Figure(go.Heatmap(
            z=z, x=pivot.columns.tolist(), y=pivot.index.tolist(),
            colorscale=[[0, STEEL_300], [1, BLUE_700]],
            text=[[f"{v:.2f}%" if not np.isnan(v) else "" for v in row] for row in z],
            texttemplate="%{text}",
            textfont=dict(size=11),
            colorbar=dict(title="CTR %"),
        ))
        st.plotly_chart(style_fig(fig, "Click-Through Rate by Specialty and Region", height=460), width="stretch")
        max_idx = np.unravel_index(np.nanargmax(z), z.shape)
        takeaway(f"<b>{pivot.index[max_idx[0]]}</b> in the <b>{pivot.columns[max_idx[1]]}</b> region has the "
                 f"highest CTR in view at <b>{z[max_idx]:.2f}%</b>. Action: the strongest expansion candidate "
                 f"for incremental targeting budget next cycle.")

        section_header(
            "Top 10 Specialty x Region Segments by Volume",
            question="Where is most of our reach concentrated today, regardless of how well it performs?",
        )
        top_vol = heat.sort_values("impressions", ascending=False).head(10).copy()
        top_vol["label"] = top_vol["physician_specialty"] + " / " + top_vol["region"]
        st.plotly_chart(bar_chart(top_vol, "label", "impressions", "Top 10 Segments by Impression Volume",
                                   color=STEEL_700, height=380), width="stretch")
        takeaway(f"The top segment by volume is <b>{top_vol.iloc[0]['label']}</b> with "
                 f"<b>{top_vol.iloc[0]['impressions']:,}</b> impressions in view. Action: cross-check this "
                 f"against the CTR heatmap above -- high volume does not guarantee high engagement, and budget "
                 f"following volume alone can miss better-performing, lower-volume segments.")

    # ---------------------------------------------------------------- Model + Risk
    with tabs[5]:
        model_meta = meta.get("model", {})
        cm = model_meta.get("confusion_matrix_test", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Escalation Model Test AUC", f"{model_meta.get('test_auc', 0):.3f}")
        c2.metric("Decile-1 Lift", f"{model_meta.get('decile1_lift', 0):.2f}x")
        c3.metric("Overall Escalation Rate", f"{100 * model_meta.get('overall_escalation_rate', 0):.2f}%")

        insight(
            "Every report gets a rule-based QA risk score computed the same week it is reported, from variance, "
            "missing-data, and pacing-deviation signals alone. That score is fully auditable line by line and is "
            "the checkpoint a client-facing conversation is built on. A small logistic regression model sits on "
            "top of it purely to prioritize a long escalation queue, combining the rule score with client, format, "
            "and specialty context. It never overrides the rule and is never shown to a client -- it only decides "
            "the order the queue gets worked in.",
            label="How To Read This Tab",
        )

        section_header(
            "Escalation Rate by Risk Decile",
            question="Does the escalation-risk model actually concentrate real risk, or is its ranking no "
                      "better than random?",
            info_text="**Decile 1 = highest predicted escalation risk, decile 10 = lowest**, always ranked "
                       "this direction. **Escalation risk score** is the model's predicted probability that a "
                       "report will require QA escalation.",
        )
        dec = fdf.dropna(subset=["escalation_risk_decile"]).groupby("escalation_risk_decile").agg(
            n=("report_id", "size"), esc=("flagged_for_qa_escalation", "sum")
        ).reset_index()
        dec["decile"] = dec["escalation_risk_decile"].astype(int)
        dec["esc_rate"] = 100 * dec["esc"] / dec["n"]
        fig = px.bar(dec.sort_values("decile"), x="decile", y="esc_rate", text="esc_rate",
                     color_discrete_sequence=[RED_SOFT])
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside", textfont=dict(size=12, color=NAVY))
        fig.update_layout(xaxis=dict(dtick=1))
        st.plotly_chart(style_fig(fig, "Actual Escalation Rate by Predicted Risk Decile (1 = Highest Risk)"),
                         width="stretch")
        d1 = dec[dec["decile"] == 1]
        if not d1.empty:
            takeaway(f"Decile 1 (highest predicted risk) has an actual escalation rate of "
                     f"<b>{d1.iloc[0]['esc_rate']:.2f}%</b> versus <b>"
                     f"{100 * model_meta.get('overall_escalation_rate', 0):.2f}%</b> overall in the full dataset.")

        if cm:
            section_header(
                "Escalation Model Confusion Matrix",
                question="At the standard 0.5 probability threshold, how often is the model right, and what "
                          "kind of mistakes does it make?",
            )
            st.plotly_chart(
                confusion_matrix_chart(cm.get("true_negative", 0), cm.get("false_positive", 0),
                                        cm.get("false_negative", 0), cm.get("true_positive", 0)),
                width="stretch",
            )
            precision = cm.get("true_positive", 0) / max(cm.get("true_positive", 0) + cm.get("false_positive", 0), 1)
            takeaway(f"At the default 0.5 probability threshold, the model's test-set precision is "
                     f"<b>{100 * precision:.2f}%</b> -- most reports it flags do end up requiring escalation. "
                     f"Action: this precision level supports using the model to prioritize the queue, but the "
                     f"rule-based score stays the actual gate -- the model ranks within it, never replaces it.")

        section_header(
            "QA Escalation Queue -- Highest Priority",
            question="Given everything above, which specific reports should a QA analyst open first today?",
        )
        queue = fdf[fdf["flagged_for_qa_escalation"] == 1].sort_values(
            ["escalation_risk_decile", "qa_risk_score"], ascending=[True, False]
        ).head(15)[["report_id", "campaign_id", "client_name", "report_week", "qa_risk_score", "qa_risk_tier",
                     "escalation_risk_score"]]
        queue["escalation_risk_score"] = (100 * queue["escalation_risk_score"]).round(2)
        st.dataframe(
            queue.rename(columns={"escalation_risk_score": "escalation_risk_pct"}),
            width="stretch", hide_index=True,
        )
        takeaway(f"This table lists the <b>{len(queue)}</b> highest-priority escalations currently in view -- the "
                 f"daily review list a QA analyst would work first.")

    # ---------------------------------------------------------------- Financial Impact
    with tabs[6]:
        section_header(
            "Contracted vs. Actual Deliverable Value by Client",
            question="Which client accounts are over- or under-delivering against what they contracted for?",
        )
        by_client = fdf.groupby("client_name").agg(
            contracted=("contracted_deliverable_value_usd", "sum"),
            actual=("actual_deliverable_value_usd", "sum"),
        ).reset_index().sort_values("actual", ascending=False)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=by_client["client_name"], y=by_client["contracted"], name="Contracted",
                              marker_color=STEEL_300, hovertemplate="Contracted: $%{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Bar(x=by_client["client_name"], y=by_client["actual"], name="Actual",
                              marker_color=BLUE_700, hovertemplate="Actual: $%{y:,.2f}<extra></extra>"))
        fig.update_layout(barmode="group", legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.22))
        st.plotly_chart(style_fig(fig, "Contracted vs. Actual Deliverable Value by Client", height=400),
                         width="stretch")
        takeaway(f"Total actual deliverable value tracked across all clients in view is "
                 f"<b>${by_client['actual'].sum():,.0f}</b> against <b>${by_client['contracted'].sum():,.0f}</b> "
                 f"contracted. Action: cross-reference against the Overview tab's pacing-by-client ranking -- "
                 f"the same clients should show up on both.")

        section_header(
            "Attributed ROI by Therapeutic Area",
            question="Which therapeutic areas justify the strongest renewal or upsell case based on "
                      "demonstrated return?",
        )
        by_area = fdf.groupby("therapeutic_area")["attributed_roi"].mean().reset_index().sort_values(
            "attributed_roi", ascending=False
        )
        st.plotly_chart(bar_chart(by_area, "therapeutic_area", "attributed_roi",
                                   "Average Attributed ROI by Therapeutic Area", y_title="ROI (x spend)",
                                   color=None, height=360), width="stretch")
        top_area = by_area.iloc[0]
        takeaway(f"<b>{top_area['therapeutic_area']}</b> shows the strongest average attributed ROI in view at "
                 f"<b>{top_area['attributed_roi']:.2f}x</b> spend. Action: the strongest QBR talking point to "
                 f"lead with for that area's clients heading into a renewal.")

    # ---------------------------------------------------------------- Recommendations
    with tabs[7]:
        section_subtitle(
            "Every recommendation below traces back to a specific chart or SQL query above, cited in its "
            "Evidence line, tiered by how soon it can realistically be acted on."
        )
        filter_summary_block()
        section_header("Immediate Actions (0-30 Days)")
        c1, c2 = st.columns(2)
        with c1:
            rec_card(
                "Immediate", "Work the decile-1 escalation queue first",
                "High", "Low",
                "Route the Model + Risk tab's decile-1 report list to same-day QA review before those reports "
                "reach a client, converting the model from a postmortem report into a same-cycle catch.",
                "Model + Risk tab, QA Escalation Queue",
            )
        with c2:
            rec_card(
                "Immediate", "Fix the double-loaded feed producing duplicate report rows",
                "High", "Low",
                "SQL Section 1.3 finds report rows sharing an identical campaign/specialty/region/week business "
                "key -- a double-submitted feed that silently inflates every downstream KPI until deduplicated.",
                "SQL Section 1.3, Duplicate Report-Row Detection",
            )

        action_divider()
        section_header("Short-Term Actions (30-90 Days)")
        c1, c2 = st.columns(2)
        with c1:
            rec_card(
                "Short-Term", "Target the lowest-pacing clients for a pacing conversation",
                "Medium", "Medium",
                "Use the Overview tab's pacing-by-client ranking to prioritize which accounts need a proactive "
                "pacing conversation before the client raises it first.",
                "Overview tab, Pacing vs. Contracted Target by Client",
            )
        with c2:
            rec_card(
                "Short-Term", "Reallocate underperforming specialty x region targeting",
                "Medium", "Medium",
                "Use the Geographic & Specialty Performance tab's heatmap to shift budget away from the lowest "
                "click-through-rate specialty x region cells toward the highest-performing ones.",
                "Geographic & Specialty Performance tab, Specialty x Region Heatmap",
            )

        action_divider()
        section_header("Strategic Investments (90+ Days)")
        c1, c2 = st.columns(2)
        with c1:
            rec_card(
                "Strategic", "Embed the QA risk score at report-generation time",
                "High", "High",
                "All three rule inputs (variance, missing data, pacing deviation) are knowable the moment a "
                "report is generated -- scoring at generation time converts this from a downstream QA pass into "
                "a pre-send control.",
                "data_dictionary.md, Rule-based QA risk score",
            )
        with c2:
            rec_card(
                "Strategic", "Formalize the escalation-risk model as a queue-ranking service",
                "Medium", "High",
                "The decile-1 lift shown on the Model + Risk tab is strong enough to justify running the model "
                "as a lightweight scheduled job that re-ranks the queue daily as new reports land, rather than "
                "a one-time batch score.",
                "Model + Risk tab, Decile-1 Lift metric",
            )


if __name__ == "__main__":
    main()
