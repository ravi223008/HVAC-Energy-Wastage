import streamlit as st
import pandas as pd
import numpy as np
import glob
import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from zipfile import ZipFile, ZIP_DEFLATED

# =====================================================================
# PAGE CONFIG & AUTO REFRESH
# =====================================================================
st.set_page_config(page_title="HVAC Insight Pro", layout="wide", page_icon="❄️")

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if (time.time() - st.session_state.last_refresh) > 15 * 60:
    st.session_state.last_refresh = time.time()
    st.rerun()

# =====================================================================
# UNIVERSAL SMTP EMAIL (Replaces Outlook win32com)
# =====================================================================
def send_email_alert(subject, html_body, to_email):
    """
    Universal SMTP sender that works on Linux (Streamlit Cloud) and Windows.
    Configure these in the Sidebar or Streamlit Secrets.
    """
    # These should ideally be moved to st.secrets for security
    smtp_server = st.sidebar.text_input("SMTP Server", "smtp.office365.com")
    smtp_port = st.sidebar.number_input("SMTP Port", value=587)
    smtp_user = st.sidebar.text_input("SMTP User (Email)", "your-email@example.com")
    smtp_password = st.sidebar.text_input("SMTP Password", type="password")

    if not smtp_password:
        return False, "SMTP Password missing."

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True, "Email Alert Sent successfully."
    except Exception as e:
        return False, f"Email Error: {str(e)}"

# =====================================================================
# HTML TEMPLATES (Kept your original styling)
# =====================================================================
def ghost_running_html(hours, total_cost, carbon):
    return f"""
    <div style="font-family: sans-serif; padding:20px; border:1px solid #eee; border-radius:10px;">
        <h2 style="color: #f5b400;">⚠️ Ghost Running Alert</h2>
        <p><b>Wasted Hours:</b> {hours}</p>
        <p><b>Today's Loss:</b> ₹{int(total_cost):,}</p>
        <p><b>CO₂ Impact:</b> {int(carbon)} kg</p>
    </div>
    """

def overcooling_html(intervals, total_loss, avg_dt, carbon):
    return f"""
    <div style="font-family: sans-serif; padding:20px; border:1px solid #eee; border-radius:10px;">
        <h2 style="color: #ff4d4d;">❄️ Overcooling Alert</h2>
        <p><b>Fault Intervals:</b> {intervals}</p>
        <p><b>Cooling Loss:</b> ₹{int(total_loss):,}</p>
        <p><b>Avg ΔT:</b> {avg_dt:.1f}°C</p>
    </div>
    """

# =====================================================================
# HELPERS & DATA LOADING
# =====================================================================
@st.cache_data(ttl=60)
def load_latest_csv(folder):
    try:
        # Use relative paths for GitHub/Cloud compatibility
        files = glob.glob(os.path.join(folder, "*.csv"))
        if not files: return None, None
        latest = max(files, key=os.path.getmtime)
        return pd.read_csv(latest), latest
    except: return None, None

def calculate_carbon_from_kwh(kwh): return kwh * 0.71

def archive_old_csvs(base_path, archive_path, age_hours):
    summary = {"zipped": 0, "errors": 0}
    for folder in ["power", "status", "temp", "valve"]:
        src = os.path.join(base_path, folder)
        if not os.path.exists(src): continue
        files = glob.glob(os.path.join(src, "*.csv"))
        for f in files:
            if (time.time() - os.path.getmtime(f)) > age_hours * 3600:
                try:
                    os.makedirs(archive_path, exist_ok=True)
                    zip_path = os.path.join(archive_path, f"{folder}_archive.zip")
                    with ZipFile(zip_path, "a", ZIP_DEFLATED) as zf:
                        zf.write(f, arcname=os.path.basename(f))
                    os.remove(f)
                    summary["zipped"] += 1
                except: summary["errors"] += 1
    return summary

# =====================================================================
# SIDEBAR & SETTINGS
# =====================================================================
st.sidebar.title("⚙️ Cloud Control Panel")

# FIXED: Default to a relative path for GitHub deployment
BASE_PATH = st.sidebar.text_input("Data Folder (Relative Path)", value="scenario_data/live")

cost_rate = st.sidebar.number_input("Rate (₹/kWh)", value=12.0)
cooling_factor = st.sidebar.number_input("Cooling Factor (₹/°C/hr)", value=150.0)

st.sidebar.subheader("Shift Schedule")
off_start = st.sidebar.slider("OFF Start", 0, 23, 22)
off_end = st.sidebar.slider("OFF End", 0, 23, 6)

st.sidebar.subheader("Alert Settings")
enable_email = st.sidebar.checkbox("Enable Alerts", value=False)
alert_to_email = st.sidebar.text_input("Recipient Email", "ops-team@airport.com")

# =====================================================================
# MAIN DASHBOARD
# =====================================================================
st.title("✈️ Real-Time Unified HVAC Insight")

col1, col2 = st.columns([2, 1])
scenario = col1.selectbox("Module:", ["Ghost Running", "Overcooling"])
view_mode = col2.radio("Persona:", ["👔 Manager", "👷 Operator"], horizontal=True)

