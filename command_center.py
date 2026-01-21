import streamlit as st
import pandas as pd
import json
from datetime import datetime
import pytz
import os
import time
import textwrap

from app_utils import preprocess, compute_analytics

# ======================================================
# CONFIG
# ======================================================
DATA_DIR = "data/live"
POLL_SECONDS = 10

# ======================================================
# HTML RENDERER
# ======================================================
def render_html_card(html):
    html = textwrap.dedent(html)
    html = "".join(line.strip() for line in html.splitlines())
    st.markdown(html, unsafe_allow_html=True)

# ======================================================
# SESSION STATE
# ======================================================
st.session_state.setdefault("df", None)
st.session_state.setdefault("last_loaded_file", None)
st.session_state.setdefault("ack_actions", set())

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(page_title="HVAC Energy Command Center", layout="wide")

# ======================================================
# BRANDING
# ======================================================
try:
    with open("assets/config.json") as f:
        branding = json.load(f)
except FileNotFoundError:
    branding = {
        "timezone": "Asia/Kolkata",
        "airport_name": "Demo Airport",
        "terminal_name": "T1"
    }

tz = pytz.timezone(branding["timezone"])

# ======================================================
# HEADER
# ======================================================
c1, c2 = st.columns([1, 6])
with c1:
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=80)

with c2:
    st.markdown("<h1>HVAC ENERGY COMMAND CENTER</h1>", unsafe_allow_html=True)
    st.caption(
        f"{branding['airport_name']} • {branding['terminal_name']} • Advisory analytics only"
    )

# ======================================================
# SIDEBAR
# ======================================================
st.sidebar.header("⚙️ Detection Configuration")

ZONE_OVERCOOL_TOL = st.sidebar.slider("Zone overcool tolerance (°C)", 0.5, 3.0, 1.0, 0.5)
ZONE_SAT_TOL = st.sidebar.slider("Zone comfort tolerance (°C)", 0.0, 2.0, 0.5, 0.1)
AHU_AIRFLOW_HIGH = st.sidebar.slider("AHU high airflow threshold (%)", 30, 100, 60, 5)
AHU_ZONE_SAT_RATIO = st.sidebar.slider("Satisfied zone ratio (%)", 60, 95, 80, 5) / 100
CHILLER_LOW_DT = st.sidebar.slider("Chiller Low ΔT threshold (°C)", 2.0, 8.0, 4.0, 0.5)

st.sidebar.header("💰 Cost Assumptions")
COST_PER_KWH = st.sidebar.number_input("Electricity cost (₹/kWh)", 5.0, 30.0, 10.0)

if st.sidebar.button("🔄 Force Reload"):
    st.session_state.df = None
    st.session_state.last_loaded_file = None
    st.rerun()

# ======================================================
# CSV INGESTION
# ======================================================
def get_latest_csv(folder):
    if not os.path.exists(folder):
        return None
    files = sorted(f for f in os.listdir(folder) if f.endswith(".csv"))
    return os.path.join(folder, files[-1]) if files else None

latest_file = get_latest_csv(DATA_DIR)

if latest_file is None:
    st.warning("📡 Waiting for HVAC CSVs from BMS …")
    time.sleep(POLL_SECONDS)
    st.rerun()

if st.session_state.last_loaded_file != latest_file:
    df_new = pd.read_csv(latest_file)
    df_new = preprocess(df_new)
    st.session_state.df = df_new
    st.session_state.last_loaded_file = latest_file
    st.toast(f"📥 New data ingested: {os.path.basename(latest_file)}")

df = st.session_state.df

# ======================================================
# TIME
# ======================================================
now = df["timestamp"].max()
now_local = now.tz_localize("UTC").tz_convert(tz) if now.tzinfo is None else now.astimezone(tz)

# ======================================================
# ANALYTICS (FLAGS ONLY)
# ======================================================
cfg = dict(
    ZONE_OVERCOOL_TOL=ZONE_OVERCOOL_TOL,
    ZONE_SAT_TOL=ZONE_SAT_TOL,
    AHU_AIRFLOW_HIGH=AHU_AIRFLOW_HIGH,
    AHU_ZONE_SAT_RATIO=AHU_ZONE_SAT_RATIO,
    CHILLER_LOW_DT=CHILLER_LOW_DT,
    COST_PER_KWH=COST_PER_KWH,
)

zone_flags, ahu_flags, chiller_flags = compute_analytics(df, cfg)

# ======================================================
# TOTAL LOSS
# ======================================================
total_cost = (
    zone_flags["est_cost"].sum()
    + ahu_flags["est_cost"].sum()
    + chiller_flags["est_cost"].sum()
)

# ======================================================
# KPI STRIP
# ======================================================
def kpi_card(title, value, color):
    render_html_card(f"""
    <div style="background:#0b1220;padding:20px;border-radius:14px;
                text-align:center;border-left:6px solid {color};">
        <div style="color:#9ca3af;font-size:14px;">{title}</div>
        <div style="font-size:36px;font-weight:700;color:{color};">{value}</div>
    </div>
    """)

k1, k2, k3, k4 = st.columns(4)
with k1: kpi_card("💸 Total Estimated Loss (₹)", f"{int(total_cost):,}", "#facc15")
with k2: kpi_card("🌡 Zones Overcooled", zone_flags["zone_id"].nunique(), "#fb923c")
with k3: kpi_card("🌀 AHUs Wasting Energy", ahu_flags["ahu_id"].nunique(), "#38bdf8")
with k4: kpi_card("❄️ Chillers (Low ΔT)", chiller_flags["chiller_id"].nunique(), "#60a5fa")

