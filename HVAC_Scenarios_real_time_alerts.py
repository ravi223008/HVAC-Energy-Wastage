
import streamlit as st
import pandas as pd
import numpy as np
import glob
import os
import time
from zipfile import ZipFile, ZIP_DEFLATED

# Outlook COM
import pythoncom
import win32com.client as win32


# =====================================================================
# PAGE CONFIG & AUTO REFRESH
# =====================================================================
st.set_page_config(page_title="HVAC Insight Pro", layout="wide", page_icon="❄️")

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if (time.time() - st.session_state.last_refresh) > 15 * 60:  # 15 min
    st.session_state.last_refresh = time.time()
    st.rerun()


# =====================================================================
# OUTLOOK HTML EMAIL (thread‑safe)
# =====================================================================
def send_outlook_email(subject, html_body, to_email):
    """
    Thread‑safe Outlook HTML sender for Streamlit.
    Uses COM Initialize / Uninitialize.
    """

    try:
        pythoncom.CoInitialize()

        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)

        mail.To = to_email
        mail.Subject = subject
        mail.HTMLBody = html_body  # send HTML formatted email

        mail.Send()

        pythoncom.CoUninitialize()
        return True, "Outlook email sent."

    except Exception as e:
        pythoncom.CoUninitialize()
        return False, f"Outlook send error: {e}"


# =====================================================================
# FORMATTED HTML TEMPLATES
# =====================================================================
def ghost_running_html(hours, total_cost, carbon):
    return f"""
<html>
<head>
<style>
body {{
    font-family: Segoe UI, Arial, sans-serif;
    color:#333; font-size:14px;
}}
.container {{
    padding:18px; border:1px solid #e5e5e5;
    border-radius:8px; max-width:480px;
}}
.title {{
    font-size:20px; font-weight:600; margin-bottom:10px;
}}
.alert {{
    border-left:4px solid #f5b400;
    padding:10px 14px; background:#fff8e1;
    margin-bottom:16px;
}}
.metric {{ margin-top:6px; font-size:15px; }}
</style>
</head>
<body>
<div class="container">
    <div class="title">Ghost Running Alert</div>

    <div class="alert">
        ⚠️ <b>Ghost Running Detected</b><br><br>
    </div>

    <div class="metric"><b>Wasted Hours:</b> {hours}</div>
    <div class="metric"><b>Today's Loss:</b> ₹{int(total_cost):,}</div>
    <div class="metric"><b>CO₂ Impact:</b> {int(carbon)} kg</div>
</div>
</body>
</html>
"""


def overcooling_html(intervals, total_loss, avg_dt, carbon):
    return f"""
<html>
<head>
<style>
body {{
    font-family: Segoe UI, Arial, sans-serif;
    color:#333; font-size:14px;
}}
.container {{
    padding:18px; border:1px solid #e5e5e5;
    border-radius:8px; max-width:480px;
}}
.title {{
    font-size:20px; font-weight:600; margin-bottom:10px;
}}
.alert {{
    border-left:4px solid #ff4d4d;
    padding:10px 14px; background:#fff2f2;
    margin-bottom:16px;
}}
.metric {{ margin-top:6px; font-size:15px; }}
</style>
</head>
<body>
<div class="container">
    <div class="title">Overcooling Alert</div>

    <div class="alert">
        ❄️ <b>Overcooling Detected</b><br><br>
        Cooling valve open while temperature below setpoint.
    </div>

    <div class="metric"><b>Fault Intervals:</b> {intervals}</div>
    <div class="metric"><b>Cooling Loss Today:</b> ₹{int(total_loss):,}</div>
    <div class="metric"><b>Avg ΔT:</b> {avg_dt:.1f}°C</div>
    <div class="metric"><b>CO₂ Impact:</b> {int(carbon)} kg</div>
</div>
</body>
</html>
"""


# =====================================================================
# HELPERS
# =====================================================================
@st.cache_data(ttl=60)
def load_latest_csv(folder):
    try:
        files = glob.glob(os.path.join(folder, "*.csv"))
        if not files:
            return None, None
        latest = max(files, key=os.path.getmtime)
        return pd.read_csv(latest), latest
    except:
        return None, None


def calculate_carbon_from_kwh(kwh): 
    return kwh * 0.71


def folder_exists(path): 
    return os.path.exists(path) and os.path.isdir(path)


# =====================================================================
# AUTO ARCHIVE
# =====================================================================
def is_stale(file_path, age_hours):
    try:
        return (time.time() - os.path.getmtime(file_path)) > age_hours * 3600
    except:
        return False


