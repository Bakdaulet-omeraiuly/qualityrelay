/*
  QualityRelay17 -- reference ESP32 station firmware.

  This is a STARTING POINT, not a finished station. It reads one potentiometer as a
  stand-in dimensional sensor, debounces one confirm button, drives a 3-LED status bar
  through a 74HC595, and sounds a buzzer on HOLD -- then POSTs the raw ADC reading to
  the FastAPI reference endpoint added in qualityrelay17/api.py
  (POST /hardware/caliper-reading). Calibration (ADC -> mm) happens SERVER-SIDE in
  qualityrelay17/hardware_ingest.py on purpose, so recalibrating never needs a reflash.

  See docs/engineering/PHYSICAL_TEST_PLAYBOOK.md for the wiring diagram, the
  repeatability screen you must run before trusting any reading this sends, and why
  the server returns 503 until the station's signing key is provisioned server-side
  (python scripts/provision_station_keys.py -> .env; the key never lives on this board).

  Wiring (adjust pins to your board; avoid ADC2 pins -- they conflict with WiFi):
    Potentiometer wiper -> GPIO34 (ADC1_CH6, input only, no pull resistor needed)
    Confirm button      -> GPIO32, other leg to GND, INPUT_PULLUP in software
    74HC595: DS->GPIO25, SHCP->GPIO26, STCP->GPIO27, drives 3 LEDs (green/amber/red)
      through 3x current-limiting resistors from the 120pc resistor pack
    Buzzer (active)      -> through a PN2222 (base via ~1k resistor from GPIO33,
      emitter->GND, collector->buzzer->VCC); put one of the diodes across the buzzer
      leads (cathode to VCC) for flyback protection
    Photoresistor + 4N35 bin sensor is a SEPARATE module -- see bin_sensor.ino in
    this same folder once you build it; keep that signal path electrically isolated
    from this station's actuation-free sensing-only wiring.
*/

#include <WiFi.h>
#include <HTTPClient.h>

// ---- fill these in for your own network/server; do not commit real values ----
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://YOUR_SERVER_HOST:8000/hardware/caliper-reading";
const char* STATION_ID = "slot";             // or "tab" -- matches contracts.py station_id
const char* CALIBRATION_ID = "cal-slot-01";  // bump this string whenever you re-zero the pot

// ---- BACK-01 signed envelope -------------------------------------------------------------
// Mirrors qualityrelay17/station_auth.py exactly. The server verifies BEFORE trusting the body:
//   canonical = METHOD \n PATH \n STATION_ID \n unix_ts \n nonce \n sha256hex(body)
//   X-Station-Signature = hex HMAC-SHA256(STATION_DEVICE_KEY, canonical)
// Needs real time: configTime() in setup() and waitForTime() before the first POST.
#include "mbedtls/md.h"
#include <time.h>

const char* STATION_DEVICE_KEY = "PASTE_OUTPUT_OF__provision_station_keys.py --show-device-key";  // do not commit a real value
const char* SERVER_PATH = "/hardware/caliper-reading";  // must equal the path part of SERVER_URL

static String hexOf(const unsigned char* buf, size_t n) {
  static const char* d = "0123456789abcdef"; String s; s.reserve(n * 2);
  for (size_t i = 0; i < n; i++) { s += d[buf[i] >> 4]; s += d[buf[i] & 0xF]; }
  return s;
}
static String sha256Hex(const String& msg) {
  unsigned char out[32];
  mbedtls_md_context_t ctx; mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 0);
  mbedtls_md_starts(&ctx); mbedtls_md_update(&ctx, (const unsigned char*)msg.c_str(), msg.length());
  mbedtls_md_finish(&ctx, out); mbedtls_md_free(&ctx);
  return hexOf(out, 32);
}
static String hmacSha256Hex(const char* key, const String& msg) {
  unsigned char out[32];
  mbedtls_md_context_t ctx; mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*)key, strlen(key));
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)msg.c_str(), msg.length());
  mbedtls_md_hmac_finish(&ctx, out); mbedtls_md_free(&ctx);
  return hexOf(out, 32);
}
static String randomHex32() {  // 4 x 32-bit hardware RNG words -> 32 hex chars (server needs >= 16)
  char b[33]; snprintf(b, sizeof b, "%08x%08x%08x%08x", esp_random(), esp_random(), esp_random(), esp_random());
  return String(b);
}
static void waitForTime() {
  while (time(nullptr) < 1000000000) { delay(200); Serial.print("t"); }  // until NTP has set the clock
}
// Attach X-Station-* headers for `body`. Returns false (and skips the POST) if the clock is not set.
static bool addStationEnvelope(HTTPClient& http, const String& body) {
  time_t now = time(nullptr);
  if (now < 1000000000) { Serial.println("clock not set; refusing to send an unsigned/undated reading"); return false; }
  String nonce = randomHex32();
  String canonical = String("POST\n") + SERVER_PATH + "\n" + STATION_ID + "\n" + String((unsigned long)now) + "\n" + nonce + "\n" + sha256Hex(body);
  http.addHeader("X-Station-Id", STATION_ID);
  http.addHeader("X-Station-Timestamp", String((unsigned long)now));
  http.addHeader("X-Station-Nonce", nonce);
  http.addHeader("X-Station-Signature", hmacSha256Hex(STATION_DEVICE_KEY, canonical));
  return true;
}
// Boot nonce so event_ids never repeat after a reset (millis() restarts at 0; the server
// answers 409 to a reused id).
static String BOOT_NONCE = "";
// --------------------------------------------------------------------------------------------

