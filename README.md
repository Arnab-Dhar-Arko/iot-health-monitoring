# IoT Health Monitoring  Decision Support

## Run locally
pip install -r requirements.txt
python -m streamlit run app.py

## Data schema
Time, HR (bpm), SpO (%), Temp (C) [Status optional]

## Features
- Threshold alerts (HR>120, SpO<90, Temp>38)
- KPI cards, charts, alerts table + CSV export
- Upload your own CSV

## Thesis context (Bangladesh)
Use DGHS, WHO, World Bank, BDHS reports for Chapters 2 & 5.

