/*
  QualityRelay measurement station — spare ESP32.

  Sends one caliper/gauge reading per button press over USB serial at 115200, so
  web/measurement_logger.html can log it without typing (use its "Connect ESP32" button,
  which uses the browser Web Serial API in Chrome/Edge).

  The operator-confirmed caliper value stays authoritative. A reading from this board is
  PHYSICAL_CAPTURE evidence, not an automatic verdict (see AGENTS.md and
  qualityrelay17/hardware_ingest.py).

  ---------------------------------------------------------------------------------------
  Reading source — pick one:

    SOURCE_POT      A linear potentiometer / slide gauge on an ADC pin. Reliable to wire,
                    but lower precision than a real caliper and it MUST be calibrated.
                    This mirrors potentiometer_to_mm() in qualityrelay17/hardware_ingest.py.

    SOURCE_CALIPER  A digital caliper's 1.5 V data port (precise, your real caliper).
                    ADVANCED and UNTESTED here: needs level shifting and brand-specific
                    frame decoding. Left as a stub that returns NAN until you implement it.
  ---------------------------------------------------------------------------------------

  Output lines (the logger parses these):
    "# QRM ready"                        banner / comment   -> ignored
    "<value_mm>"                         a bare number       -> fills the focused field
    "QRM,<feature>,<location>,<value>"   a full row          -> appended directly

  By default this sketch prints a bare number (simplest, most robust). Set SEND_FULL_ROW
  to 1 and edit FEATURE/LOCATION to emit full rows instead.

  Wiring is documented in web/measurement_logger.html, tab 2.
*/

#define SOURCE_POT      1
#define SOURCE_CALIPER  2
#define READ_SOURCE     SOURCE_POT   // <-- choose SOURCE_POT or SOURCE_CALIPER

#define USE_LCD         0            // 1 to drive a QAPASS 16x2 I2C LCD (needs LiquidCrystal_I2C)
#define SEND_FULL_ROW   0            // 1 to print "QRM,feature,location,value" instead of a bare number

#include <math.h>
#if USE_LCD
  #include <Wire.h>
  #include <LiquidCrystal_I2C.h>
  LiquidCrystal_I2C lcd(0x27, 16, 2);   // many QAPASS modules are 0x27; some are 0x3F
#endif

// ----- pins -----
const int POT_PIN           = 34;   // ADC1, input-only, safe with Wi-Fi
const int BUTTON_PIN        = 32;   // "send reading" button to GND, INPUT_PULLUP
const int CALIPER_CLK_PIN   = 25;   // SOURCE_CALIPER only, via level shifter
const int CALIPER_DATA_PIN  = 26;   // SOURCE_CALIPER only, via level shifter

// ----- potentiometer calibration (SOURCE_POT) -----
// Fit these to YOUR gauge: record >= 5 known caliper positions and the raw ADC at each,
// then set the endpoints (or replace mapRawToMm() with your own fit).
const float ADC_MIN = 0.0f;
const float ADC_MAX = 4095.0f;      // ESP32 ADC is 12-bit
const float MM_MIN  = 0.0f;
const float MM_MAX  = 25.0f;        // gauge travel in mm at ADC_MAX

// ----- what a full row describes (SEND_FULL_ROW only) -----
const char* FEATURE  = "width";
const char* LOCATION = "mid";

const unsigned long DEBOUNCE_MS = 250;
unsigned long lastPressMs = 0;
bool lastPressed = false;

float mapRawToMm(int raw) {
  if (raw < ADC_MIN) raw = ADC_MIN;
  if (raw > ADC_MAX) raw = ADC_MAX;
  return MM_MIN + (raw - ADC_MIN) * (MM_MAX - MM_MIN) / (ADC_MAX - ADC_MIN);
}

// Average several ADC samples to steady the reading.
float readPotMm() {
  long acc = 0;
  const int N = 16;
  for (int i = 0; i < N; i++) { acc += analogRead(POT_PIN); delay(2); }
  return mapRawToMm((int)(acc / N));
}

// SOURCE_CALIPER: decode the caliper's 24-bit frame here. Brand-specific; returns NAN
// until implemented. See the caveats in web/measurement_logger.html, tab 2.
float readCaliperMm() {
  return NAN;
}

float readValueMm() {
#if READ_SOURCE == SOURCE_POT
  return readPotMm();
#else
  return readCaliperMm();
#endif
}

void emitReading(float mm) {
  if (isnan(mm)) {
    Serial.println("# QRM no reading (caliper decode not implemented)");
    return;
  }
#if SEND_FULL_ROW
  Serial.print("QRM,"); Serial.print(FEATURE); Serial.print(",");
  Serial.print(LOCATION); Serial.print(","); Serial.println(mm, 2);
#else
  Serial.println(mm, 2);   // bare number -> fills the focused field in the logger
#endif
#if USE_LCD
  lcd.clear(); lcd.setCursor(0, 0); lcd.print("meas: "); lcd.print(mm, 2);
  lcd.setCursor(0, 1); lcd.print("LOGGED");
#endif
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
#if READ_SOURCE == SOURCE_POT
  analogReadResolution(12);
#else
  pinMode(CALIPER_CLK_PIN, INPUT);
  pinMode(CALIPER_DATA_PIN, INPUT);
#endif
#if USE_LCD
  Wire.begin(21, 22);
  lcd.init(); lcd.backlight();
  lcd.print("QualityRelay"); lcd.setCursor(0, 1); lcd.print("measure ready");
#endif
  Serial.println("# QRM ready");
  Serial.println("# press the button to send one reading");
}

void loop() {
  bool pressed = digitalRead(BUTTON_PIN) == LOW;
  bool newPress = pressed && !lastPressed;
  lastPressed = pressed;
  if (newPress && millis() - lastPressMs > DEBOUNCE_MS) {
    lastPressMs = millis();
    emitReading(readValueMm());
  }
}
