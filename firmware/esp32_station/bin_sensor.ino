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

const int PIN_SENSE = 35;  // input-only ADC-capable pin also works fine as digital input here

bool last_blocked = false;
unsigned long specimen_counter = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SENSE, INPUT);  // external pull-up from the 4N35 side; no INPUT_PULLUP needed
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print("."); }
  Serial.println("\nBin sensor online: " + WiFi.localIP().toString());
}

void postAck(bool blocked) {
  if (!blocked) return;  // hardware_ingest.bin_ack_evidence() refuses a false reading anyway
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  specimen_counter++;
  String event_id = "evt-bin-" + String(STATION_ID) + "-" + String(millis());
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

  int code = http.POST(body);
  // 200 body is {"evidence":{...},"interlock":{"status":...}}: PHYSICAL_ROUTE_CONFIRMED,
  // ROUTE_MISMATCH (wrong bin, route faulted), NO_PENDING_ACTION (nothing staged for this
  // specimen). 409 = this event_id was already recorded (replay / millis() reuse after reboot).
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
