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
