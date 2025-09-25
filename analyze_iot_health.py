import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
# =========================
# Configuration / Paths
# =========================
BASE = os.path.dirname(os.path.abspath(__file__))         # folder where this script lives
DATA_PATH   = os.path.join(BASE, "iot_health_data.csv")   # input CSV (must exist)
ALERTS_PATH = os.path.join(BASE, "iot_health_alerts.csv") # output alerts CSV
FIG_HR      = os.path.join(BASE, "figure_hr_timeseries.png")
FIG_SPO2    = os.path.join(BASE, "figure_spo2_timeseries.png")
FIG_TEMP    = os.path.join(BASE, "figure_temp_timeseries.png")

REQUIRED_COLS = ["Time", "HR (bpm)", "SpO₂ (%)", "Temp (°C)"]

# =========================
# Helper: Status rules
# =========================
def compute_status(hr, spo2, temp):
    """
    Clinical rule-based status:
      - HR > 120 bpm          -> High Heart Rate Alert
      - SpO2 < 90 %           -> Low Oxygen Alert
      - Temp > 38.0 °C        -> Fever Alert
      - Otherwise             -> Normal
    """
    try:
        if float(hr) > 120:
            return "High Heart Rate Alert"
        elif float(spo2) < 90:
            return "Low Oxygen Alert"
        elif float(temp) > 38:
            return "Fever Alert"
        else:
            return "Normal"
    except Exception:
        return "Normal"

# =========================
# Main
# =========================
def main():
    print("====================================")
    print(" IoT Health Data Analyzer (Chapter 4)")
    print("====================================")
    print(f"[INFO] Script folder:    {BASE}")
    print(f"[INFO] Looking for CSV:  {DATA_PATH}")

    # ---- Load CSV (with fallback for semicolon) ----
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"CSV not found at:\n  {DATA_PATH}\n"
            f"Put 'iot_health_data.csv' next to this script and re-run."
        )

    try:
        df = pd.read_csv(DATA_PATH)
    except Exception:
        # Some locales export CSV with ; separator
        df = pd.read_csv(DATA_PATH, sep=";")

    # ---- Validate columns ----
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "CSV is missing required columns:\n"
            f"  {missing}\n"
            "Expected header exactly as:\n"
            "  Time,HR (bpm),SpO₂ (%),Temp (°C)[,Status]"
        )

    # ---- Parse time & compute status if missing ----
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")

    if "Status" not in df.columns:
        df["Status"] = df.apply(
            lambda x: compute_status(x["HR (bpm)"], x["SpO₂ (%)"], x["Temp (°C)"]),
            axis=1
        )

    # ---- Print sample and summary to console ----
    print("\n=== Dataset Sample (first 5 rows) ===")
    print(df.head())

    total_rows = len(df)
    alerts_df = df[df["Status"] != "Normal"].copy()
    total_alerts = len(alerts_df)

    print(f"\n[STATS] Total rows:   {total_rows}")
    print(f"[STATS] Total alerts: {total_alerts}")

    if total_alerts > 0:
        print("\n=== Alert categories (counts) ===")
        print(alerts_df["Status"].value_counts())

    # ---- Save alerts CSV ----
    alerts_df.to_csv(ALERTS_PATH, index=False, encoding="utf-8")
    print(f"\n[OK] Alerts saved → {ALERTS_PATH}")

    # =========================
    # Plots (each its own figure)
    # =========================

    # Heart Rate
    plt.figure(figsize=(11, 5))
    plt.plot(df["Time"], df["HR (bpm)"], label="HR (bpm)")
    hr_alerts = df[df["Status"] == "High Heart Rate Alert"]
    if not hr_alerts.empty:
        plt.scatter(hr_alerts["Time"], hr_alerts["HR (bpm)"], label="HR alerts", marker="o")
    plt.title("Heart Rate Over Time")
    plt.xlabel("Time"); plt.ylabel("HR (bpm)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_HR, dpi=160)
    plt.close()
    print(f"[OK] Saved: {FIG_HR}")

    # SpO2
    plt.figure(figsize=(11, 5))
    plt.plot(df["Time"], df["SpO₂ (%)"], label="SpO₂ (%)")
    spo2_alerts = df[df["Status"] == "Low Oxygen Alert"]
    if not spo2_alerts.empty:
        plt.scatter(spo2_alerts["Time"], spo2_alerts["SpO₂ (%)"], label="SpO₂ alerts", marker="x")
    plt.title("SpO₂ Over Time")
    plt.xlabel("Time"); plt.ylabel("SpO₂ (%)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_SPO2, dpi=160)
    plt.close()
    print(f"[OK] Saved: {FIG_SPO2}")
    if not temp_alerts.empty:
        plt.scatter(temp_alerts["Time"], temp_alerts["Temp (°C)"], label="Fever alerts", marker="s")
    plt.title("Temperature Over Time")
    plt.xlabel("Time"); plt.ylabel("Temp (°C)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_TEMP, dpi=160)
    plt.close()
    print(f"[OK] Saved: {FIG_TEMP}")

    print("\nAll done ✅")
    print("Files created in your folder:")
    print(f"  - {ALERTS_PATH}")
    print(f"  - {FIG_HR}")
    print(f"  - {FIG_SPO2}")
    print(f"  - {FIG_TEMP}")

if __name__ == "__main__":
    main()

