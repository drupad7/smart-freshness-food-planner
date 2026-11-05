"""
FRESHO cloud bridge
-------------------
Runs on your laptop / server. For every sensor message from the ESP32 it:
  1. grabs a photo from the phone camera (IP Webcam app, or a folder / test image)
  2. calls predict_freshness(image, sensors)   <-- YOUR ML MODEL GOES HERE
  3. publishes the result back to the ESP32 (LEDs update)
  4. logs everything to fresho_log.csv + saves the image (history / training data)

Install:  pip install paho-mqtt requests pillow
Run:      python fresho_bridge.py
"""
import csv, io, json, os, time
from datetime import datetime

import paho.mqtt.client as mqtt
import requests
from PIL import Image

# ------------------------------------------------------------------ settings
MQTT_HOST   = "10.79.9.145"                         # broker address (same as MQTT_HOST in config.h)
MQTT_PORT   = 1883
DEVICE_ID   = "fresho-01"
PHONE_SHOT  = "http://192.168.1.50:8080/shot.jpg" # 'IP Webcam' app -> Start server -> shows this URL
IMAGE_EVERY_S = 60                                # don't hammer the phone camera
LOG_CSV     = "fresho_log.csv"
IMG_DIR     = "captures"
os.makedirs(IMG_DIR, exist_ok=True)

LABELS = ["fresh", "use_soon", "deteriorating"]

# ------------------------------------------------------------------ YOUR ML MODEL
def load_models():
    """Load your trained models ONCE here. Return whatever you need as a dict."""
    models = {}
    # --- examples (uncomment / adapt) ---
    # import tensorflow as tf
    # models["vision"] = tf.keras.models.load_model("vision_model.h5")
    # import torch;  models["vision"] = torch.load("vision_model.pt").eval()
    # import joblib; models["fusion"] = joblib.load("fusion_model.pkl")   # sklearn / xgboost on sensor+vision features
    return models


def predict_freshness(models, image, s):
    """
    image : PIL.Image or None (None if the phone camera was unreachable)
    s     : dict from the ESP32, keys:
            temp_c, humidity, gas_index, gas_rs_kohm, gas_mv, storage_h, warmup, ts
    return: dict {"food": str, "label": one of LABELS, "score": 0-100}

    Replace the body with your pipeline, e.g.:
        food, vis_probs = vision_model(image)                 # Tomato/Banana/Apple/Carrot/Spinach + fresh/rotten
        x = [*vis_probs, s["temp_c"], s["humidity"], s["gas_index"], s["storage_h"]]
        label_idx = fusion_model.predict([x])[0]
    Keep the feature order identical to your training script.
    """
    # ---- PLACEHOLDER (sensor-only rules) so the whole chain works before your model is plugged in ----
    score = 100.0
    gi = s.get("gas_index")
    if gi is not None and gi > 1.2:
        score -= (gi - 1.2) * 40
    t = s.get("temp_c")
    if t is not None and t > 25:
        score -= (t - 25) * 2
    h = s.get("humidity")
    if h is not None and h > 90:
        score -= (h - 90) * 1.5
    sh = s.get("storage_h", -1)
    if sh and sh > 72:
        score -= (sh - 72) * 0.15
    score = max(0.0, min(100.0, score))
    label = LABELS[0] if score >= 70 else LABELS[1] if score >= 40 else LABELS[2]
    return {"food": "unknown", "label": label, "score": round(score)}

# ------------------------------------------------------------------ plumbing
last_img_time = 0.0
last_img = None

def grab_phone_image():
    global last_img_time, last_img
    if time.time() - last_img_time < IMAGE_EVERY_S and last_img is not None:
        return last_img
    try:
        r = requests.get(PHONE_SHOT, timeout=5)
        r.raise_for_status()
        last_img = Image.open(io.BytesIO(r.content)).convert("RGB")
        last_img_time = time.time()
        return last_img
    except Exception as e:
        print("[CAM] phone camera unavailable:", e)
        return last_img      # reuse previous frame if we have one

def log_row(s, res, img_name):
    new = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "temp_c", "humidity", "gas_index", "gas_rs_kohm", "gas_mv",
                        "storage_h", "food", "label", "score", "image"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), s.get("temp_c"), s.get("humidity"),
                    s.get("gas_index"), s.get("gas_rs_kohm"), s.get("gas_mv"), s.get("storage_h"),
                    res["food"], res["label"], res["score"], img_name])

models = load_models()

def on_connect(c, userdata, flags, rc, props=None):
    print("[MQTT] connected, listening on fresho/%s/sensors" % DEVICE_ID)
    c.subscribe(f"fresho/{DEVICE_ID}/sensors")

def on_message(c, userdata, msg):
    try:
        s = json.loads(msg.payload)
    except Exception:
        return
    if s.get("warmup"):
        print("[SKIP] gas sensor still warming up")
        return
    img = grab_phone_image()
    res = predict_freshness(models, img, s)
    c.publish(f"fresho/{DEVICE_ID}/result", json.dumps(res))

    img_name = ""
    if img is not None:
        img_name = f"{IMG_DIR}/{datetime.now():%Y%m%d_%H%M%S}.jpg"
        img.save(img_name, quality=85)
    log_row(s, res, img_name)
    print("[RESULT]", res, "| sensors:", s)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_forever()