def archive_old_csvs(base_path, archive_path, age_hours):
    summary = {"moved": 0, "zipped": 0, "skipped": 0, "errors": 0}

    for folder in ["power", "status", "temp", "valve"]:
        src = os.path.join(base_path, folder)
        if not folder_exists(src):
            summary["errors"] += 1
            continue

        files = glob.glob(os.path.join(src, "*.csv"))

        for f in files:
            if not is_stale(f, age_hours):
                summary["skipped"] += 1
                continue

            mtime = time.localtime(os.path.getmtime(f))
            yyyy = time.strftime("%Y", mtime)
            ymd  = time.strftime("%Y-%m-%d", mtime)

            dst_dir = os.path.join(archive_path, folder, yyyy, ymd)
            os.makedirs(dst_dir, exist_ok=True)

            zip_path = os.path.join(dst_dir, f"{ymd}.zip")
            try:
                with ZipFile(zip_path, "a", ZIP_DEFLATED) as zf:
                    zf.write(f, arcname=os.path.basename(f))
                os.remove(f)
                summary["zipped"] += 1
            except:
                summary["errors"] += 1

    return summary


# =====================================================================
# SIDEBAR
# =====================================================================
st.sidebar.title("⚙️ Control Panel")

BASE_PATH = st.sidebar.text_input("Live Data Folder",
                                  value=r"D:\Energy_MVP\final\scenario_data\live")

for f in ["power", "status", "temp", "valve"]:
    if not folder_exists(os.path.join(BASE_PATH, f)):
        st.sidebar.error(f"Missing: {os.path.join(BASE_PATH, f)}")
        st.stop()

cost_rate = st.sidebar.number_input("Rate (₹/kWh)", value=12.0)
cooling_factor = st.sidebar.number_input("Cooling Factor (₹/°C/hr)", value=150.0)

st.sidebar.subheader("Shift Schedule (Ghost Running)")
off_start = st.sidebar.slider("OFF Start", 0, 23, 22)
off_end   = st.sidebar.slider("OFF End",   0, 23, 6)

st.sidebar.subheader("Archiving")
archive_age = st.sidebar.number_input("Archive CSV older than (hours)",
                                      min_value=1, value=24)
archive_path = st.sidebar.text_input("Archive Path",
                                     value=os.path.join(BASE_PATH, "_archive"))
auto_archive = st.sidebar.checkbox("Auto Archive on Refresh", value=True)

if st.sidebar.button("Archive Now"):
    st.sidebar.write(archive_old_csvs(BASE_PATH, archive_path, archive_age))

if auto_archive:
    archive_old_csvs(BASE_PATH, archive_path, archive_age)


st.sidebar.subheader("Outlook Alerts")
enable_email = st.sidebar.checkbox("Enable Alerts", value=False)
alert_to_email = st.sidebar.text_input("Send To", "ops-team@airport.com")


# =====================================================================
# MAIN UI
# =====================================================================
st.title("✈️ Real-Time Unified HVAC Insight")

col1, col2 = st.columns([2, 1])
scenario = col1.selectbox("Module:", ["Ghost Running", "Overcooling"])
view_mode = col2.radio("Persona:", ["👔 Manager", "👷 Operator"], horizontal=True)

# Load data
p_df, _ = load_latest_csv(os.path.join(BASE_PATH, "power"))
s_df, _ = load_latest_csv(os.path.join(BASE_PATH, "status"))
t_df, _ = load_latest_csv(os.path.join(BASE_PATH, "temp"))
v_df, _ = load_latest_csv(os.path.join(BASE_PATH, "valve"))

st.divider()


