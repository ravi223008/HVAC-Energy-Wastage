import streamlit as st
import pandas as pd
import numpy as np
import glob
import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =====================================================================
# PAGE CONFIG & AUTO REFRESH
# =====================================================================
st.set_page_config(
    page_title="Airport HVAC Loss & Efficiency Monitor",
    layout="wide",
    page_icon="✈️"
)

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if (time.time() - st.session_state.last_refresh) > 15 * 60:
    st.session_state.last_refresh = time.time()
    st.rerun()

# =====================================================================
# ALERT STATE TRACKING
# =====================================================================
if "ghost_alert_active" not in st.session_state:
    st.session_state.ghost_alert_active = False
if "cooling_alert_active" not in st.session_state:
    st.session_state.cooling_alert_active = False

# =====================================================================
# EMAIL ALERT SYSTEM
# =====================================================================
def send_gmail_alert(subject, html_body):
    try:
        sender_email = st.secrets["gmail"]["user"]
        sender_password = st.secrets["gmail"]["password"]
        receiver_email = st.secrets["gmail"]["receiver"]

        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        st.sidebar.error(f"Email alert failed: {e}")

# =====================================================================
# EMAIL TEMPLATES
# =====================================================================
def ghost_running_email(hours, cost, carbon):
    return f"""
    <h2>⚠️ HVAC Operating Outside Occupancy Hours</h2>
    <p><b>Unnecessary Runtime:</b> {hours} hours</p>
    <p><b>Estimated Cost Impact:</b> ₹{int(cost):,}</p>
    <p><b>CO₂ Impact:</b> {int(carbon)} kg</p>
    """

def overcooling_email(loss, avg_dt):
    return f"""
    <h2>❄️ Excess Cooling Detected</h2>
    <p><b>Estimated Cooling Loss:</b> ₹{int(loss):,}</p>
    <p><b>Average Temperature Deviation:</b> {avg_dt:.1f}°C below setpoint</p>
    """

# =====================================================================
# DATA HELPERS
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

def calculate_carbon(kwh):
    return kwh * 0.71

# =====================================================================
# EXPLAINABILITY
# =====================================================================
def explainability_manager(title, why, impact):
    with st.expander("🔍 Why this matters (Executive Explainability)"):
        st.markdown(f"### {title}")
        st.write(why)
        st.info(impact)

def explainability_operator(rules, signals, checks):
    with st.expander("🛠️ How this was detected (Operational Explainability)"):
        st.markdown("**Detection Rules Applied**")
        for r in rules:
            st.write(f"• {r}")
        st.markdown("**Signals Used**")
        for s in signals:
            st.write(f"• {s}")
        st.markdown("**What to Check in BMS**")
        for c in checks:
            st.write(f"• {c}")

# =====================================================================
# SIDEBAR
# =====================================================================
st.sidebar.title("⚙️ Operations Configuration")
BASE_PATH = st.sidebar.text_input("Live Data Folder Path", value="scenario_data/live")
cost_rate = st.sidebar.number_input("Electricity Cost Rate (₹/kWh)", value=12.0)
cooling_factor = st.sidebar.number_input("Cooling Penalty Cost (₹ / °C / hour)", value=150.0)
off_start = st.sidebar.slider("Non-Occupancy Start Hour", 0, 23, 22)
off_end = st.sidebar.slider("Non-Occupancy End Hour", 0, 23, 6)
enable_email = st.sidebar.checkbox("Enable Email Alerts", value=False)

# =====================================================================
# MAIN DASHBOARD
# =====================================================================
st.title("✈️ Airport HVAC Loss & Efficiency Monitor")
st.caption("Explainable, role-based HVAC loss detection for airports")

scenario = st.selectbox(
    "Select Operational Risk Scenario",
    [
        "🚨 HVAC Running Outside Occupancy Hours",
        "❄️ Excess Cooling / Control Inefficiency"
    ]
)

