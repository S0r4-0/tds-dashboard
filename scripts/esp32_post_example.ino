/*
 * Arduino UNO R4 WiFi - TDS Sensor + HTTP POST (JSON)
 * 
 * Reads analog TDS sensor and sends data via HTTP POST (JSON) 
 * to a Python FastAPI or Flask dashboard server.
 * 
 * Hardware:
 * - TDS Sensor Signal → A0
 * - TDS Sensor VCC → 5V
 * - TDS Sensor GND → GND
 * 
 * Dependencies:
 * - WiFiS3 (built-in for UNO R4 WiFi)
 * - ArduinoHttpClient
 * - ArduinoJson
 */

#include <WiFiS3.h>
#include <ArduinoHttpClient.h>
#include <ArduinoJson.h>
#include <time.h>

// ===== CONFIGURATION =====
const char* ssid = "Galaxy F14 5G 91C7";           // Wi-Fi name
const char* password = "Pratik123";    // Wi-Fi password
const char* serverAddress = "10.227.227.77"; // Laptop/Server IP
int serverPort = 5000;                       // FastAPI port
const char* endpoint = "/api/tds";           // API endpoint
const char* deviceID = "uno-r4-01";          // Unique identifier
// ==========================

// ===== SENSOR CONFIG =====
#define TdsSensorPin A0
#define VREF 5.0
#define SCOUNT 30
#define POST_INTERVAL 2000  // every 2s
// ==========================

WiFiClient wifi;
HttpClient client = HttpClient(wifi, serverAddress, serverPort);

int analogBuffer[SCOUNT];
int analogBufferIndex = 0;
float temperature = 25.0;
float tdsValue = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n=================================");
  Serial.println("TDS Monitor - Arduino UNO R4 WiFi");
  Serial.println("=================================");

  pinMode(TdsSensorPin, INPUT);
  connectWiFi();
}

void loop() {
  static unsigned long sampleTime = millis();
  if (millis() - sampleTime > 40U) {
    sampleTime = millis();
    analogBuffer[analogBufferIndex] = analogRead(TdsSensorPin);
    analogBufferIndex++;
    if (analogBufferIndex >= SCOUNT) analogBufferIndex = 0;
  }

  static unsigned long postTime = millis();
  if (millis() - postTime > POST_INTERVAL) {
    postTime = millis();

    float averageVoltage = getMedianAverage(analogBuffer, SCOUNT) * (float)VREF / 1023.0;

    float compensationCoefficient = 1.0 + 0.02 * (temperature - 25.0);
    float compensationVoltage = averageVoltage / compensationCoefficient;

    // EC and TDS conversion
    float ecValue = (133.42 * pow(compensationVoltage, 3)
                    - 255.86 * pow(compensationVoltage, 2)
                    + 857.39 * compensationVoltage) / 1000.0;
    tdsValue = ecValue * 0.5 * 1000;

    if (tdsValue < 0) tdsValue = 0;

    // Debug output
    Serial.print("TDS: ");
    Serial.print(tdsValue, 1);
    Serial.print(" ppm | Voltage: ");
    Serial.print(averageVoltage, 2);
    Serial.println(" V");

    // Send to server
    sendTDSData(tdsValue, averageVoltage);
  }
}

void connectWiFi() {
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(ssid);
  
  while (WiFi.begin(ssid, password) != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\n✓ Wi-Fi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void sendTDSData(float tds, float voltage) {
  if (WiFi.status() == WL_CONNECTED) {
    StaticJsonDocument<200> doc;
    doc["device_id"] = deviceID;
    doc["device_ip"] = WiFi.localIP().toString();
    doc["tds"] = tds;
    doc["voltage"] = voltage;
    doc["timestamp"] = getISO8601Timestamp();

    String jsonString;
    serializeJson(doc, jsonString);

    client.beginRequest();
    client.post(endpoint);
    client.sendHeader("Content-Type", "application/json");
    client.sendHeader("Content-Length", jsonString.length());
    client.beginBody();
    client.print(jsonString);
    client.endRequest();

    int statusCode = client.responseStatusCode();
    String response = client.responseBody();

    Serial.print("→ POST status: ");
    Serial.println(statusCode);
    Serial.print("Response: ");
    Serial.println(response);
  } else {
    Serial.println("✗ Wi-Fi not connected, skipping POST");
    connectWiFi();
  }
}
String getISO8601Timestamp() {
  time_t now = time(nullptr);
  if (now < 1000) return "1970-01-01T00:00:00Z";  // fallback
  
  struct tm timeinfo;
  gmtime_r(&now, &timeinfo);  // safer for embedded

  char buffer[25];
  sprintf(buffer, "%04d-%02d-%02dT%02d:%02d:%02dZ",
          timeinfo.tm_year + 1900,
          timeinfo.tm_mon + 1,
          timeinfo.tm_mday,
          timeinfo.tm_hour,
          timeinfo.tm_min,
          timeinfo.tm_sec);
  return String(buffer);
}

int getMedianAverage(int *arr, int number) {
  int temp;
  int sorted[number];
  memcpy(sorted, arr, number * sizeof(int));

  for (int i = 0; i < number - 1; i++) {
    for (int j = i + 1; j < number; j++) {
      if (sorted[i] > sorted[j]) {
        temp = sorted[i];
        sorted[i] = sorted[j];
        sorted[j] = temp;
      }
    }
  }

  if (number % 2 == 0)
    return (sorted[number/2] + sorted[number/2 - 1]) / 2;
  else
    return sorted[number/2];
}
