import os
import sqlite3
from typing import List, Dict
import pandas as pd

DB_URL = os.getenv("DB_URL", "sqlite:///iot.db")
# For SQLite local file:
_SQLITE_FILE = "iot.db"

def _conn():
    # SQLite for simplicity; swap to Postgres with SQLAlchemy in future
    return sqlite3.connect(_SQLITE_FILE, check_same_thread=False)

def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            name TEXT
        );
        CREATE TABLE IF NOT EXISTS thresholds (
            patient_id TEXT PRIMARY KEY,
            hr_high INTEGER,
            spo2_low INTEGER,
            temp_high REAL,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            time TEXT,
            hr INTEGER,
            spo2 INTEGER,
            temp REAL,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            time TEXT,
            kind TEXT,
            value REAL,
            status TEXT DEFAULT 'new',
            acknowledged_by TEXT,
            ack_time TEXT,
            note TEXT
        );
        """)
    return True

def list_patients() -> List[Dict]:
    with _conn() as con:
        rows = con.execute("SELECT id, name FROM patients ORDER BY id").fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]

def get_patient_thresholds(patient_id: str):
    defaults = {"hr_high": 120, "spo2_low": 90, "temp_high": 38.0}
    if not patient_id:
        return defaults
    with _conn() as con:
        row = con.execute(
            "SELECT hr_high, spo2_low, temp_high FROM thresholds WHERE patient_id=?",
            (patient_id,)
        ).fetchone()
    if not row:
        return defaults
    return {"hr_high": row[0], "spo2_low": row[1], "temp_high": row[2]}

def upsert_patient_thresholds(patient_id: str, hr_high: int, spo2_low: int, temp_high: float):
    with _conn() as con:
        con.execute("""
        INSERT INTO thresholds(patient_id, hr_high, spo2_low, temp_high, updated_at)
        VALUES(?,?,?,?,datetime('now'))
        ON CONFLICT(patient_id) DO UPDATE SET
            hr_high=excluded.hr_high,
            spo2_low=excluded.spo2_low,
            temp_high=excluded.temp_high,
            updated_at=datetime('now');
        """, (patient_id, hr_high, spo2_low, temp_high))

def save_dataset_to_db(patient_id: str, patient_name: str, df: pd.DataFrame) -> int:
    # ensure patient exists
    with _conn() as con:
        con.execute("INSERT OR IGNORE INTO patients(id, name) VALUES (?,?)", (patient_id, patient_name))
        # bulk insert observations
        rows = [
            (patient_id, str(t), int(hr), int(spo2), float(temp), str(status))
            for t, hr, spo2, temp, status in zip(df["Time"], df["HR (bpm)"], df["SpO₂ (%)"], df["Temp (°C)"], df["Status"])
        ]
        con.executemany("""
        INSERT INTO observations(patient_id, time, hr, spo2, temp, status)
        VALUES (?,?,?,?,?,?)
        """, rows)
        return len(rows)

def load_observations(patient_id: str) -> pd.DataFrame:
    with _conn() as con:
        df = pd.read_sql_query("""
            SELECT time as Time, hr as "HR (bpm)", spo2 as "SpO₂ (%)",
                   temp as "Temp (°C)", status as Status
            FROM observations
            WHERE patient_id=?
            ORDER BY time
        """, con, params=(patient_id,))
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        return df

def record_alerts(patient_id: str, alerts_df: pd.DataFrame) -> int:
    if alerts_df.empty:
        return 0
    with _conn() as con:
        rows = []
        for _, r in alerts_df.iterrows():
            if r["Status"] == "High Heart Rate Alert":
                rows.append((patient_id, str(r["Time"]), "HR_HIGH", float(r["HR (bpm)"])))
            if r["Status"] == "Low Oxygen Alert":
                rows.append((patient_id, str(r["Time"]), "SPO2_LOW", float(r["SpO₂ (%)"])))
            if r["Status"] == "Fever Alert":
                rows.append((patient_id, str(r["Time"]), "TEMP_HIGH", float(r["Temp (°C)"])))
        con.executemany("""
            INSERT INTO alerts(patient_id, time, kind, value, status)
            VALUES (?,?,?,?, 'new')
        """, rows)
        return len(rows)

def list_alerts(patient_id: str) -> pd.DataFrame:
    with _conn() as con:
        return pd.read_sql_query("""
            SELECT id, time, kind, value, status, acknowledged_by, ack_time, note
            FROM alerts
            WHERE patient_id=?
            ORDER BY time DESC
        """, con, params=(patient_id,))