# =====================================================================
# SCENARIO 1 — GHOST RUNNING
# =====================================================================
if scenario == "Ghost Running":

    if p_df is None or s_df is None:
        st.error("Missing power or status CSVs.")
        st.stop()

    p_df["T_Stamp"] = pd.to_datetime(p_df["T_Stamp"])
    p_df = p_df.set_index("T_Stamp").resample("1h").mean()

    s_df["Log_Time"] = pd.to_datetime(s_df["Log_Time"])
    s_df = s_df.set_index("Log_Time").resample("1h").ffill()

    df = pd.concat([p_df, s_df], axis=1).dropna()
    df.columns = ["Power_kW", "Status_Binary"]

    df["Actual_Status"] = df["Status_Binary"].apply(lambda x: "ON" if x > 0.5 else "OFF")
    df["Hour"] = df.index.hour

    if off_start > off_end:
        df["Schedule_Status"] = df["Hour"].apply(
            lambda h: "OFF" if (h >= off_start or h < off_end) else "ON")
    else:
        df["Schedule_Status"] = df["Hour"].apply(
            lambda h: "OFF" if (off_start <= h < off_end) else "ON")

    df["Energy_Cost"] = df["Power_kW"] * cost_rate
    waste = df[(df["Actual_Status"] == "ON") & (df["Schedule_Status"] == "OFF")]

    total_cost = waste["Energy_Cost"].sum()
    kwh = waste["Power_kW"].sum()
    carbon = calculate_carbon_from_kwh(kwh)

    metrics = {
        "hours": len(waste),
        "total_cost": total_cost,
        "trend7": len(waste.tail(7)),
        "monthly": total_cost * 30,
        "carbon": carbon
    }

    # ALERT
    if enable_email and metrics["hours"] >= 2:
        html = ghost_running_html(metrics["hours"], metrics["total_cost"], metrics["carbon"])
        ok, msg = send_outlook_email("Ghost Running Alert", html, alert_to_email)
        st.sidebar.write("Email:", "Sent" if ok else msg)

    # Manager UI
    if "Manager" in view_mode:
        a, b, c, d, e = st.columns(5)
        a.metric("Waste Today", f"₹{int(metrics['total_cost']):,}")
        b.metric("Hours Lost", metrics["hours"])
        c.metric("Monthly Proj", f"₹{int(metrics['monthly']):,}")
        d.metric("7‑Day Trend", metrics["trend7"])
        e.metric("CO₂ Impact", f"{int(metrics['carbon'])} kg")

    else:
        st.warning(f"Scheduled OFF: {off_start}:00 → {off_end}:00")
        st.info("Check AHU local panel → Set to AUTO")

    st.line_chart(df[["Energy_Cost"]])
    processed_df = df


# =====================================================================
# SCENARIO 2 — OVERCOOLING
# =====================================================================
else:

    if t_df is None or v_df is None:
        st.error("Missing temperature or valve CSVs.")
        st.stop()

    t_df["Timestamp"] = pd.to_datetime(t_df["Timestamp"])
    t_df = t_df.set_index("Timestamp").resample("15min").interpolate()

    v_df["Log_Time"] = pd.to_datetime(v_df["Log_Time"])
    v_df = v_df.set_index("Log_Time").resample("15min").ffill()

    df = pd.concat([t_df, v_df], axis=1).dropna()
    df.columns = ["Room_Temp", "Setpoint", "Valve_Pct"]

    df["Is_Fault"] = (df["Room_Temp"] < df["Setpoint"] - 1) & (df["Valve_Pct"] > 80)
    df["Delta_T"] = (df["Setpoint"] - df["Room_Temp"]).clip(0)
    df["Wasted_Cost"] = df["Delta_T"] * cooling_factor * df["Is_Fault"]

    total_loss = df["Wasted_Cost"].sum()
    kwh_equiv = total_loss / cost_rate if cost_rate > 0 else 0
    carbon = calculate_carbon_from_kwh(kwh_equiv)

    metrics = {
        "intervals": df["Is_Fault"].sum(),
        "total_loss": total_loss,
        "avg_dt": df[df["Is_Fault"]]["Delta_T"].mean() if df["Is_Fault"].any() else 0,
        "trend7": df["Is_Fault"].tail(7).sum(),
        "monthly": total_loss * 30,
        "carbon": carbon
    }

    # ALERT
    if enable_email and metrics["total_loss"] > 500:
        html = overcooling_html(
            metrics["intervals"],
            metrics["total_loss"],
            metrics["avg_dt"],
            metrics["carbon"]
        )
        ok, msg = send_outlook_email("Overcooling Alert", html, alert_to_email)
        st.sidebar.write("Email:", "Sent" if ok else msg)

    # UI
    if "Manager" in view_mode:
        a, b, c, d, e = st.columns(5)
        a.metric("Cooling Waste", f"₹{int(metrics['total_loss']):,}")
        b.metric("Avg ΔT", f"{metrics['avg_dt']:.1f}°C")
        c.metric("Monthly Proj", f"₹{int(metrics['monthly']):,}")
        d.metric("7‑Day Trend", metrics["trend7"])
        e.metric("CO₂ Impact", f"{int(metrics['carbon'])} kg")

        st.line_chart(df[["Room_Temp", "Setpoint"]])

    else:
        st.warning("Cooling valve OPEN while room BELOW setpoint.")
        st.line_chart(df[["Valve_Pct", "Room_Temp"]])

    processed_df = df


# =====================================================================
# EXPORT
# =====================================================================
st.divider()
with st.expander("📥 Export Evidence Data"):
    st.dataframe(processed_df, width="stretch")
    csv_data = processed_df.to_csv().encode("utf-8")
    st.download_button("Download CSV",
                       csv_data,
                       file_name=f"hvac_{scenario.lower().replace(' ', '_')}.csv",
                       mime="text/csv")

st.caption(f"Last refresh: {time.strftime('%H:%M:%S')} — HVAC Insight Pro (Outlook Alerts)")
