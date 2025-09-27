import io
from datetime import datetime

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from utils import compute_status, plot_timeseries, validate_csv_columns
from db import init_db, list_patients, get_patient_thresholds, upsert_patient_thresholds
from db import save_dataset_to_db, load_observations, list_alerts, record_alerts
from alerts import send_email  # SMS optional

st.set_page_config(
    page_title="IoT Health Monitoring – Decision Support",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# Bootstrap DB (SQLite by default)
# ----------------------------
init_db()  # idempotent

# ----------------------------
# Sidebar controls
# ----------------------------
st.sidebar.title("Controls")

# Patient selection (demo patients created on first save)
patients = list_patients()
if len(patients) == 0:
    st.sidebar.warning("No patients in DB yet. Upload CSV below to create one (Patient ID will be 'P001').")

patient_id = st.sidebar.selectbox(
    "Patient",
    options=[p["id"] for p in patients] if patients else [],
    format_func=lambda pid: next((p["name"] for p in patients if p["id"] == pid), pid)
) if patients else None

# Upload data
uploaded = st.sidebar.file_uploader("Upload CSV (Time, HR (bpm), SpO₂ (%), Temp (°C))", type=["csv"])
st.sidebar.caption("If empty, you can still view stored data (once saved before).")

# Thresholds (fallback defaults if no patient selected yet)
defaults = {"hr_high": 120, "spo2_low": 90, "temp_high": 38.0}
thr = get_patient_thresholds(patient_id) if patient_id else defaults
hr_thr = st.sidebar.number_input("HR alert if > bpm", 60, 220, int(thr["hr_high"]))
spo2_thr = st.sidebar.number_input("SpO₂ alert if < %", 70, 100, int(thr["spo2_low"]))
temp_thr = st.sidebar.number_input("Temp alert if > °C", 35.0, 42.0, float(thr["temp_high"]))

if patient_id and (hr_thr != thr["hr_high"] or spo2_thr != thr["spo2_low"] or temp_thr != thr["temp_high"]):
    if st.sidebar.button("Save thresholds for patient"):
        upsert_patient_thresholds(patient_id, hr_thr, spo2_thr, temp_thr)
        st.sidebar.success("Thresholds saved.")

# ----------------------------
# Data ingestion
# ----------------------------
st.title("IoT Health Monitoring – Decision Support")

if uploaded is not None:
    # 1) Load CSV
    try:
        df = pd.read_csv(uploaded)
    except Exception:
        df = pd.read_csv(uploaded, sep=";")
    validate_csv_columns(df)

    # 2) Parse time
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")

    # 3) Compute status (rule-based)
    df["Status"] = df.apply(
        lambda x: compute_status(x["HR (bpm)"], x["SpO₂ (%)"], x["Temp (°C)"], hr_thr, spo2_thr, temp_thr),
        axis=1
    )

    # 4) Choose/create patient ID for this upload
    st.subheader("Assign data to a patient")
    new_pid = st.text_input("Patient ID (e.g., P001)", value=patient_id or "P001")
    new_pname = st.text_input("Patient Name", value=next((p["name"] for p in patients if p["id"] == patient_id), "Demo Patient") if patient_id else "Demo Patient")

    if st.button("Save uploaded dataset to DB"):
        count = save_dataset_to_db(new_pid, new_pname, df)
        upsert_patient_thresholds(new_pid, hr_thr, spo2_thr, temp_thr)
        # record alerts for any non-normal rows
        alerts_written = record_alerts(new_pid, df[df["Status"] != "Normal"])
        st.success(f"Saved {count} observations for {new_pid} ({new_pname}), alerts recorded: {alerts_written}")

# ----------------------------
# Load time-series from DB
# ----------------------------
if patient_id:
    df_db = load_observations(patient_id)
    st.subheader(f"Dataset (patient: {patient_id})")
    if df_db.empty:
        st.info("No observations found for this patient. Upload a CSV to populate.")
    else:
        # KPIs
        alerts_df = df_db[df_db["Status"] != "Normal"].copy()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Records", f"{len(df_db):,}")
        k2.metric("Total Alerts", f"{len(alerts_df):,}")
        k3.metric("Avg HR (bpm)", f"{df_db['HR (bpm)'].mean():.1f}")
        k4.metric("Avg SpO₂ (%)", f"{df_db['SpO₂ (%)'].mean():.1f}")

        st.dataframe(df_db.head(12), use_container_width=True)

        # Plots
        st.subheader("Time-Series (alerts highlighted)")
        c1, c2, c3 = st.columns(3)
        with c1:
            fig = plot_timeseries(df_db, "HR (bpm)", "Heart Rate", "HR (bpm)", df_db["Status"] == "High Heart Rate Alert")
            st.pyplot(fig)
        with c2:
            fig = plot_timeseries(df_db, "SpO₂ (%)", "SpO₂", "SpO₂ (%)", df_db["Status"] == "Low Oxygen Alert")
            st.pyplot(fig)
        with c3:
            fig = plot_timeseries(df_db, "Temp (°C)", "Temperature", "Temp (°C)", df_db["Status"] == "Fever Alert")
            st.pyplot(fig)

        # Alerts table
        st.subheader("Alerts")
        st.dataframe(alerts_df, use_container_width=True)

        # Download alerts
        csv_buf = io.StringIO()
        alerts_df.to_csv(csv_buf, index=False)
        st.download_button(
            "Download alerts as CSV",
            csv_buf.getvalue(),
            file_name=f"{patient_id}_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        # Send a test email
        st.subheader("Notify")
        email_to = st.text_input("Send a test alert email to:", value="")
        if st.button("Send Test Email") and email_to:
            body = f"[IoT Alert Demo] Patient {patient_id}: {len(alerts_df)} alerts at {datetime.now().isoformat(timespec='seconds')}"
            ok, msg = send_email(email_to, "IoT Health Alerts (Demo)", body)
            (st.success if ok else st.error)(msg)