# Attempt to load data
p_df, _ = load_latest_csv(os.path.join(BASE_PATH, "power"))
s_df, _ = load_latest_csv(os.path.join(BASE_PATH, "status"))
t_df, _ = load_latest_csv(os.path.join(BASE_PATH, "temp"))
v_df, _ = load_latest_csv(os.path.join(BASE_PATH, "valve"))

if any(x is None for x in [p_df, s_df, t_df, v_df]):
    st.error(f"Data not found at `{BASE_PATH}`. Please upload your CSVs to GitHub.")
    st.stop()

st.divider()

# Logic implementation is identical to your original, just using the new email function
if scenario == "Ghost Running":
    # (Your existing Ghost Running processing logic here...)
    # [Restoring Logic Summary]
    p_df["T_Stamp"] = pd.to_datetime(p_df["T_Stamp"])
    p_df = p_df.set_index("T_Stamp").resample("1h").mean()
    s_df["Log_Time"] = pd.to_datetime(s_df["Log_Time"])
    s_df = s_df.set_index("Log_Time").resample("1h").ffill()
    df = pd.concat([p_df, s_df], axis=1).dropna()
    df.columns = ["Power_kW", "Status_Binary"]
    df["Actual_Status"] = df["Status_Binary"].apply(lambda x: "ON" if x > 0.5 else "OFF")
    df["Hour"] = df.index.hour
    
    # Schedule Logic
    if off_start > off_end:
        df["Schedule_Status"] = df["Hour"].apply(lambda h: "OFF" if (h >= off_start or h < off_end) else "ON")
    else:
        df["Schedule_Status"] = df["Hour"].apply(lambda h: "OFF" if (off_start <= h < off_end) else "ON")
    
    df["Energy_Cost"] = df["Power_kW"] * cost_rate
    waste = df[(df["Actual_Status"] == "ON") & (df["Schedule_Status"] == "OFF")]
    
    m = {"hours": len(waste), "total_cost": waste["Energy_Cost"].sum(), "carbon": calculate_carbon_from_kwh(waste["Power_kW"].sum())}

    if enable_email and m["hours"] >= 2:
        html = ghost_running_html(m["hours"], m["total_cost"], m["carbon"])
        ok, msg = send_email_alert("HVAC Alert: Ghost Running", html, alert_to_email)
        st.sidebar.info(msg)

    # UI Rendering
    if "Manager" in view_mode:
        a, b, c = st.columns(3)
        a.metric("Waste Today", f"₹{int(m['total_cost']):,}")
        b.metric("Hours Lost", m["hours"])
        c.metric("CO₂ Impact", f"{int(m['carbon'])} kg")
        st.line_chart(df[["Energy_Cost"]])
    else:
        st.warning(f"Detection Active: {off_start}:00 to {off_end}:00")

    processed_df = df

else:
    # (Your existing Overcooling processing logic here...)
    t_df["Timestamp"] = pd.to_datetime(t_df["Timestamp"])
    t_df = t_df.set_index("Timestamp").resample("15min").interpolate()
    v_df["Log_Time"] = pd.to_datetime(v_df["Log_Time"])
    v_df = v_df.set_index("Log_Time").resample("15min").ffill()
    df = pd.concat([t_df, v_df], axis=1).dropna()
    df.columns = ["Room_Temp", "Setpoint", "Valve_Pct"]
    df["Is_Fault"] = (df["Room_Temp"] < df["Setpoint"] - 1) & (df["Valve_Pct"] > 80)
    df["Delta_T"] = (df["Setpoint"] - df["Room_Temp"]).clip(0)
    df["Wasted_Cost"] = df["Delta_T"] * cooling_factor * df["Is_Fault"]
    
    m = {"loss": df["Wasted_Cost"].sum(), "avg_dt": df[df["Is_Fault"]]["Delta_T"].mean() if df["Is_Fault"].any() else 0}

    if enable_email and m["loss"] > 500:
        html = overcooling_html(df["Is_Fault"].sum(), m["loss"], m["avg_dt"], 0)
        ok, msg = send_email_alert("HVAC Alert: Overcooling", html, alert_to_email)
        st.sidebar.info(msg)

    if "Manager" in view_mode:
        a, b = st.columns(2)
        a.metric("Cooling Waste", f"₹{int(m['loss']):,}")
        b.metric("Avg ΔT", f"{m['avg_dt']:.1f}°C")
        st.line_chart(df[["Room_Temp", "Setpoint"]])
    else:
        st.line_chart(df[["Valve_Pct", "Room_Temp"]])
    
    processed_df = df

# =====================================================================
# EXPORT
# =====================================================================
st.divider()
with st.expander("📥 Export Evidence Data"):
    st.dataframe(processed_df, width="stretch")
    st.download_button("Download CSV", processed_df.to_csv().encode("utf-8"), 
                       file_name="hvac_data.csv", mime="text/csv")

st.caption(f"Cloud Fleet Monitor | Last Sync: {time.strftime('%H:%M:%S')}")