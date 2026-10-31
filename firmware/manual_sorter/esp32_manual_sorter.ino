/*
  QualityRelay manual-track servo sorter prototype.

  Serial Monitor stages one route:
    P = PASS
    H = HOLD
    R = REJECT

  The servo moves only after the physical confirmation button is pressed.
  Install the ESP32Servo library before compiling.

  Wiring:
    Servo signal -> GPIO13
    Servo power  -> external regulated supply matched to the servo
    Servo ground -> external supply ground
    External supply ground -> ESP32 GND (common signal reference)
    Button -> GPIO32 and GND (INPUT_PULLUP)

  Never power the servo from an ESP32 GPIO or the 3.3 V pin.
*/

#include <ESP32Servo.h>
#include <ctype.h>

const int SERVO_PIN = 13;
const int CONFIRM_BUTTON_PIN = 32;

// Calibrate these with the flap disconnected first, then in 5-degree steps.
const int PASS_ANGLE = 35;
const int HOLD_ANGLE = 90;
const int REJECT_ANGLE = 145;

const unsigned long DEBOUNCE_MS = 250;
const unsigned long STAGE_TIMEOUT_MS = 15000;

Servo diverter;
char pendingRoute = '\0';
int pendingAngle = HOLD_ANGLE;
unsigned long stagedAtMs = 0;
unsigned long lastPressMs = 0;
bool lastButtonPressed = false;

void clearPending(const char* reason) {
  pendingRoute = '\0';
  pendingAngle = HOLD_ANGLE;
  stagedAtMs = 0;
  Serial.println(reason);
}

bool routeToAngle(char route, int& angle) {
  switch (route) {
    case 'P': angle = PASS_ANGLE; return true;
    case 'H': angle = HOLD_ANGLE; return true;
    case 'R': angle = REJECT_ANGLE; return true;
    default: return false;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(CONFIRM_BUTTON_PIN, INPUT_PULLUP);

  diverter.setPeriodHertz(50);
  diverter.attach(SERVO_PIN, 500, 2400);
  diverter.write(HOLD_ANGLE);

  Serial.println("QualityRelay sorter ready.");
  Serial.println("Type P, H, or R, then press the physical confirmation button.");
}

void loop() {
  if (Serial.available() > 0) {
    char route = (char)toupper(Serial.read());
    int requestedAngle = HOLD_ANGLE;

    if (routeToAngle(route, requestedAngle)) {
      pendingRoute = route;
      pendingAngle = requestedAngle;
      stagedAtMs = millis();
      Serial.print("Route staged: ");
      Serial.print(pendingRoute);
      Serial.println(". Press confirmation button within 15 seconds.");
    }
  }

  if (pendingRoute != '\0' && millis() - stagedAtMs > STAGE_TIMEOUT_MS) {
    clearPending("Staged route expired; gate did not move.");
  }

  bool pressed = digitalRead(CONFIRM_BUTTON_PIN) == LOW;
  bool newPress = pressed && !lastButtonPressed;
  lastButtonPressed = pressed;

  if (newPress && millis() - lastPressMs > DEBOUNCE_MS) {
    lastPressMs = millis();

    if (pendingRoute == '\0') {
      Serial.println("No route staged; gate did not move.");
    } else {
      diverter.write(pendingAngle);
      Serial.print("AUTHORIZED MOVE -> route ");
      Serial.print(pendingRoute);
      Serial.print(", angle ");
      Serial.println(pendingAngle);
      clearPending("Route consumed; stage the next specimen separately.");
    }
  }
}
