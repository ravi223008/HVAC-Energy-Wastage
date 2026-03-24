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
import matplotlib.pyplot as plt

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
# EMAIL FUNCTION
# =====================================================================
def send_gmail_alert(subject, html_body):
    try:
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
        return True
    except:
        return False

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

def calculate_carbon(kwh):
    return kwh * 0.71

# =====================================================================
# SIDEBAR
# =====================================================================
st.sidebar.title("⚙️ Control Panel")

BASE_PATH = st.sidebar.text_input("Data Folder Path", value="scenario_data/live")

cost_rate = st.sidebar.number_input("Rate (₹/kWh)", value=12.0)
cooling_factor = st.sidebar.number_input("Cooling Factor", value=150.0)

off_start = st.sidebar.slider("OFF Start Hour", 0, 23, 22)
off_end = st.sidebar.slider("OFF End Hour", 0, 23, 6)

# =====================================================================
# MAIN UI
# =====================================================================
st.title("✈️ HVAC Insight Dashboard")

scenario = st.selectbox("Scenario", ["Ghost Running", "Overcooling"])
view_mode = st.radio("View", ["Manager", "Operator"])

# Load data
p_df, _ = load_latest_csv(os.path.join(BASE_PATH, "power"))
s_df, _ = load_latest_csv(os.path.join(BASE_PATH, "status"))
t_df, _ = load_latest_csv(os.path.join(BASE_PATH, "temp"))
v_df, _ = load_latest_csv(os.path.join(BASE_PATH, "valve"))

if any(x is None for x in [p_df, s_df, t_df, v_df]):
    st.error("Data not found")
    st.stop()

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
        "carbon": calculate_carbon(waste_df["Power_kW"].sum())
    }

    if view_mode == "Manager":

        st.metric("Waste Today", f"₹{int(m['cost'])}")
        st.metric("Hours Lost", f"{m['hours']} hrs")
        st.metric("Monthly", f"₹{int(m['monthly'])}")
        st.metric("CO₂", f"{int(m['carbon'])} kg")

        # Original chart
        st.bar_chart(df["Energy_Cost"])

        # 🔥 NEW ANALYTICS GRAPH
        fig, ax = plt.subplots(figsize=(12, 5))

        ax.plot(df.index, df["Power_kW"], label="Power")

        off_mask = df["Schedule_Status"] == "OFF"
        ax.fill_between(df.index, 0, df["Power_kW"],
                        where=off_mask, alpha=0.2, label="OFF Schedule")

        waste_mask = (df["Actual_Status"] == "ON") & (df["Schedule_Status"] == "OFF")
        ax.scatter(df.index[waste_mask],
                   df["Power_kW"][waste_mask],
                   color="red", label="Waste")

        ax.legend()
        ax.set_title("Energy vs Schedule")

        st.pyplot(fig)

        st.info(f"⚠️ {m['hours']} hours potential waste detected")

    else:
        st.dataframe(df)

# =====================================================================
# SCENARIO 2: OVERCOOLING
# =====================================================================
elif scenario == "Overcooling":

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
        "monthly": df["Wasted_Cost"].sum() * 30,
        "carbon": calculate_carbon(df["Wasted_Cost"].sum() / 15)
    }

    if view_mode == "Manager":
        st.metric("Cooling Waste", f"₹{int(m['loss'])}")
        st.metric("Monthly", f"₹{int(m['monthly'])}")
        st.metric("CO₂", f"{int(m['carbon'])}")

        st.line_chart(df[["Room_Temp", "Setpoint"]])

    else:
        st.line_chart(df[["Valve_Pct", "Room_Temp"]])

# =====================================================================
# EXPORT
# =====================================================================
st.download_button(
    "Download CSV",
    df.to_csv().encode(),
    file_name="hvac.csv"
)