view_mode = st.radio(
    "Viewer Role",
    ["👔 Terminal / Facilities Manager", "🎛️ Control Room Operator"],
    horizontal=True
)

# =====================================================================
# DATA LOAD
# =====================================================================
p_df, _ = load_latest_csv(os.path.join(BASE_PATH, "power"))
s_df, _ = load_latest_csv(os.path.join(BASE_PATH, "status"))
t_df, _ = load_latest_csv(os.path.join(BASE_PATH, "temp"))
v_df, _ = load_latest_csv(os.path.join(BASE_PATH, "valve"))

if any(x is None for x in [p_df, s_df, t_df, v_df]):
    st.error("Required data feeds not detected.")
    st.stop()

st.divider()

# =====================================================================
# SCENARIO 1 — OUTSIDE OCCUPANCY
# =====================================================================
if "Outside Occupancy" in scenario:
    p_df["T_Stamp"] = pd.to_datetime(p_df["T_Stamp"])
    p_df = p_df.set_index("T_Stamp").resample("1h").mean()
    s_df["Log_Time"] = pd.to_datetime(s_df["Log_Time"])
    s_df = s_df.set_index("Log_Time").resample("1h").ffill()

    df = pd.concat([p_df, s_df], axis=1).dropna()
    df.columns = ["Power_kW", "Unit_Status"]

    df["Actual_Status"] = np.where(df["Unit_Status"] > 0.5, "ON", "OFF")
    df["Hour"] = df.index.hour

    if off_start > off_end:
        df["Scheduled_Status"] = df["Hour"].apply(lambda h: "OFF" if (h >= off_start or h < off_end) else "ON")
    else:
        df["Scheduled_Status"] = df["Hour"].apply(lambda h: "OFF" if (off_start <= h < off_end) else "ON")

    df["Energy_Cost"] = df["Power_kW"] * cost_rate
    waste_df = df[(df["Actual_Status"] == "ON") & (df["Scheduled_Status"] == "OFF")]

    condition_active = len(waste_df) >= 2
    if enable_email and condition_active and not st.session_state.ghost_alert_active:
        send_gmail_alert(
            "HVAC Alert: Running Outside Occupancy Hours",
            ghost_running_email(
                len(waste_df),
                waste_df["Energy_Cost"].sum(),
                calculate_carbon(waste_df["Power_kW"].sum())
            )
        )
        st.session_state.ghost_alert_active = True
    if not condition_active:
        st.session_state.ghost_alert_active = False

    # ===== MANAGER VIEW =====
    if "Manager" in view_mode:
        st.info(
            "This condition resulted in avoidable HVAC energy cost during non-operational hours."
        )

        st.metric(
            "Primary Impact: Estimated Cost Loss",
            f"₹{int(waste_df['Energy_Cost'].sum()):,}"
        )

        cols = st.columns(3)
        cols[0].metric("Projected Monthly Loss", f"₹{int(waste_df['Energy_Cost'].sum()*30):,}")
        cols[1].metric("Unnecessary Runtime", f"{len(waste_df)} hrs")
        cols[2].metric("CO₂ Impact", f"{int(calculate_carbon(waste_df['Power_kW'].sum()))} kg")

        st.bar_chart(df["Energy_Cost"])

        explainability_manager(
            "HVAC Operating Outside Occupancy Hours",
            "HVAC units were running during scheduled non-occupancy hours.",
            "These losses accumulate silently and inflate operational energy spend."
        )

    # ===== OPERATOR VIEW =====
    else:
        st.warning("Immediate Attention Required")

        st.markdown("### ✅ Recommended Check Sequence")
        st.markdown(
            """
            1. Verify AHU runtime in BMS  
            2. Confirm no manual or night-purge override  
            3. Validate occupancy schedule configuration  
            """
        )

        st.line_chart(df["Power_kW"])
        st.dataframe(df[["Power_kW", "Actual_Status", "Scheduled_Status"]], width="stretch")

        explainability_operator(
            ["Unit status = ON", "Scheduled status = OFF", "Power draw above idle"],
            ["Power meter", "ON/OFF status", "Occupancy schedule"],
            ["Check AHU runtime", "Verify overrides", "Confirm schedule"]
        )

    processed_df = df