const int PIN_POT = 34;
const int PIN_BUTTON = 32;
const int PIN_BUZZER = 33;
const int PIN_595_DATA = 25;
const int PIN_595_CLOCK = 26;
const int PIN_595_LATCH = 27;

unsigned long specimen_counter = 0;
unsigned long last_press_ms = 0;
const unsigned long DEBOUNCE_MS = 250;

void shiftStatus(bool green, bool amber, bool red) {
  byte bits = (green ? 0b001 : 0) | (amber ? 0b010 : 0) | (red ? 0b100 : 0);
  digitalWrite(PIN_595_LATCH, LOW);
  shiftOut(PIN_595_DATA, PIN_595_CLOCK, MSBFIRST, bits);
  digitalWrite(PIN_595_LATCH, HIGH);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_595_DATA, OUTPUT);
  pinMode(PIN_595_CLOCK, OUTPUT);
  pinMode(PIN_595_LATCH, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  shiftStatus(false, true, false);  // amber: not yet connected

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
  configTime(0, 0, "pool.ntp.org", "time.google.com");  // envelope timestamps must be real time
  waitForTime();
  BOOT_NONCE = randomHex32().substring(0, 8);
    delay(300);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
  shiftStatus(true, false, false);  // green: idle, ready
}

bool postReading(int adc_value, float uncertainty_mm) {
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  specimen_counter++;
  String specimen_id = "S-" + String(specimen_counter);
  String event_id = "evt-" + String(STATION_ID) + "-" + BOOT_NONCE + "-" + String(millis());

  String body = String("{") +
    "\"event_id\":\"" + event_id + "\"," +
    "\"specimen_id\":\"" + specimen_id + "\"," +
    "\"station_id\":\"" + STATION_ID + "\"," +
    "\"adc_value\":" + String(adc_value) + "," +
    "\"uncertainty_mm\":" + String(uncertainty_mm, 4) + "," +
    "\"calibration_id\":\"" + CALIBRATION_ID + "\"" +
    "}";

  if (!addStationEnvelope(http, body)) { http.end(); return; }
  int code = http.POST(body);  // 401 = envelope rejected (key/clock/nonce), 403 = wrong station for this path
  Serial.println("POST -> " + String(code) + ": " + http.getString());
  http.end();
  return code == 200;
}

void loop() {
  // Average a few ADC samples to cut quantization noise before sending.
  long sum = 0;
  const int SAMPLES = 16;
  for (int i = 0; i < SAMPLES; i++) { sum += analogRead(PIN_POT); delay(2); }
  int adc_value = sum / SAMPLES;

  bool pressed = (digitalRead(PIN_BUTTON) == LOW);
  if (pressed && millis() - last_press_ms > DEBOUNCE_MS) {
    last_press_ms = millis();
    shiftStatus(false, true, false);  // amber while sending

    // uncertainty_mm is a PLACEHOLDER -- replace with the value you measured in
    // your own ten-reposition repeatability screen (PHYSICAL_TEST_PLAYBOOK.md step 1),
    // not this guessed number.
    bool ok = postReading(adc_value, 0.05);

    if (ok) {
      shiftStatus(true, false, false);
    } else {
      shiftStatus(false, false, true);  // red: send failed, server not ready / key missing
      digitalWrite(PIN_BUZZER, HIGH);
      delay(150);
      digitalWrite(PIN_BUZZER, LOW);
    }
  }
}
