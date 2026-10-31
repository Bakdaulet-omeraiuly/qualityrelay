/*
  QualityRelay17 -- independent bin-acknowledgment sensor (photoresistor + 4N35).

  Purpose: a sensing path that is ELECTRICALLY ISOLATED from whatever told the sorter to
  move a part (actuation.py's SorterInterlock never touches this circuit). That isolation
  is the whole point of H5 / E12 / E13 in docs/research/EXPERIMENT_PROTOCOL.md -- an
  "independent route acknowledgment" that a software bug in the actuation path cannot
  silently also flip.

  Circuit (two separate loops on either side of the 4N35's internal LED/phototransistor):
    Primary (sensing) loop: VCC -- photoresistor -- node A -- resistor (~1k, from the
      120pc pack) -- 4N35 pin 1 (LED anode) -- 4N35 pin 2 (LED cathode) -- GND.
      Light on the LDR lets enough current through to light the 4N35's internal LED;
      a part blocking the LDR starves that current.
    Secondary (logic) loop, NOT sharing a ground reference requirement with the above:
      ESP32 3.3V -- pull-up resistor (~10k) -- GPIO pin AND 4N35 pin 6 (collector);
      4N35 pin 5 (emitter) -- GND.
      Phototransistor conducts only while the LED side is lit, pulling the GPIO LOW;
      blocked LDR -> LED off -> phototransistor off -> GPIO reads HIGH (pulled up).
    So: GPIO HIGH == something is blocking light at the bin == part present.
    Tune the primary-loop resistor for your ambient lighting before trusting this --
    a dim room will not get it right out of the box.

  Posts to POST /hardware/bin-ack (added in qualityrelay17/api.py). This firmware only
  reports what it sensed; it has no authority to stage or confirm an actuation request --
  that handshake happens server-side in actuation.SorterInterlock.acknowledge(), which
  takes this event's event_id as its required sensor_event_id argument.
*/

#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://YOUR_SERVER_HOST:8000/hardware/bin-ack";
const char* STATION_ID = "sorter";
const char* BIN_NAME = "PASS";  // one physical sensor per bin; flash separately per bin

// ---- BACK-01 signed envelope -------------------------------------------------------------
// Mirrors qualityrelay17/station_auth.py exactly. The server verifies BEFORE trusting the body:
//   canonical = METHOD \n PATH \n STATION_ID \n unix_ts \n nonce \n sha256hex(body)
//   X-Station-Signature = hex HMAC-SHA256(STATION_DEVICE_KEY, canonical)
// Needs real time: configTime() in setup() and waitForTime() before the first POST.
#include "mbedtls/md.h"
#include <time.h>

const char* STATION_DEVICE_KEY = "PASTE_OUTPUT_OF__provision_station_keys.py --show-device-key";  // do not commit a real value
const char* SERVER_PATH = "/hardware/bin-ack";            // must equal the path part of SERVER_URL

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

const int PIN_SENSE = 35;  // input-only ADC-capable pin also works fine as digital input here

bool last_blocked = false;
unsigned long specimen_counter = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SENSE, INPUT);  // external pull-up from the 4N35 side; no INPUT_PULLUP needed
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print("."); }
  configTime(0, 0, "pool.ntp.org", "time.google.com");  // envelope timestamps must be real time
  waitForTime();
  BOOT_NONCE = randomHex32().substring(0, 8);
  Serial.println("\nBin sensor online: " + WiFi.localIP().toString());
}

void postAck(bool blocked) {
  if (!blocked) return;  // hardware_ingest.bin_ack_evidence() refuses a false reading anyway
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  specimen_counter++;
  String event_id = "evt-bin-" + String(STATION_ID) + "-" + BOOT_NONCE + "-" + String(millis());
  // In a real run, specimen_id should come from whatever upstream event this part already
  // carries (QR/ID), not a local counter -- this placeholder exists only so the sketch runs.
  String specimen_id = "S-" + String(specimen_counter);

  String body = String("{") +
    "\"event_id\":\"" + event_id + "\"," +
    "\"specimen_id\":\"" + specimen_id + "\"," +
    "\"station_id\":\"" + STATION_ID + "\"," +
    "\"bin_name\":\"" + BIN_NAME + "\"," +
    "\"photoresistor_blocked\":true" +
    "}";

  if (!addStationEnvelope(http, body)) { http.end(); return; }
  int code = http.POST(body);  // 401 = envelope rejected (key/clock/nonce), 403 = wrong station for this path
  // 200 body is {"evidence":{...},"interlock":{"status":...}}: PHYSICAL_ROUTE_CONFIRMED,
  // ROUTE_MISMATCH (wrong bin, route faulted), NO_PENDING_ACTION (nothing staged for this
  // specimen). 409 = this event_id was already recorded (exact replay; BOOT_NONCE prevents reuse after reset).
  Serial.println("ACK POST -> " + String(code) + ": " + http.getString());
  http.end();
}

void loop() {
  bool blocked = digitalRead(PIN_SENSE) == HIGH;
  if (blocked && !last_blocked) {
    postAck(true);  // rising edge only: one ACK per part arrival, not one per poll
  }
  last_blocked = blocked;
  delay(50);
}