# ======================================================
# SEVERITY
# ======================================================
def severity(cost):
    if cost >= 5000:
        return "High", "#ef4444"
    if cost >= 2000:
        return "Medium", "#f59e0b"
    return "Low", "#22c55e"

# ======================================================
# ACTION CARD
# ======================================================
def render_action_card(r, acknowledged):
    sev, sev_color = severity(r["Cost"])
    border = "#22c55e" if acknowledged else sev_color
    status = "Completed" if acknowledged else "Pending"
    status_icon = "✅" if acknowledged else "⏳"

    render_html_card(f"""
    <div style="
        background:radial-gradient(circle at top left,#0f172a,#020617);
        border-left:6px solid {border};
        border-radius:16px;
        padding:22px;
        margin-bottom:14px;
        color:#e5e7eb;
    ">
        <div style="font-size:20px;font-weight:700;margin-bottom:10px;">
            🔴 {r['Type']} – {r['Asset']}
        </div>

        <div style="margin-bottom:14px;">
            <b>Severity:</b>
            <span style="color:{sev_color};font-weight:700;">{sev}</span>
        </div>

        🧩 <b>Rule</b><br>{r['Rule']}<br><br>
        📊 <b>Evidence</b><br>{r['Evidence']}<br><br>
        🛠 <b>Recommended Action</b><br>{r['Action']}<br>

        <div style="background:#020617;padding:12px;border-radius:10px;margin-top:12px;font-size:13px;">
            <b>Why?</b><br>{r['Why']}
        </div>

        <div style="margin-top:14px;font-weight:600;">
            💰 Estimated Loss: ₹{int(r['Cost']):,}
        </div>

        <div style="margin-top:6px;">
            <b>Status:</b> {status_icon} {status}
        </div>
    </div>
    """)

# ======================================================
# TOP ACTIONS (ZONE + AHU + CHILLER)
# ======================================================
st.markdown("## 🚨 TOP ACTIONS TODAY")

actions = []

# ---------- ZONES ----------
for zone, g in zone_flags.groupby("zone_id"):
    df_zone = df[df["zone_id"] == zone]

    if {"zone_temp", "zone_setpoint"}.issubset(df_zone.columns):
        dev = (df_zone["zone_setpoint"] - df_zone["zone_temp"]).mean()
        evidence = f"Avg deviation = {dev:.1f}°C"
    else:
        evidence = "Zone temperature data unavailable"

    actions.append(dict(
        Type="Overcooled Zone",
        Asset=zone,
        Cost=g["est_cost"].sum(),
        Rule=f"Zone temperature below setpoint > {ZONE_OVERCOOL_TOL}°C",
        Evidence=evidence,
        Action="Increase zone setpoint or reduce airflow",
        Why="Overcooling wastes cooling energy and reduces passenger comfort."
    ))

# ---------- AHUs ----------
for ahu, g in ahu_flags.groupby("ahu_id"):
    df_ahu = df[df["ahu_id"] == ahu]

    if {"zone_temp", "zone_setpoint"}.issubset(df_ahu.columns):
        satisfied = (
            (df_ahu["zone_temp"] - df_ahu["zone_setpoint"]).abs()
            <= ZONE_SAT_TOL
        )
        sat_pct = int(satisfied.mean() * 100)
        evidence = f"Satisfied zones ≈ {sat_pct}%"
    else:
        evidence = "Zone temperature data unavailable"

    actions.append(dict(
        Type="AHU Excess Airflow",
        Asset=ahu,
        Cost=g["est_cost"].sum(),
        Rule="High airflow while zones are satisfied",
        Evidence=evidence,
        Action="Reset static pressure or reduce airflow",
        Why="Fan energy is wasted when airflow does not follow actual demand."
    ))

# ---------- CHILLERS ----------
for ch, g in chiller_flags.groupby("chiller_id"):
    df_ch = df[df["chiller_id"] == ch]

    if {"chw_return_temp", "chw_supply_temp"}.issubset(df_ch.columns):
        dt = (df_ch["chw_return_temp"] - df_ch["chw_supply_temp"]).mean()
        evidence = f"Avg ΔT = {dt:.1f}°C (Threshold {CHILLER_LOW_DT}°C)"
    else:
        evidence = "Chilled water temperature data unavailable"

    actions.append(dict(
        Type="Low ΔT (Chiller)",
        Asset=ch,
        Cost=g["est_cost"].sum(),
        Rule="Chilled water ΔT below threshold",
        Evidence=evidence,
        Action="Inspect bypass valve and chilled water flow",
        Why="Low ΔT indicates poor heat transfer or bypass flow."
    ))

actions_df = pd.DataFrame(actions).sort_values("Cost", ascending=False).head(3)

for i, r in actions_df.iterrows():
    action_id = f"{r['Type']}|{r['Asset']}"
    ack = action_id in st.session_state.ack_actions

    render_action_card(r, ack)

    if not ack:
        if st.button(f"✅ Action Taken – {r['Asset']}", key=f"ack_{i}"):
            st.session_state.ack_actions.add(action_id)
            st.rerun()

# ======================================================
# TABLES
# ======================================================
st.markdown("## 🔍 Detailed Findings")

with st.expander("🌡 Overcooled Zones"):
    st.dataframe(zone_flags, width="stretch")

with st.expander("🌀 AHU Energy Wastage"):
    st.dataframe(ahu_flags, width="stretch")

with st.expander("❄️ Chiller Low ΔT"):
    st.dataframe(chiller_flags, width="stretch")

# ======================================================
# DATA FRESHNESS
# ======================================================
age_min = int((datetime.now(tz) - now_local).total_seconds() / 60)
st.caption(f"📡 Data age: {age_min} minutes")
st.caption("⚠️ Advisory analytics only. No automated control actions performed.")
