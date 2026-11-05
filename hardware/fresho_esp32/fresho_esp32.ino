/*
  FRESHO - ESP32 edge node
  Sensors : DHT22/DHT11 (temp + humidity), MQ-135 style gas/VOC sensor
  Camera  : phone (handled on the cloud/laptop side, see fresho_bridge.py)
  Link    : Wi-Fi + MQTT (JSON)

  Libraries (Library Manager):
    - DHT sensor library (Adafruit)  + Adafruit Unified Sensor
    - PubSubClient (Nick O'Leary)
    - ArduinoJson (Benoit Blanchon) v7.x
  Board: "ESP32 Dev Module" (esp32 core 2.x or 3.x)

  MQTT topics:
    fresho/<id>/sensors  (ESP32 -> cloud)  readings every N seconds
    fresho/<id>/result   (cloud -> ESP32)  {"label":"fresh|use_soon|deteriorating","score":0-100,"food":"tomato"}
    fresho/<id>/cmd      (cloud -> ESP32)  {"cmd":"calibrate"} | {"cmd":"new_batch"} | {"cmd":"interval","value":10} | {"cmd":"publish_now"}
    fresho/<id>/status   (retained)        "online" / "offline"
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <Preferences.h>
#include <time.h>
#include "config.h"

#if USE_ONBOARD_MODEL
  #include "fresho_model.h"   // must provide: int fresho_predict(const float* x);  (0=fresh,1=use_soon,2=deteriorating)
#endif

// ---------------------------------------------------------------- globals
DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
Preferences prefs;

char topicSensors[48], topicStatus[48], topicCmd[48], topicResult[48];

struct Reading {
  bool  dhtOk;
  float tempC, hum;
  float gasMv;       // voltage at ADC pin (mV)
  float gasRsKohm;   // sensor resistance
  float gasIndex;    // R0/Rs : ~1 in clean air, rises with VOC/ammonia/decay gases
};

float    r0Kohm        = 0;       // clean-air baseline of gas sensor (stored in flash)
uint32_t batchStartTs  = 0;       // epoch when current food batch was stored
bool     warmedUp      = false;
uint32_t publishEveryS = PUBLISH_INTERVAL_S;

uint32_t lastPublishMs = 0, lastMqttTryMs = 0, lastResultMs = 0;
float    lastTemp = NAN, lastHum = NAN;

String   cloudLabel = "unknown";  // last label from cloud model
float    cloudScore = -1;
String   cloudFood  = "";

// ---------------------------------------------------------------- helpers
bool timeValid() { return time(nullptr) > 1700000000; }

void setLeds(const String& label) {
  bool isFresh = (label == "fresh");
  bool isRotten = (label == "rotten" ||
                   label == "deteriorating" ||
                   label == "use_soon");

  digitalWrite(LED_GREEN, isFresh ? HIGH : LOW);
  digitalWrite(LED_RED, isRotten ? HIGH : LOW);
}

float readGasMv() {
  uint32_t sum = 0;
  for (int i = 0; i < 32; i++) { sum += analogReadMilliVolts(GAS_PIN); delayMicroseconds(300); }
  return sum / 32.0f;
}

float mvToRsKohm(float mv) {
  float vout = (mv / 1000.0f) / GAS_DIVIDER_RATIO;     // undo voltage divider
  if (vout < 0.05f) vout = 0.05f;
  if (vout > GAS_VCC - 0.01f) vout = GAS_VCC - 0.01f;
  return GAS_RL_KOHM * (GAS_VCC - vout) / vout;
}

void calibrateR0() {                                    // do this in clean air, after warm-up
  Serial.println("[GAS] Calibrating R0 in clean air (10 s)...");
  float acc = 0;
  for (int i = 0; i < 50; i++) { acc += mvToRsKohm(readGasMv()); delay(200); }
  r0Kohm = acc / 50.0f;
  prefs.putFloat("r0", r0Kohm);
  Serial.printf("[GAS] R0 = %.2f kOhm (saved)\n", r0Kohm);
}

void newBatch() {
  batchStartTs = timeValid() ? (uint32_t)time(nullptr) : 0;
  prefs.putUInt("batch", batchStartTs);
  Serial.println("[BATCH] Storage timer reset");
}

Reading readSensors() {
#if SIMULATE_SENSORS
  {
    Reading sim;
    float t = millis() / 1000.0f;
    sim.dhtOk     = true;
    sim.tempC     = 24 + 3 * sinf(t / 120.0f);
    sim.hum       = 65 + 10 * sinf(t / 200.0f);
    sim.gasIndex  = 1.0f + (t / 60.0f) * 0.1f + 0.05f * sinf(t / 10.0f);   // slowly rising = food decaying
    sim.gasRsKohm = r0Kohm / sim.gasIndex;
    float vout    = GAS_VCC * GAS_RL_KOHM / (GAS_RL_KOHM + sim.gasRsKohm);
    sim.gasMv     = vout * GAS_DIVIDER_RATIO * 1000.0f;
    return sim;
  }
#endif
  Reading r;
  float t = dht.readTemperature(), h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {                           // one retry, DHT can be flaky
    delay(2100);
    t = dht.readTemperature(); h = dht.readHumidity();
  }
  r.dhtOk = !(isnan(t) || isnan(h));
  if (r.dhtOk) { lastTemp = t; lastHum = h; }
  r.tempC = lastTemp; r.hum = lastHum;

  r.gasMv     = readGasMv();
  r.gasRsKohm = mvToRsKohm(r.gasMv);
  r.gasIndex  = (r0Kohm > 0) ? r0Kohm / r.gasRsKohm : NAN;
  return r;
}

float storageHours() {
  if (!timeValid() || batchStartTs == 0) return -1;
  return ((uint32_t)time(nullptr) - batchStartTs) / 3600.0f;
}

// ---------------------------------------------------------------- freshness (local)
// PLACEHOLDER rules - only used when the cloud model is silent. Tune or replace with your model.
String ruleBasedLabel(const Reading& r, float& score) {
  score = 100;
  if (!isnan(r.gasIndex)) {
    if (r.gasIndex > 1.2f) score -= (r.gasIndex - 1.2f) * 40;
  }
  if (r.dhtOk) {
    if (r.tempC > 25) score -= (r.tempC - 25) * 2;
    if (r.hum > 90)   score -= (r.hum - 90) * 1.5f;
  }
  float sh = storageHours();
  if (sh > 72) score -= (sh - 72) * 0.15f;
  score = constrain(score, 0, 100);
  if (score >= 70) return "fresh";
  if (score >= 40) return "use_soon";
  return "deteriorating";
}

// Single entry point for local decisions. Swap in your exported model via USE_ONBOARD_MODEL.
String localFreshness(const Reading& r, float& score) {
#if USE_ONBOARD_MODEL
  // Feature order MUST match your training script
  float x[5] = { r.tempC, r.hum, r.gasIndex, r.gasRsKohm, storageHours() };
  int c = fresho_predict(x);
  score = (c == 0) ? 90 : (c == 1) ? 55 : 15;
  return (c == 0) ? "fresh" : (c == 1) ? "use_soon" : "deteriorating";
#else
  return ruleBasedLabel(r, score);
#endif
}

// ---------------------------------------------------------------- MQTT
void onMessage(char* topic, byte* payload, unsigned int len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) { Serial.println("[MQTT] bad JSON"); return; }

  if (strcmp(topic, topicResult) == 0) {
    cloudLabel   = doc["label"] | "unknown";
    cloudScore   = doc["score"] | -1.0f;
    cloudFood    = doc["food"]  | "";
    lastResultMs = millis();
    setLeds(cloudLabel);
    Serial.printf("[CLOUD] %s (%.0f) food=%s\n", cloudLabel.c_str(), cloudScore, cloudFood.c_str());
  }
  else if (strcmp(topic, topicCmd) == 0) {
    String cmd = doc["cmd"] | "";
    if      (cmd == "calibrate")   calibrateR0();
    else if (cmd == "new_batch")   newBatch();
    else if (cmd == "interval")    publishEveryS = constrain((int)(doc["value"] | 30), 5, 3600);
    else if (cmd == "publish_now") lastPublishMs = 0;
  }
}

bool ntpStarted = false;

void ensureWifi(bool wait = false) {
  if (WiFi.status() == WL_CONNECTED) {
    if (!ntpStarted) {
      Serial.printf("[WiFi] OK, IP %s\n", WiFi.localIP().toString().c_str());
      configTime(19800, 0, "pool.ntp.org", "time.google.com");   // IST (UTC+5:30)
      ntpStarted = true;
    }
    return;
  }
  ntpStarted = false;
  static uint32_t lastTry = 0;
  if (lastTry && millis() - lastTry < 15000) return;              // retry every 15 s, never block the loop
  lastTry = millis();
  Serial.printf("[WiFi] Connecting to %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  if (wait) {
    uint32_t t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) { delay(500); Serial.print("."); }
    Serial.println();
  }
}
WiFiClientSecure secureClient;

unsigned long lastSupabasePollMs = 0;

void pollSupabaseState() {

  if (WiFi.status() != WL_CONNECTED) return;

  secureClient.setInsecure(); // Temporary prototype testing only

  HTTPClient http;

  String url = String(SUPABASE_URL) +
    "/rest/v1/device_state?select=led_state&device_id=eq." +
    DEVICE_ID;

  http.begin(secureClient, url);

  http.addHeader("apikey", SUPABASE_KEY);
  http.addHeader("Accept", "application/json");

  int httpCode = http.GET();

  if (httpCode == 200) {

    String response = http.getString();

    JsonDocument doc;

    if (!deserializeJson(doc, response) && doc.size() > 0) {

      String state = doc[0]["led_state"] | "off";

      setLeds(state);

      Serial.printf("[SUPABASE] LED: %s\n", state.c_str());

    } else {

      setLeds("off");
      Serial.println("[SUPABASE] Invalid response");
      Serial.println(http.getString());
    }

  } else {

    setLeds("off");
    Serial.printf("[SUPABASE] HTTP error: %d\n", httpCode);
  }

  http.end();
}

void ensureMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqtt.connected()) return;
  if (millis() - lastMqttTryMs < 5000) return;                  // back-off, never block the loop
  lastMqttTryMs = millis();

  String cid = String(DEVICE_ID) + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  const char* u = strlen(MQTT_USER) ? MQTT_USER : nullptr;
  const char* p = strlen(MQTT_USER) ? MQTT_PASS : nullptr;

  if (mqtt.connect(cid.c_str(), u, p, topicStatus, 1, true, "offline")) {
    Serial.println("[MQTT] connected");
    mqtt.publish(topicStatus, "online", true);
    mqtt.subscribe(topicResult);
    mqtt.subscribe(topicCmd);
  } else {
    Serial.printf("[MQTT] failed rc=%d\n", mqtt.state());
  }
}

void publishReading(const Reading& r) {
  JsonDocument doc;
  doc["device"] = DEVICE_ID;
  doc["ts"]     = timeValid() ? (uint32_t)time(nullptr) : 0;
  if (r.dhtOk) { doc["temp_c"] = round(r.tempC * 10) / 10.0; doc["humidity"] = round(r.hum * 10) / 10.0; }
  doc["gas_mv"]      = (int)r.gasMv;
  doc["gas_rs_kohm"] = round(r.gasRsKohm * 100) / 100.0;
  if (!isnan(r.gasIndex)) doc["gas_index"] = round(r.gasIndex * 100) / 100.0;
  doc["gas_r0_kohm"] = round(r0Kohm * 100) / 100.0;
  doc["warmup"]      = !warmedUp;
  doc["storage_h"]   = round(storageHours() * 10) / 10.0;
  doc["rssi"]        = WiFi.RSSI();

  char buf[400];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  if (mqtt.connected() && mqtt.publish(topicSensors, (const uint8_t*)buf, n)) Serial.printf("[PUB] %s\n", buf);
  else Serial.printf("[PUB-FAIL] %s\n", buf);
}

// ---------------------------------------------------------------- setup / loop
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== FRESHO ESP32 node ===");

  pinMode(LED_GREEN, OUTPUT); pinMode(LED_YELLOW, OUTPUT); pinMode(LED_RED, OUTPUT);
  // LED self-test
  digitalWrite(LED_GREEN, 1); delay(200); digitalWrite(LED_YELLOW, 1); delay(200); digitalWrite(LED_RED, 1); delay(200);
  setLeds("");

  analogSetPinAttenuation(GAS_PIN, ADC_11db);           // 0 - ~3.1 V range
  dht.begin();

  prefs.begin("fresho", false);
  r0Kohm       = prefs.getFloat("r0", 0);
  batchStartTs = prefs.getUInt("batch", 0);
#if SIMULATE_SENSORS
  r0Kohm = 10.0f; warmedUp = true;      // fake baseline, no warm-up wait
  Serial.println("[SIM] SIMULATION MODE - sending fake sensor values");
#endif

  snprintf(topicSensors, sizeof(topicSensors), "fresho/%s/sensors", DEVICE_ID);
  snprintf(topicStatus,  sizeof(topicStatus),  "fresho/%s/status",  DEVICE_ID);
  snprintf(topicCmd,     sizeof(topicCmd),     "fresho/%s/cmd",     DEVICE_ID);
  snprintf(topicResult,  sizeof(topicResult),  "fresho/%s/result",  DEVICE_ID);

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(512);

  ensureWifi(true);
  ensureWifi();
  uint32_t t0 = millis();                                // wait briefly for NTP
  while (!timeValid() && millis() - t0 < 5000) delay(200);
  if (batchStartTs == 0) newBatch();
}

void loop() {

  ensureWifi();

  if (WiFi.status() == WL_CONNECTED &&
      millis() - lastSupabasePollMs >= 5000) {

    lastSupabasePollMs = millis();

    pollSupabaseState();
  }

  delay(10);
}