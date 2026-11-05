# Fresho – ESP32 hardware + ML integration

```
DHT22 + MQ-135 ──► ESP32 ──Wi-Fi/MQTT──► Broker ──► fresho_bridge.py ──► your ML model
                     ▲                                   ▲   │
                     └──────── result (LED update) ──────┘   └─ phone camera (IP Webcam snapshot)
```

## 1. Wiring

| Part | Pin on part | ESP32 pin | Notes |
|---|---|---|---|
| DHT22 | VCC | 3V3 | |
| | DATA | GPIO 4 | needs 10k pull-up to 3V3 (bare sensor; most 3-pin modules already have it) |
| | GND | GND | |
| MQ-135 module | VCC | **VIN (5V)** | heater needs 5V, 3.3V will not work well |
| | GND | GND | common ground with ESP32 |
| | AO | **voltage divider** → GPIO 34 | see below |
| LED green / yellow / red | anode via 220 Ω | GPIO 25 / 26 / 27 | cathode to GND |

**Voltage divider (important):** the MQ module outputs up to 5 V but ESP32 pins tolerate 3.3 V.
`AO ──[10k]──┬── GPIO34` and `┬──[15k]── GND`. This gives a ratio of 0.6, which is already set as `GAS_DIVIDER_RATIO`.
If you use other resistors, update that value in `config.h`.

Use GPIO 34 (ADC1). ADC2 pins stop working while Wi-Fi is on.

## 2. Flash the ESP32

1. Arduino IDE → install ESP32 board package (Espressif).
2. Library Manager: **DHT sensor library** (Adafruit, also accept the Unified Sensor dependency), **PubSubClient**, **ArduinoJson (v7)**.
3. Open `fresho_esp32/fresho_esp32.ino`, edit `config.h` (Wi-Fi, broker IP, pins).
4. Board = *ESP32 Dev Module*, upload, open Serial Monitor at 115200.

First boot: the gas sensor preheats (3 min, `GAS_WARMUP_MS`), then it auto-calibrates `R0` **in clean air** and saves it to flash.
Use `GAS_WARMUP_MS 60000UL` for quick demos. A brand-new MQ sensor stabilises better after ~24 h of powered burn-in.
`gas_index = R0/Rs` is about 1 in clean air and rises when VOC/ammonia from decaying food increases.

## 3. Run the cloud side

```bash
# broker (laptop)
sudo apt install mosquitto     # or: brew install mosquitto / use Mosquitto for Windows
# bridge
pip install paho-mqtt requests pillow
python fresho_bridge.py
```
If Mosquitto only listens on localhost, add `listener 1883` and `allow_anonymous true` to its config for LAN testing.

**Phone camera:** install the free *IP Webcam* app (Android), tap *Start server*, put the URL it shows into `PHONE_SHOT`
(`http://<phone-ip>:8080/shot.jpg`). Phone and laptop must be on the same Wi-Fi. (iPhone: any app that exposes a JPEG snapshot URL works the same way.)

## 4. Where your ML model goes

**Option A – Cloud/laptop (recommended for your design, since the camera is the phone)**
Edit two functions in `fresho_bridge.py`:
- `load_models()`: load your vision model / fusion model once.
- `predict_freshness(models, image, s)`: run vision → fuse with `temp_c, humidity, gas_index, storage_h` → return `{"food", "label", "score"}`.

The ESP32 receives that result automatically and lights green / yellow / red. If the cloud is silent for
`CLOUD_RESULT_TIMEOUT_S`, the ESP32 falls back to its own local rules.

**Option B – On-device sensor model (TinyML)**
Only for a sensor-only model (temp, humidity, gas, time). Image models are too big for the ESP32.
1. Export your sklearn model with `micromlgen` (`port(clf)`) or TFLite Micro / Edge Impulse.
2. Wrap it in `fresho_model.h` so it exposes `int fresho_predict(const float* x);` returning 0 = fresh, 1 = use soon, 2 = deteriorating.
3. Feature order must match training: `{temp_c, humidity, gas_index, gas_rs_kohm, storage_h}`.
4. Set `USE_ONBOARD_MODEL 1` in `config.h`.

**Training data:** `fresho_log.csv` and `captures/` build up automatically while the system runs. Label them and use them to retrain with real sensor data.

## 5. MQTT cheat sheet (test with `mosquitto_pub`)

| Topic | Payload |
|---|---|
| `fresho/fresho-01/sensors` (from ESP32) | `{"temp_c":27.4,"humidity":61,"gas_index":1.35,"gas_rs_kohm":8.2,"storage_h":12.5,...}` |
| `fresho/fresho-01/result` (to ESP32) | `{"label":"use_soon","score":55,"food":"tomato"}` |
| `fresho/fresho-01/cmd` | `{"cmd":"calibrate"}` clean air re-baseline · `{"cmd":"new_batch"}` reset storage timer · `{"cmd":"interval","value":10}` · `{"cmd":"publish_now"}` |

## 6. Known limits
- MQ sensors respond to many gases; the index is a *relative trend*, not a ppm value. This is why fusing it with the camera model is useful.
- Re-calibrate (`calibrate` command) in clean air if you move the sensor to a new location.
- Rules in `ruleBasedLabel()` and the placeholder in `predict_freshness()` are only to prove the chain works; your model replaces them.

## 7. ESP32-C3 boards (C3 Nano / Super Mini)
| Part | ESP32-C3 pin |
|---|---|
| Gas sensor AO (via 10k/15k divider) | GPIO 3 |
| DHT data | GPIO 5 |
| LED green / yellow / red | GPIO 6 / 7 / 10 |

Arduino IDE: board = **ESP32C3 Dev Module**, **USB CDC On Boot = Enabled** (otherwise Serial Monitor stays empty).
If upload fails, hold BOOT, tap RESET, release BOOT, then upload. Avoid GPIO 8, 9 (boot pins) and 18, 19 (USB).

## 8. ESP32-C6 boards (your setup)
| Part | ESP32-C6 pin |
|---|---|
| Gas sensor AO (via 10k/15k divider) | GPIO 2 |
| DHT data | GPIO 10 |
| LED green / yellow / red (220 Ω each) | GPIO 18 / 19 / 20 |
| MQ-135 VCC | 5V pin |
| DHT VCC | 3V3 |

Arduino IDE: install **esp32 by Espressif version 3.0.0 or newer** (older versions do not support the C6),
board = **ESP32C6 Dev Module**, **USB CDC On Boot = Enabled**. Wi-Fi is 2.4 GHz only.

## 9. No sensors yet? Simulation mode
`SIMULATE_SENSORS 1` in `config.h` sends fake readings (gas index slowly rises so the LEDs go green, yellow, red).
It lets you test Wi-Fi, MQTT, `fresho_bridge.py` and the LEDs with only the ESP32. Set it to `0` once the DHT and MQ-135 are connected.

## 10. Seeed XIAO ESP32-C6 (the board you have)
| Part | XIAO pin (GPIO) |
|---|---|
| Gas sensor AO via 10k/15k divider | D2 (GPIO2) |
| DHT data | D3 (GPIO21) |
| LED green / yellow / red | D10 (GPIO18) / D8 (GPIO19) / D9 (GPIO20) |
| MQ-135 VCC | 5V pin |
| DHT VCC | 3V3 |
Arduino IDE board: **XIAO_ESP32C6**. Upload problem fix: hold BOOT, plug USB, release BOOT, then Upload.
