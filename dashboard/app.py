from streamlit_autorefresh import st_autorefresh
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make the project root importable when running dashboard/app.py
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


import os
import requests
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

API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")

try:
    if API_BASE_URL:
        response = requests.get(
            f"{API_BASE_URL}/readings",
            params={"limit": 100},
            timeout=15,
        )
        response.raise_for_status()
        readings = response.json()["readings"]
    else:
        readings = get_readings(limit=100)

except (requests.RequestException, ValueError, KeyError) as exc:
    st.error(f"Could not load sensor readings: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Could not load sensor readings: {exc}")
    st.stop()
df = pd.DataFrame(readings)

if df.empty:
    st.info(
        "No sensor readings available yet. "
        "Connect your ESP32 or generate a simulated reading."
    )
    st.stop()

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



# --- Camera-Based Food Detection ---
from food_detector import detect_food

st.divider()
st.header("📸 Fresho Vision — Food Freshness Detection")

st.write(
    "Identify food items and estimate the visual freshness "
    "of supported fruits: apples, bananas and oranges."
)

uploaded_file = st.file_uploader(
    "Upload a food image",
    type=["jpg", "jpeg", "png"],
    key="food_image_upload",
)

camera_image = st.camera_input(
    "Or take a picture of food",
    key="food_camera",
)

selected_image = camera_image or uploaded_file

if selected_image is not None:
    from PIL import Image

    image = Image.open(selected_image).convert("RGB")

    with st.spinner("Fresho is analyzing your food..."):
        detections, annotated_image = detect_food(image)

    st.subheader("Detection Result")
    st.image(
        annotated_image,
        caption="YOLO food detection",
        use_container_width=True,
    )

    if detections:
        st.success(f"Detected {len(detections)} food object(s).")

        for index, detection in enumerate(detections, start=1):
            food = detection["food"].capitalize()
            yolo_confidence = detection["confidence"]
            freshness = detection.get("freshness")

            with st.container(border=True):
                st.markdown(f"### {index}. {food}")

                col1, col2 = st.columns(2)

                col1.metric(
                    "Food detection confidence",
                    f"{yolo_confidence * 100:.1f}%"
                )

                if freshness:
                    status = freshness["freshness"]
                    confidence = freshness["confidence"]

                    col2.metric(
                        "Visual freshness",
                        status
                    )

                    st.progress(confidence)

                    st.caption(
                        f"Freshness model confidence: "
                        f"{confidence * 100:.1f}%"
                    )
                else:
                    col2.metric(
                        "Visual freshness",
                        "Not supported"
                    )

        st.caption(
            "Freshness predictions are experimental visual estimates. "
            "They do not establish food safety or detect pathogens."
        )

    else:
        st.info(
            "No supported food items detected. "
            "Try a clearer image with the food visible."
        )
