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

# Auto-refresh logic (15 minutes)
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if (time.time() - st.session_state.last_refresh) > 15 * 60:
    st.session_state.last_refresh = time.time()
    st.rerun()

# =====================================================================
# GMAIL SMTP ALERT SYSTEM (Using Secrets)
# =====================================================================
def send_gmail_alert(subject, html_body):
    """
    Sends an email using Gmail SMTP and Streamlit Secrets.
    Works on local Windows and Streamlit Cloud Linux.
    """
    try:
        # Pull credentials from secrets.toml or Cloud Secrets
        sender_email = st.secrets["gmail"]["user"]
        sender_password = st.secrets["gmail"]["password"]
        receiver_email = st.secrets["gmail"]["receiver"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() 
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True, "✅ Gmail Alert Sent Successfully"
    except Exception as e:
        return False, f"❌ Gmail Error: {str(e)}"

# =====================================================================
# HTML EMAIL TEMPLATES
# =====================================================================
def ghost_running_html(hours, total_cost, carbon):
    return f"""
    <div style="font-family: Arial, sans-serif; padding:20px; border:2px solid #f5b400; border-radius:10px;">
        <h2 style="color: #f5b400;">⚠️ Ghost Running Alert</h2>
        <p><b>Wasted Hours:</b> {hours} hrs</p>
        <p><b>Estimated Loss:</b> ₹{int(total_cost):,}</p>
        <p><b>Carbon Impact:</b> {int(carbon)} kg CO₂</p>
        <hr>
        <p style="font-size: 12px; color: #666;">This is an automated alert from HVAC Insight Pro.</p>
    </div>
    """

def overcooling_html(intervals, total_loss, avg_dt):
    return f"""
    <div style="font-family: Arial, sans-serif; padding:20px; border:2px solid #ff4d4d; border-radius:10px;">
        <h2 style="color: #ff4d4d;">❄️ Overcooling Alert</h2>
        <p><b>Fault Intervals:</b> {intervals}</p>
        <p><b>Cooling Waste:</b> ₹{int(total_loss):,}</p>
        <p><b>Avg Delta T:</b> {avg_dt:.1f}°C below setpoint</p>
        <hr>
        <p style="font-size: 12px; color: #666;">Corrective action recommended for stuck-open valves.</p>
    </div>
    """

# =====================================================================
# DATA HELPERS
# =====================================================================
@st.cache_data(ttl=60)
def load_latest_csv(folder):
    try:
        files = glob.glob(os.path.join(folder, "*.csv"))
        if not files: return None, None
        latest = max(files, key=os.path.getmtime)
        return pd.read_csv(latest), latest
    except: return None, None

def calculate_carbon(kwh): return kwh * 0.71

# =====================================================================
# SIDEBAR
# =====================================================================
st.sidebar.title("⚙️ Cloud Control Panel")

# RELATIVE PATH for GitHub/Cloud compatibility
BASE_PATH = st.sidebar.text_input("Data Folder Path", value="scenario_data/live")

cost_rate = st.sidebar.number_input("Rate (₹/kWh)", value=12.0)
cooling_factor = st.sidebar.number_input("Cooling Factor (₹/°C/hr)", value=150.0)

st.sidebar.subheader("Shift Schedule")
off_start = st.sidebar.slider("OFF Start Hour", 0, 23, 22)
off_end = st.sidebar.slider("OFF End Hour", 0, 23, 6)

st.sidebar.subheader("Alert Settings")
enable_email = st.sidebar.checkbox("Enable Gmail Alerts", value=False)
if st.sidebar.button("Send Test Email"):
    ok, msg = send_gmail_alert("HVAC Dashboard Test", "<h3>Connection Successful!</h3>")
    st.sidebar.write(msg)

# =====================================================================
# MAIN UI
# =====================================================================
st.title("✈️ Real-Time Unified HVAC Insight")

c1, c2 = st.columns([2, 1])
scenario = c1.selectbox("Module Selection:", ["Ghost Running", "Overcooling"])
view_mode = c2.radio("Persona View:", ["👔 Manager", "👷 Operator"], horizontal=True)

# Attempt Data Load
p_df, _ = load_latest_csv(os.path.join(BASE_PATH, "power"))
s_df, _ = load_latest_csv(os.path.join(BASE_PATH, "status"))
t_df, _ = load_latest_csv(os.path.join(BASE_PATH, "temp"))
v_df, _ = load_latest_csv(os.path.join(BASE_PATH, "valve"))

if any(x is None for x in [p_df, s_df, t_df, v_df]):
    st.error(f"⚠️ Data files not found at `{BASE_PATH}`. Please check your GitHub folder structure.")
    st.stop()

st.divider()

# =====================================================================
# SCENARIO 1: GHOST RUNNING
# =====================================================================
if scenario == "Ghost Running":
    p_df["T_Stamp"] = pd.to_datetime(p_df["T_Stamp"])
    p_df = p_df.set_index("T_Stamp").resample("1h").mean()
    s_df["Log_Time"] = pd.to_datetime(s_df["Log_Time"])
    s_df = s_df.set_index("Log_Time").resample("1h").ffill()
    
    df = pd.concat([p_df, s_df], axis=1).dropna()
    df.columns = ["Power_kW", "Status_Binary"]
    df["Actual_Status"] = df["Status_Binary"].apply(lambda x: "ON" if x > 0.5 else "OFF")
    df["Hour"] = df.index.hour
    
    # Overnight Schedule Logic
    if off_start > off_end:
        df["Schedule_Status"] = df["Hour"].apply(lambda h: "OFF" if (h >= off_start or h < off_end) else "ON")
    else:
        df["Schedule_Status"] = df["Hour"].apply(lambda h: "OFF" if (off_start <= h < off_end) else "ON")
    
    df["Energy_Cost"] = df["Power_kW"] * cost_rate
    waste_df = df[(df["Actual_Status"] == "ON") & (df["Schedule_Status"] == "OFF")]
    
    m = {
        "cost": waste_df["Energy_Cost"].sum(),
        "hours": len(waste_df),
        "monthly": waste_df["Energy_Cost"].sum() * 30,
        "trend7": len(waste_df.tail(7)),
        "carbon": calculate_carbon(waste_df["Power_kW"].sum())
    }

    if enable_email and m["hours"] >= 2:
        html = ghost_running_html(m["hours"], m["cost"], m["carbon"])
        ok, msg = send_gmail_alert("HVAC Alert: Ghost Running Detected", html)
        st.sidebar.info(msg)

    if "Manager" in view_mode:
        cols = st.columns(5)
        cols[0].metric("Waste Today", f"₹{int(m['cost']):,}")
        cols[1].metric("Hours Lost", f"{m['hours']} hrs")
        cols[2].metric("Monthly Proj.", f"₹{int(m['monthly']):,}")
        cols[3].metric("7D Trend", f"{m['trend7']} evts")
        cols[4].metric("CO₂ Impact", f"{int(m['carbon'])} kg", delta="Environment")
        st.bar_chart(df[["Energy_Cost"]])
    else:
        st.warning(f"Monitoring OFF-Hours: {off_start}:00 to {off_end}:00")
        st.dataframe(df, width="stretch")

    processed_df = df

# =====================================================================
# SCENARIO 2: OVERCOOLING
# =====================================================================
else:
    t_df["Timestamp"] = pd.to_datetime(t_df["Timestamp"])
    t_df = t_df.set_index("Timestamp").resample("15min").interpolate()
    v_df["Log_Time"] = pd.to_datetime(v_df["Log_Time"])
    v_df = v_df.set_index("Log_Time").resample("15min").ffill()
    
    df = pd.concat([t_df, v_df], axis=1).dropna()
    df.columns = ["Room_Temp", "Setpoint", "Valve_Pct"]
    df["Is_Fault"] = (df["Room_Temp"] < df["Setpoint"] - 1) & (df["Valve_Pct"] > 80)
    df["Delta_T"] = (df["Setpoint"] - df["Room_Temp"]).clip(0)
    df["Wasted_Cost"] = df["Delta_T"] * cooling_factor * df["Is_Fault"]
    
    m = {
        "loss": df["Wasted_Cost"].sum(),
        "avg_dt": df[df["Is_Fault"]]["Delta_T"].mean() if df["Is_Fault"].any() else 0,
        "monthly": df["Wasted_Cost"].sum() * 30,
        "trend7": df["Is_Fault"].tail(7).sum(),
        "carbon": calculate_carbon(df["Wasted_Cost"].sum() / 15)
    }

    if enable_email and m["loss"] > 500:
        html = overcooling_html(df["Is_Fault"].sum(), m["loss"], m["avg_dt"])
        ok, msg = send_gmail_alert("HVAC Alert: Overcooling Issue", html)
        st.sidebar.info(msg)

    if "Manager" in view_mode:
        cols = st.columns(5)
        cols[0].metric("Cooling Waste", f"₹{int(m['loss']):,}")
        cols[1].metric("Avg ΔT", f"{m['avg_dt']:.1f}°C")
        cols[2].metric("Monthly Proj.", f"₹{int(m['monthly']):,}")
        cols[3].metric("7D Trend", f"{m['trend7']} evts")
        cols[4].metric("CO₂ Impact", f"{int(m['carbon'])} kg")
        st.line_chart(df[["Room_Temp", "Setpoint"]])
    else:
        st.warning("Investigate Valve/Temp correlation for thermal efficiency.")
        st.line_chart(df[["Valve_Pct", "Room_Temp"]])
    
    processed_df = df

# =====================================================================
# SHARED EXPORT AREA
# =====================================================================
st.divider()
with st.expander("📥 Export Evidence Data & Detailed Table"):
    st.write(f"Showing raw data for: **{scenario}**")
    st.dataframe(processed_df, width="stretch") 
    st.download_button("Download Full CSV", processed_df.to_csv().encode("utf-8"), 
                       file_name=f"hvac_{scenario.lower().replace(' ','_')}.csv", mime="text/csv")

st.caption(f"Last Sync: {time.strftime('%H:%M:%S')} | Fleet Monitor v2.5")