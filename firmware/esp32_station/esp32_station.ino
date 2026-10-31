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
  String event_id = "evt-" + String(STATION_ID) + "-" + String(millis());

  String body = String("{") +
    "\"event_id\":\"" + event_id + "\"," +
    "\"specimen_id\":\"" + specimen_id + "\"," +
    "\"station_id\":\"" + STATION_ID + "\"," +
    "\"adc_value\":" + String(adc_value) + "," +
    "\"uncertainty_mm\":" + String(uncertainty_mm, 4) + "," +
    "\"calibration_id\":\"" + CALIBRATION_ID + "\"" +
    "}";

  int code = http.POST(body);
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
