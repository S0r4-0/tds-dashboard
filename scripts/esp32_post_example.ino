// Fixed: UNO R4 WiFi - TDS Sensor -> HTTP POST (JSON)
// Flash this to your UNO R4 WiFi

#include <WiFiS3.h>
#include <ArduinoHttpClient.h>
#include <ArduinoJson.h>

// ===== CONFIGURATION =====
const char* ssid = "Vedant's M34";           // Wi-Fi name
const char* password = "9n6hr5gxqa67ges";                // Wi-Fi password
const char* serverAddress = "192.168.156.77";       // Laptop/Server IP (must be reachable)
int serverPort = 5000;                             // FastAPI port
const char* endpoint = "/api/tds";                 // API endpoint
const char* deviceID = "uno-r4-01";                // Unique identifier
// ==========================

#define TdsSensorPin A0
#define VREF 5.0
#define SCOUNT 30
#define POST_INTERVAL 2000  // ms

WiFiClient wifi;
HttpClient client = HttpClient(wifi, serverAddress, serverPort);

int analogBuffer[SCOUNT];
int analogBufferIndex = 0;
float temperature = 25.0;
float tdsValue = 0.0;

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

    float avgRaw = getMedianAverage(analogBuffer, SCOUNT);
    // UNO ADC is 0..1023
    float averageVoltage = avgRaw * (float)VREF / 1023.0;

    float compensationCoefficient = 1.0 + 0.02 * (temperature - 25.0);
    float compensationVoltage = averageVoltage / compensationCoefficient;

    float ecValue = (133.42 * pow(compensationVoltage, 3)
                    - 255.86 * pow(compensationVoltage, 2)
                    + 857.39 * compensationVoltage) / 1000.0;
    tdsValue = ecValue * 0.5 * 1000.0;

    if (tdsValue < 0.0) tdsValue = 0.0;

    // Debug
    Serial.print("TDS: ");
    Serial.print(tdsValue, 1);
    Serial.print(" ppm | Voltage: ");
    Serial.print(averageVoltage, 2);
    Serial.println(" V");

    // Send to server (omit timestamp — server will add if missing)
    sendTDSData(tdsValue, averageVoltage);
  }
}

void connectWiFi() {
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password); // call once

  unsigned long start = millis();
  const unsigned long timeout = 20000UL; // 20s total timeout
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (millis() - start > timeout) {
      Serial.println();
      Serial.println("✗ Wi-Fi connect timeout, retrying...");
      WiFi.disconnect();
      delay(500);
      WiFi.begin(ssid, password);
      start = millis();
    }
  }

  Serial.println();
  Serial.println("✓ Wi-Fi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void sendTDSData(float tds, float voltage) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("✗ Wi-Fi not connected, attempting reconnect...");
    connectWiFi();
    return;
  }

  // JSON payload
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceID;
  doc["device_ip"] = WiFi.localIP().toString();
  doc["tds"] = tds;
  doc["voltage"] = voltage;
  // do not send timestamp — server will add one

  String jsonString;
  serializeJson(doc, jsonString);

  // Send POST
  client.beginRequest();
  client.post(endpoint);
  client.sendHeader("Content-Type", "application/json");
  client.sendHeader("Content-Length", jsonString.length());
  client.sendHeader("Connection", "close"); // help ensure server closes socket
  client.beginBody();
  client.print(jsonString);
  client.endRequest();

  int statusCode = client.responseStatusCode();
  String response = client.responseBody();

  Serial.print("→ POST status: ");
  Serial.println(statusCode);
  if (response.length() > 0) {
    Serial.print("Response: ");
    Serial.println(response);
  }

  if (statusCode < 0 || statusCode >= 400) {
    Serial.println("✗ Bad response — checking Wi-Fi & retry later");
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi lost — reconnecting...");
      connectWiFi();
    }
  }

  // small delay to avoid socket starvation
  delay(100);
}

int getMedianAverage(int *arr, int number) {
  // Make a local copy so original buffer isn't permanently sorted
  int temp;
  int sortedArr[number];
  for (int i = 0; i < number; i++) sortedArr[i] = arr[i];

  // Simple sort (sufficient for SCOUNT=30)
  for (int i = 0; i < number - 1; i++) {
    for (int j = i + 1; j < number; j++) {
      if (sortedArr[i] > sortedArr[j]) {
        temp = sortedArr[i];
        sortedArr[i] = sortedArr[j];
        sortedArr[j] = temp;
      }
    }
  }

  if (number % 2 == 0)
    return (sortedArr[number/2] + sortedArr[number/2 - 1]) / 2;
  else
    return sortedArr[number/2];
}
