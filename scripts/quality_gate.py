import re

import pandas as pd

import ast

src = open("app.py", encoding="utf-8").read()

ast.parse(src)
print("PASS: syntax")

assert src.count("—") == 0, "FAIL: em dash found"
print("PASS: no em dashes")

# Streamlit's markdown renderer typographer-converts "--" to a real em dash
# in plain st.markdown() calls (e.g. expander info_text) even though the
# source only has ASCII hyphens -- unsafe_allow_html div-wrapped blocks are
# exempt (raw HTML passthrough), but info_text= and any other plain
# st.markdown() text is not. Caught by browser inspection during manual
# verification; guarded here so it can't silently regress.
info_text_blocks = re.findall(r'info_text=(".*?"|\(.*?\))', src, flags=re.DOTALL)
for block in info_text_blocks:
    assert " -- " not in block, f"FAIL: info_text contains ' -- ', renders as a real em dash: {block[:80]}"
print("PASS: no double-hyphen dashes in info_text (would render as em dash)")

assert "RED_700" not in src, "FAIL: RED_700 found (must be RED_SOFT)"
print("PASS: no RED_700 literal")

base_layout_body = src.split("def base_layout(")[1].split("def style_fig(")[0]
dict_body = base_layout_body.split("return dict(")[1].split(")\n\n\n")[0]
keys = re.findall(r"^\s*(\w+)=", dict_body, flags=re.MULTILINE)
assert len(keys) == 5, f"FAIL: base_layout() has {len(keys)} keys, expected exactly 5: {keys}"
print(f"PASS: base_layout() has exactly 5 keys: {keys}")

gen_src = open("scripts/01_generate_data.py", encoding="utf-8").read()
assert "pd.qcut(-" in gen_src, "FAIL: generator decile assignment must be descending"
print("PASS: generator decile assignment is descending")

df = pd.read_csv("data/concord_clinical_network.csv")
assert set(df["flagged_for_qa_escalation"].unique()).issubset({0, 1}), "FAIL: target column not binary"
assert df["flagged_for_qa_escalation"].isnull().sum() == 0, "FAIL: target column has nulls"
print("PASS: target column clean")

leakage_cols = ["escalation_risk_score", "escalation_risk_decile", "report_id", "campaign_id"]
features_block = gen_src.split("cat_features = [")[1].split("target =")[0] if "cat_features = [" in gen_src else ""
for col in leakage_cols:
    assert f'"{col}"' not in features_block, f"FAIL: output/identifier column {col} referenced as a model feature"
print("PASS: model output/identifier columns excluded from model features")

dup_key_cols = ["campaign_id", "physician_specialty", "region", "report_week"]
dup_count = df.duplicated(subset=dup_key_cols, keep=False).sum()
assert dup_count > 0, "FAIL: expected the intentional duplicate-report-row scenario to be present in the data"
print(f"PASS: intentional duplicate-report-row scenario present ({dup_count} rows)")

funnel_cols = ["impressions", "clicks", "content_engagements", "specialty_verified_reach", "follow_up_actions"]
for a, b in zip(funnel_cols, funnel_cols[1:]):
    assert (df[b] > df[a]).sum() == 0, f"FAIL: funnel monotonicity violated between {a} and {b}"
print("PASS: engagement funnel is monotonically non-increasing")

print("\nAll quality gate checks passed.")
