import matplotlib.pyplot as plt
import pandas as pd

REQUIRED_COLS = ["Time", "HR (bpm)", "SpO₂ (%)", "Temp (°C)"]

def validate_csv_columns(df: pd.DataFrame):
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}\nExpected: {', '.join(REQUIRED_COLS)}")

def compute_status(hr, spo2, temp, thr_hr=120, thr_spo2=90, thr_temp=38.0):
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

def plot_timeseries(df: pd.DataFrame, ycol: str, title: str, ylabel: str, alert_mask: pd.Series):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["Time"], df[ycol], label=ycol)
    if alert_mask is not None and getattr(alert_mask, "any", lambda: False)():
        ax.scatter(df.loc[alert_mask, "Time"], df.loc[alert_mask, ycol], marker="o")
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig
