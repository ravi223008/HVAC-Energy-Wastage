import streamlit as st
import time, json, os
from datetime import datetime
import pytz
from app_utils import load_latest_csv, preprocess, compute_analytics

# ---- CONFIG ----
cfg = json.load(open("assets/config.json"))
tz = pytz.timezone(cfg["timezone"])

st.set_page_config(layout="wide", page_title="HVAC Wallboard")

st.markdown("""
<style>
[data-testid="stSidebar"], header, footer { display:none; }
html, body { overflow:hidden; }
</style>
""", unsafe_allow_html=True)

df = load_latest_csv()
if df is None:
    st.error("No live data")
    st.stop()

df = preprocess(df)

params = {
    "ZONE_OVERCOOL_TOL": 1.0,
    "ZONE_SAT_TOL": 0.5,
    "AHU_AIRFLOW_HIGH": 60,
    "AHU_ZONE_SAT_RATIO": 0.8,
    "CHILLER_LOW_DT": 4.0,
    "COST_PER_KWH": 10
}

zone_flags, ahu_flags, chiller_flags = compute_analytics(df, params)

total_loss = (
    zone_flags["est_cost"].sum() +
    ahu_flags["est_cost"].sum() +
    chiller_flags["est_cost"].sum()
)

now_local = datetime.now(tz)

st.markdown(f"""
<div style="text-align:center; padding:30px;">
    <img src="assets/airport_logo.png" width="90"><br>
    <h1>{cfg["airport_name"]}</h1>
    <h3>{cfg["terminal_name"]} – HVAC ENERGY STATUS</h3>
    <p>{now_local.strftime('%d %b %Y • %H:%M %Z')}</p>
</div>
<hr>
""", unsafe_allow_html=True)

c1,c2,c3 = st.columns(3)
c1.metric("AHUs Wasting Energy", ahu_flags["ahu_id"].nunique())
c2.metric("Zones Overcooled", zone_flags["zone_id"].nunique())
c3.metric("Estimated Loss (₹)", f"{int(total_loss):,}")

time.sleep(300)
st.rerun()
