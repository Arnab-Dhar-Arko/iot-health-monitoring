import os
import io
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(
    page_title="IoT Health Monitoring – Decision Support",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# Helpers
# ----------------------------
REQUIRED_COLS = ["Time", "HR (bpm)", "SpO₂ (%)", "Temp (°C)"]

def compute_status(hr, spo2, temp, thr_hr=120, thr_spo2=90, thr_temp=38.0):
    """Clinical rule-based status."""
    try:
        if float(hr) > float(thr_hr):
            return "High Heart Rate Alert"
        if float(spo2) < float(thr_spo2):
            return "Low Oxygen Alert"
        if float(temp) > float(thr_temp):
            return "Fever Alert"
        return "Normal"
    except Exception:
        return "Normal"

@st.cache_data(show_spinner=False)
def load_csv(path_or_file) -> pd.DataFrame:
    try:
        df = pd.read_csv(path_or_file)
    except Exception:
        df = pd.read_csv(path_or_file, sep=";")

    # Validate required columns
    for c in REQUIRED_COLS:
        if c not in df.columns:
            raise ValueError(f"CSV missing required column: {c}")

    # Parse time & sort
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df = df.dropna(subset=["Time"]).sort_values("Time").reset_index(drop=True)

    # Coerce numerics & clip plausible ranges
    df["HR (bpm)"]   = pd.to_numeric(df["HR (bpm)"], errors="coerce").clip(lower=30, upper=220)
    df["SpO₂ (%)"]   = pd.to_numeric(df["SpO₂ (%)"], errors="coerce").clip(lower=50, upper=100)
    df["Temp (°C)"]  = pd.to_numeric(df["Temp (°C)"], errors="coerce").clip(lower=33, upper=43)
    return df

def plot_timeseries(df: pd.DataFrame, ycol: str, title: str, ylabel: str, alert_mask: pd.Series):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["Time"], df[ycol], label=ycol)
    if alert_mask is not None and alert_mask.any():
        ax.scatter(df.loc[alert_mask, "Time"], df.loc[alert_mask, ycol], marker="o", c="red")
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig

# ----------------------------
# Sidebar (data + thresholds)
# ----------------------------
st.sidebar.title("Controls")

default_path = os.path.join(os.path.dirname(__file__), "iot_health_data.csv")
uploaded = st.sidebar.file_uploader("Upload CSV (optional)", type=["csv"])
st.sidebar.caption("Expected columns: Time, HR (bpm), SpO₂ (%), Temp (°C) [Status optional]")

st.sidebar.markdown("---")
st.sidebar.caption("Clinical thresholds (adjust as needed)")
thr_hr = st.sidebar.number_input("HR alert if > bpm", 60, 220, 120, step=1)
thr_spo2 = st.sidebar.number_input("SpO₂ alert if < %", 70, 100, 90, step=1)
thr_temp = st.sidebar.number_input("Temp alert if > °C", 35.0, 42.0, 38.0, step=0.1)

# ----------------------------
# Load data
# ----------------------------
if uploaded is not None:
    df = load_csv(uploaded)
else:
    if not os.path.exists(default_path):
        st.error(f"Dataset not found: {default_path}")
        st.stop()
    df = load_csv(default_path)

# Compute/refresh Status based on current thresholds
df["Status"] = df.apply(lambda x: compute_status(
    x["HR (bpm)"], x["SpO₂ (%)"], x["Temp (°C)"], thr_hr, thr_spo2, thr_temp
), axis=1)

alerts = df[df["Status"] != "Normal"].copy()

# ----------------------------
# Header + KPIs
# ----------------------------
st.title("IoT Health Monitoring – Decision Support Dashboard")
st.caption("Student: Arnab Dhar · Prototype dashboard for thesis")
st.caption(f"Run timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Records", f"{len(df):,}")
k2.metric("Total Alerts", f"{len(alerts):,}")
k3.metric("Avg HR (bpm)", f"{df['HR (bpm)'].mean():.1f}")
k4.metric("Avg SpO₂ (%)", f"{df['SpO₂ (%)'].mean():.1f}")

# KPI export
kpi_df = pd.DataFrame([{
    "total_records": len(df),
    "total_alerts": len(alerts),
    "avg_hr_bpm": round(df["HR (bpm)"].mean(), 1),
    "avg_spo2_pct": round(df["SpO₂ (%)"].mean(), 1),
    "avg_temp_c": round(df["Temp (°C)"].mean(), 1)
}])
st.download_button(
    "Download KPI summary (CSV)",
    kpi_df.to_csv(index=False),
    file_name="kpi_summary.csv",
    mime="text/csv"
)

# ----------------------------
# Dataset preview
# ----------------------------
st.subheader("Dataset Preview")
st.dataframe(df.head(12), use_container_width=True)

# ----------------------------
# Plots row
# ----------------------------
st.subheader("Time-Series Plots (alerts highlighted)")

c1, c2, c3 = st.columns(3)

with c1:
    hr_alert_mask = (df["Status"] == "High Heart Rate Alert")
    fig_hr = plot_timeseries(df, "HR (bpm)", "Heart Rate", "HR (bpm)", hr_alert_mask)
    st.pyplot(fig_hr)

with c2:
    spo2_alert_mask = (df["Status"] == "Low Oxygen Alert")
    fig_spo2 = plot_timeseries(df, "SpO₂ (%)", "SpO₂", "SpO₂ (%)", spo2_alert_mask)
    st.pyplot(fig_spo2)

with c3:
    temp_alert_mask = (df["Status"] == "Fever Alert")
    fig_temp = plot_timeseries(df, "Temp (°C)", "Temperature", "Temp (°C)", temp_alert_mask)
    st.pyplot(fig_temp)

# ----------------------------
# Alerts breakdown + table
# ----------------------------
st.subheader("Alerts Breakdown")
if len(alerts):
    st.bar_chart(alerts["Status"].value_counts())
else:
    st.info("No alerts at current thresholds.")

st.subheader("Alerts Table")
st.dataframe(alerts, use_container_width=True)

# Save + download alerts
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
alerts_path = os.path.join(os.path.dirname(__file__), f"iot_health_alerts_{stamp}.csv")
alerts.to_csv(alerts_path, index=False, encoding="utf-8")
st.caption(f"Alerts also saved to: {alerts_path}")

csv_buf = io.StringIO()
alerts.to_csv(csv_buf, index=False)
st.download_button(
    "Download alerts as CSV",
    csv_buf.getvalue(),
    file_name=f"iot_health_alerts_{stamp}.csv",
    mime="text/csv"
)

# ----------------------------
# Extra: HR anomaly detection (statistical)
# ----------------------------
st.subheader("HR Statistical Anomalies (rolling z-score > 3)")
win = 12  # adjust depending on sample interval
hr = df["HR (bpm)"]
roll_mean = hr.rolling(win, min_periods=win).mean()
roll_std  = hr.rolling(win, min_periods=win).std()
z = (hr - roll_mean) / roll_std
anomaly = (np.abs(z) > 3)

fig_a, ax_a = plt.subplots(figsize=(10, 4))
ax_a.plot(df["Time"], hr, label="HR (bpm)")
ax_a.scatter(df["Time"][anomaly], hr[anomaly], marker="^", c="orange")
ax_a.set_xlabel("Time")
ax_a.set_ylabel("HR (bpm)")
ax_a.set_title("HR Anomalies (Z-score > 3)")
fig_a.tight_layout()
st.pyplot(fig_a)

st.caption("Tip: Adjust thresholds in the sidebar or upload a new CSV to re-run analysis.")
