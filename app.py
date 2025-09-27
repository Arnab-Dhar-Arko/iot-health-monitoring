# app.py
import os
import io
from datetime import datetime
from pathlib import Path

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
# Constants & Paths
# ----------------------------
APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = APP_DIR / "iot_health_data.csv"
HOSPITALS_CSV = APP_DIR / "hospitals_bd.csv"
RESOURCES_CSV = APP_DIR / "bd_resources.csv"
SUMMARY_MD = APP_DIR / "thesis_summary.md"
METHOD_MD = APP_DIR / "thesis_methodology.md"

REQUIRED_COLS = ["Time", "HR (bpm)", "SpO₂ (%)", "Temp (°C)"]

# ----------------------------
# Helpers
# ----------------------------
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

# Normalize incoming CSV headers to expected ones
COLUMN_ALIASES = {
    "Time": ["time", "timestamp", "date_time", "datetime"],
    "HR (bpm)": ["hr", "heart_rate", "heart rate", "hr (bpm)", "heartrate", "heart_rate_bpm"],
    "SpO₂ (%)": ["spo2", "spO2", "spO2 (%)", "spo (%)", "spo2_percent", "oxygen", "SpO (%)"],
    "Temp (°C)": ["temp", "temperature", "temp (c)", "temperature_c", "temp_c", "body_temp", "Temp (C)"]
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to match REQUIRED_COLS if aliases are present."""
    rename_map = {}
    lower_cols = {c.strip().lower(): c for c in df.columns}
    for target, aliases in COLUMN_ALIASES.items():
        if target not in df.columns:
            for a in [target] + aliases:
                key = a.strip().lower()
                if key in lower_cols:
                    rename_map[lower_cols[key]] = target
                    break
    return df.rename(columns=rename_map)

@st.cache_data(show_spinner=False)
def load_csv(path_or_file) -> pd.DataFrame:
    # Accept file-like or path; try comma then semicolon
    try:
        df = pd.read_csv(path_or_file)
    except Exception:
        df = pd.read_csv(path_or_file, sep=";")

    # Normalize headers and validate
    df = normalize_columns(df)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "CSV missing required columns after normalization: "
            + ", ".join(missing)
            + ". Expected: Time, HR (bpm), SpO₂ (%), Temp (°C)."
        )

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
        ax.scatter(df.loc[alert_mask, "Time"], df.loc[alert_mask, ycol], marker="o")
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig

def fig_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    buf.seek(0)
    return buf.read()

@st.cache_data
def load_hospitals() -> pd.DataFrame:
    if HOSPITALS_CSV.exists():
        df = pd.read_csv(HOSPITALS_CSV)
        if "iot_enabled" in df.columns:
            df["iot_enabled"] = df["iot_enabled"].astype(str).str.lower().isin(["true", "1", "yes"])
        return df
    return pd.DataFrame(columns=["name","city","ownership","iot_enabled","iot_features","contact","source","verification_status"])

@st.cache_data
def load_resources() -> pd.DataFrame:
    if RESOURCES_CSV.exists():
        return pd.read_csv(RESOURCES_CSV)
    return pd.DataFrame(columns=["category","title","url","note"])

# ----------------------------
# Sidebar (data + thresholds)
# ----------------------------
st.sidebar.title("Controls")

uploaded = st.sidebar.file_uploader("Upload CSV (optional)", type=["csv"])
st.sidebar.caption("Expected columns: Time, HR (bpm), SpO₂ (%), Temp (°C) [Status optional]")

st.sidebar.markdown("---")
st.sidebar.caption("Clinical thresholds (adjust as needed)")
thr_hr = st.sidebar.number_input("HR alert if > bpm", 60, 220, 120, step=1)
thr_spo2 = st.sidebar.number_input("SpO₂ alert if < %", 70, 100, 90, step=1)
thr_temp = st.sidebar.number_input("Temp alert if > °C", 35.0, 42.0, 38.0, step=0.1)

# ---- Other options (just below thresholds) ----
with st.sidebar.expander("Other options (quick views & exports)", expanded=False):
    show_all_btn = st.button("Show ALL alerts", key="btn_show_all")
    toggle_hr = st.toggle("HR alerts", value=True, key="tog_hr")
    toggle_spo2 = st.toggle("SpO₂ alerts", value=True, key="tog_spo2")
    toggle_temp = st.toggle("Fever alerts", value=True, key="tog_temp")
    if show_all_btn:
        toggle_hr = toggle_spo2 = toggle_temp = True
    st.session_state["alert_toggles"] = (toggle_hr, toggle_spo2, toggle_temp)

# ----------------------------
# Load data
# ----------------------------
if uploaded is not None:
    df = load_csv(uploaded)
else:
    if not DEFAULT_DATA.exists():
        st.error(f"Dataset not found: {DEFAULT_DATA}")
        st.stop()
    df = load_csv(DEFAULT_DATA)

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
    mime="text/csv",
    key="dl_kpi_summary"
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
# Alerts breakdown + table (respect toggles)
# ----------------------------
st.subheader("Alerts Breakdown")
if len(alerts):
    st.bar_chart(alerts["Status"].value_counts())
else:
    st.info("No alerts at current thresholds.")

st.subheader("Alerts Table (filtered by 'Other options')")
tog_hr, tog_spo2, tog_temp = st.session_state.get("alert_toggles", (True, True, True))
mask = (
    (tog_hr & (alerts["Status"] == "High Heart Rate Alert")) |
    (tog_spo2 & (alerts["Status"] == "Low Oxygen Alert")) |
    (tog_temp & (alerts["Status"] == "Fever Alert"))
)
alerts_view = alerts[mask].copy()

st.dataframe(alerts_view, use_container_width=True)

# Save + download alerts
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
alerts_path = APP_DIR / f"iot_health_alerts_{stamp}.csv"
alerts.to_csv(alerts_path, index=False, encoding="utf-8")
st.caption(f"Alerts also saved to: {alerts_path}")

csv_buf = io.StringIO()
alerts_view.to_csv(csv_buf, index=False)
st.download_button(
    "Download alerts (filtered) as CSV",
    csv_buf.getvalue(),
    file_name=f"iot_health_alerts_{stamp}.csv",
    mime="text/csv",
    key="dl_alerts_filtered_main"
)

# Offer figure downloads (MAIN section) — unique keys & filenames
st.download_button(
    "Download Heart Rate plot (PNG)",
    fig_bytes(fig_hr),
    file_name="figure_hr_timeseries_main.png",
    mime="image/png",
    key="dl_hr_main"
)
st.download_button(
    "Download SpO₂ plot (PNG)",
    fig_bytes(fig_spo2),
    file_name="figure_spo2_timeseries_main.png",
    mime="image/png",
    key="dl_spo2_main"
)
st.download_button(
    "Download Temperature plot (PNG)",
    fig_bytes(fig_temp),
    file_name="figure_temp_timeseries_main.png",
    mime="image/png",
    key="dl_temp_main"
)

st.caption("Tip: Adjust thresholds in the sidebar or upload a new CSV to re-run analysis.")

# ----------------------------
# BANGLADESH FOCUS (tabs)
# ----------------------------
st.divider()
st.header("Bangladesh Focus")

tab_stats, tab_hosp, tab_docs = st.tabs([
    "BD Stats & Useful Links",
    "Hospitals & IoT Directory",
    "Docs & Downloads"
])

# ---------- TAB: BD Stats & Links ----------
with tab_stats:
    st.subheader("Key metrics (driven by your CSVs)")
    res_df = load_resources()
    hosp_df = load_hospitals()
    total_hosp = int(hosp_df["name"].nunique()) if not hosp_df.empty else 0
    iot_hosp = int(hosp_df[hosp_df.get("iot_enabled", False)]["name"].nunique()) if not hosp_df.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Hospitals (in list)", f"{total_hosp:,}")
    c2.metric("Hospitals with IoT", f"{iot_hosp:,}")
    c3.metric("IoT Adoption (%)", f"{(100*iot_hosp/total_hosp):.1f}%" if total_hosp else "—")

    st.subheader("Authoritative Links (click to open)")
    if res_df.empty:
        st.info("Add your sources in bd_resources.csv or upload below.")
    else:
        show = res_df.copy()
        show["link"] = show["url"]
        st.dataframe(
            show[["category","title","link","note"]],
            use_container_width=True,
            column_config={"link": st.column_config.LinkColumn("URL")}
        )

    with st.expander("Download/Upload resource list"):
        # template
        template_res = """category,title,url,note
Government,DGHS UHC Indicators,https://dashboard.dghs.gov.bd/pages/uhc_list.php,Real-time facility indicators
WHO,WHO Bangladesh Country Profile,https://www.who.int/countries/bgd,High-level indicators
World Bank,World Bank Health Indicators (BD),https://data.worldbank.org/country/bangladesh,Hospital beds/physicians
Research,icddr,b Research & HIS,https://www.icddrb.org,HDSS Matlab & RHIS
Policy,Digital Health Strategy (BD),https://dghs.gov.bd,Strategy & telemedicine policy
"""
        st.download_button(
            "Download template (bd_resources.csv)",
            template_res,
            file_name="bd_resources_template.csv",
            mime="text/csv",
            key="dl_bd_resources_template"
        )
        if not res_df.empty:
            st.download_button(
                "Download current bd_resources.csv",
                res_df.to_csv(index=False),
                file_name="bd_resources.csv",
                mime="text/csv",
                key="dl_bd_resources_current"
            )
        up_res = st.file_uploader("Upload updated bd_resources.csv", type=["csv"], key="up_res_bd")
        if up_res:
            RESOURCES_CSV.write_bytes(up_res.read())
            st.cache_data.clear()
            st.success("bd_resources.csv replaced. Reload the app to see changes.")

# ---------- TAB: Hospitals & IoT ----------
with tab_hosp:
    st.subheader("Directory of Hospitals / Programs with IoT / Telemedicine")
    hosp_df = load_hospitals()
    if hosp_df.empty:
        st.info("Add entries in hospitals_bd.csv or upload below (see template).")
    else:
        # Filters
        fcol1, fcol2, fcol3 = st.columns(3)
        city = fcol1.selectbox("Filter by city", ["All"] + sorted(hosp_df["city"].dropna().unique().tolist()))
        own  = fcol2.selectbox("Ownership", ["All"] + sorted(hosp_df["ownership"].dropna().unique().tolist()))
        only_iot = fcol3.toggle("Only IoT-enabled", value=True)

        filt = hosp_df.copy()
        if city != "All": filt = filt[filt["city"] == city]
        if own  != "All": filt = filt[filt["ownership"] == own]
        if only_iot and "iot_enabled" in filt.columns:
            filt = filt[filt["iot_enabled"]]

        filt = filt.sort_values(["iot_enabled","city","name"], ascending=[False, True, True]) if "iot_enabled" in filt.columns else filt.sort_values(["city","name"])
        show = filt.copy()
        if "source" in show.columns:
            st.dataframe(
                show[["name","city","ownership","iot_enabled","iot_features","contact","source"]].fillna(""),
                use_container_width=True,
                column_config={"source": st.column_config.LinkColumn("Source")}
            )
        else:
            st.dataframe(show.fillna(""), use_container_width=True)

        st.download_button(
            "Download filtered list (CSV)",
            show.to_csv(index=False),
            file_name="bd_hospitals_filtered.csv",
            mime="text/csv",
            key="dl_hospitals_filtered"
        )

    with st.expander("Download template / Upload updated hospitals list"):
        template_hosp = """name,city,ownership,iot_enabled,iot_features,contact,source,verification_status
United Hospital,Dhaka,Private,True,RPM wearables + telemedicine,+880-xxxx,https://www.unitedhospital.com.bd,verify_RPM
BSMMU Telemedicine,Dhaka,Public,True,Telemedicine hub + remote consults,16263,https://bsmmu.edu.bd,verify_scope
District Hospital (Sample),Chattogram,Public,False,,,+,verify_telemed
"""
        st.download_button(
            "Download template (hospitals_bd.csv)",
            template_hosp,
            file_name="hospitals_bd_template.csv",
            mime="text/csv",
            key="dl_hospitals_template"
        )
        if not load_hospitals().empty:
            st.download_button(
                "Download current hospitals_bd.csv",
                load_hospitals().to_csv(index=False),
                file_name="hospitals_bd.csv",
                mime="text/csv",
                key="dl_hospitals_current"
            )
        up_hosp = st.file_uploader("Upload updated hospitals_bd.csv", type=["csv"], key="up_hosp_bd")
        if up_hosp:
            HOSPITALS_CSV.write_bytes(up_hosp.read())
            st.cache_data.clear()
            st.success("hospitals_bd.csv replaced. Reload the app to see changes.")

# ---------- TAB: Docs & Downloads ----------
with tab_docs:
    st.subheader("Thesis Documentation (Summary & Methodology)")
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Summary**")
        if SUMMARY_MD.exists():
            st.markdown(SUMMARY_MD.read_text(encoding="utf-8"))
        else:
            st.info("Create `thesis_summary.md` in this folder to show it here.")
    with colB:
        st.markdown("**Methodology**")
        if METHOD_MD.exists():
            st.markdown(METHOD_MD.read_text(encoding="utf-8"))
        else:
            st.info("Create `thesis_methodology.md` in this folder to show it here.")

    st.divider()
    st.subheader("Download Center")
    st.download_button(
        "Download current dataset (CSV)",
        df.to_csv(index=False),
        file_name="iot_health_data_current.csv",
        mime="text/csv",
        key="dl_dataset_docs"
    )
    st.download_button(
        "Download ALL alerts (CSV)",
        alerts.to_csv(index=False),
        file_name="iot_health_alerts_current.csv",
        mime="text/csv",
        key="dl_alerts_all_docs"
    )
    st.download_button(
        "Download filtered alerts (CSV)",
        alerts_view.to_csv(index=False),
        file_name="iot_health_alerts_filtered.csv",
        mime="text/csv",
        key="dl_alerts_filtered_docs"
    )

    # Figure downloads (DOCS tab) – different keys & filenames than MAIN
    st.download_button(
        "Download Heart Rate plot (PNG)",
        fig_bytes(fig_hr),
        file_name="figure_hr_timeseries_docs.png",
        mime="image/png",
        key="dl_hr_docs"
    )
    st.download_button(
        "Download SpO₂ plot (PNG)",
        fig_bytes(fig_spo2),
        file_name="figure_spo2_timeseries_docs.png",
        mime="image/png",
        key="dl_spo2_docs"
    )
    st.download_button(
        "Download Temperature plot (PNG)",
        fig_bytes(fig_temp),
        file_name="figure_temp_timeseries_docs.png",
        mime="image/png",
        key="dl_temp_docs"
    )

# ----------------------------
# Extra: HR anomaly detection (statistical)
# ----------------------------
st.divider()
st.subheader("HR Statistical Anomalies (rolling z-score > 3)")
win = 12  # adjust depending on sampling interval
hr = df["HR (bpm)"]
roll_mean = hr.rolling(win, min_periods=win).mean()
roll_std  = hr.rolling(win, min_periods=win).std()
z = (hr - roll_mean) / roll_std
anomaly = (np.abs(z) > 3)

fig_a, ax_a = plt.subplots(figsize=(10, 4))
ax_a.plot(df["Time"], hr, label="HR (bpm)")
ax_a.scatter(df["Time"][anomaly], hr[anomaly], marker="^")
ax_a.set_xlabel("Time")
ax_a.set_ylabel("HR (bpm)")
ax_a.set_title("HR Anomalies (Z-score > 3)")
ax_a.grid(True, alpha=0.25)
ax_a.legend(loc="best")
fig_a.tight_layout()
st.pyplot(fig_a)

st.caption("Tip: Keep BD CSVs in your repo so the information persists on Streamlit Cloud. Use the uploaders above to update quickly during demos.")
