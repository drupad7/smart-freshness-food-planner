from streamlit_autorefresh import st_autorefresh
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make the project root importable when running dashboard/app.py
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database import get_readings
from freshness_analyzer import analyze_freshness

st.set_page_config(
    page_title="Smart Freshness System",
    page_icon="🥗",
    layout="wide",
)

st_autorefresh(
    interval=10000,
    limit=None,
    key="dashboard_refresh",
)

st.title("🥗 Smart Freshness & Food Planning System")
st.caption("Environmental monitoring and prototype freshness estimates")

try:
    readings = get_readings(limit=100)
except Exception as exc:
    st.error(f"Could not load sensor readings: {exc}")
    st.stop()

if not readings:
    st.info("No sensor readings yet. Run `python sensor_service.py` to collect one.")
    st.stop()

df = pd.DataFrame(readings)

# Add the freshness classification for each reading.
df["freshness_status"] = df.apply(
    lambda row: analyze_freshness(row.to_dict())["freshness_status"],
    axis=1,
)

latest = df.iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Temperature", f"{latest['temperature']:.1f} °C")
col2.metric("Humidity", f"{latest['humidity']:.1f} %")
col3.metric("Gas reading", int(latest["gas_raw"]))
col4.metric("Freshness estimate", latest["freshness_status"])

st.subheader("Temperature history")
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
chart_df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
if not chart_df.empty:
    st.line_chart(chart_df.set_index("timestamp")["temperature"])

st.subheader("Recent sensor readings")
st.dataframe(
    df[
        [
            "timestamp",
            "device_id",
            "temperature",
            "humidity",
            "gas_raw",
            "freshness_status",
        ]
    ],
    use_container_width=True,
)

st.caption(
    "Prototype only: these estimates do not establish food safety or detect pathogens."
)