# =====================================================================
# SCENARIO 2 — EXCESS COOLING
# =====================================================================
else:
    t_df["Timestamp"] = pd.to_datetime(t_df["Timestamp"])
    t_df = t_df.set_index("Timestamp").resample("15min").interpolate()
    v_df["Log_Time"] = pd.to_datetime(v_df["Log_Time"])
    v_df = v_df.set_index("Log_Time").resample("15min").ffill()

    df = pd.concat([t_df, v_df], axis=1).dropna()
    df.columns = ["Room_Temp", "Setpoint", "Valve_Position"]

    df["Fault"] = (df["Room_Temp"] < df["Setpoint"] - 1) & (df["Valve_Position"] > 80)
    df["Delta_T"] = (df["Setpoint"] - df["Room_Temp"]).clip(0)
    df["Cooling_Loss"] = df["Delta_T"] * cooling_factor * df["Fault"]

    condition_active = df["Cooling_Loss"].sum() >= 500
    if enable_email and condition_active and not st.session_state.cooling_alert_active:
        send_gmail_alert(
            "HVAC Alert: Excess Cooling Detected",
            overcooling_email(
                df["Cooling_Loss"].sum(),
                df[df["Fault"]]["Delta_T"].mean() if df["Fault"].any() else 0
            )
        )
        st.session_state.cooling_alert_active = True
    if not condition_active:
        st.session_state.cooling_alert_active = False

    # ===== MANAGER VIEW =====
    if "Manager" in view_mode:
        st.info(
            "This condition indicates inefficient cooling control leading to continuous energy waste."
        )

        st.metric(
            "Primary Impact: Estimated Cooling Loss",
            f"₹{int(df['Cooling_Loss'].sum()):,}"
        )

        cols = st.columns(3)
        cols[0].metric("Projected Monthly Loss", f"₹{int(df['Cooling_Loss'].sum()*30):,}")
        cols[1].metric("Avg Temp Deviation", f"{df[df['Fault']]['Delta_T'].mean():.1f}°C")
        cols[2].metric("CO₂ Impact", f"{int(calculate_carbon(df['Cooling_Loss'].sum()/15))} kg")

        st.line_chart(df[["Room_Temp", "Setpoint"]])

        explainability_manager(
            "Excess Cooling / Control Inefficiency",
            "Spaces were cooled below setpoint while cooling valves remained open.",
            "This typically indicates control or actuator inefficiency."
        )

    # ===== OPERATOR VIEW =====
    else:
        st.warning("Immediate Attention Required")

        st.markdown("### ✅ Recommended Check Sequence")
        st.markdown(
            """
            1. Inspect cooling valve actuator  
            2. Check control loop tuning  
            3. Validate temperature sensor calibration  
            """
        )

        st.line_chart(df[["Valve_Position", "Room_Temp"]])
        st.dataframe(df[["Room_Temp", "Setpoint", "Valve_Position", "Fault"]], width="stretch")

        explainability_operator(
            ["Temp < setpoint", "Valve > 80%", "Sustained condition"],
            ["Temperature sensor", "Setpoint", "Valve feedback"],
            ["Inspect valve", "Check control loop", "Validate sensors"]
        )

    processed_df = df

# =====================================================================
# EXPORT
# =====================================================================
st.divider()
with st.expander("📥 Download Evidence & Audit Records"):
    st.dataframe(processed_df, width="stretch")
    st.download_button(
        "Download CSV Evidence File",
        processed_df.to_csv().encode("utf-8"),
        file_name="hvac_explainable_evidence.csv",
        mime="text/csv"
    )

st.caption(f"Last Sync: {time.strftime('%H:%M:%S')} | Explainable, Role-Aware Monitoring")
