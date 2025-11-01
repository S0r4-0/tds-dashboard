/*
 * Keyestudio / Gravity TDS Sensor - Dashboard Compatible Version
 * Modified to send CSV data format for TDS monitoring dashboard
 * 
 * Hardware:
 * - TDS Sensor Signal → A0
 * - TDS Sensor VCC → 5V
 * - TDS Sensor GND → GND
 * 
 * Output Format: device_id,tds,voltage,timestamp
 * Example: arduino-01,345.7,2.34,
 */

// ===== CONFIGURATION - CHANGE THIS =====
#define DEVICE_ID "arduino-01"     // Unique identifier for this Arduino
// =======================================

#define TdsSensorPin A0
#define VREF 5.0                   // Reference voltage for ADC
#define SCOUNT 30                  // Number of samples for smoothing

int analogBuffer[SCOUNT];          // Array to store analog readings
int analogBufferTemp[SCOUNT];
int analogBufferIndex = 0;

float averageVoltage = 0;
float tdsValue = 0;
float temperature = 25;            // Default temperature (°C) - can be adjusted

void setup()
{
  Serial.begin(115200);            // Changed from 9600 to 115200 for dashboard
  pinMode(TdsSensorPin, INPUT);
  
  delay(1000);                     // Wait for serial connection
  
  // Optional: Print header once (comment out if causes issues)
  // Serial.println("device_id,tds,voltage,");
}

void loop()
{
  static unsigned long analogSampleTimepoint = millis();
  if (millis() - analogSampleTimepoint > 40U)  // every 40ms, read ADC
  {
    analogSampleTimepoint = millis();
    analogBuffer[analogBufferIndex] = analogRead(TdsSensorPin);  // read ADC
    analogBufferIndex++;
    if (analogBufferIndex == SCOUNT)
      analogBufferIndex = 0;
  }

  static unsigned long printTimepoint = millis();
  if (millis() - printTimepoint > 1000U)  // Changed from 800ms to 1000ms (1 second)
  {
    printTimepoint = millis();
    
    // Copy buffer for processing
    for (int i = 0; i < SCOUNT; i++)
      analogBufferTemp[i] = analogBuffer[i];

    // Convert to voltage
    averageVoltage = getMedianAverage(analogBufferTemp, SCOUNT) * (float)VREF / 1024.0;
    
    // Temperature compensation
    float compensationCoefficient = 1.0 + 0.02 * (temperature - 25.0);
    float compensationVoltage = averageVoltage / compensationCoefficient;

    // Calculate EC (Electrical Conductivity) in ms/cm
    float ecValue = (133.42 * compensationVoltage * compensationVoltage * compensationVoltage
                     - 255.86 * compensationVoltage * compensationVoltage
                     + 857.39 * compensationVoltage) / 1000.0;

    // Convert EC to TDS (Total Dissolved Solids)
    // TDS = EC * K (K=0.5 for most solutions) * 1000 (to convert to ppm)
    tdsValue = ecValue * 0.5 * 1000;
    
    // Ensure non-negative value
    if (tdsValue < 0) {
      tdsValue = 0;
    }

    // ===== OUTPUT CSV FORMAT FOR DASHBOARD =====
    // Format: device_id,tds,voltage,timestamp
    Serial.print(DEVICE_ID);
    Serial.print(",");
    Serial.print(tdsValue, 1);           // TDS with 1 decimal place
    Serial.print(",");
    Serial.print(averageVoltage, 2);     // Voltage with 2 decimal places
    Serial.print(",");
    Serial.println("");                   // Empty timestamp (Python will add it)
    
    // ===== ALTERNATIVE: KEEP BOTH FORMATS (for debugging) =====
    // If you want to see human-readable output in Serial Monitor too:
    // Serial.print("TDS: ");
    // Serial.print(tdsValue, 0);
    // Serial.println(" ppm");
  }
}

// Median filtering algorithm (unchanged from original)
int getMedianAverage(int *arr, int number)
{
  int temp;
  // Simple bubble sort
  for (int i = 0; i < number - 1; i++)
  {
    for (int j = i + 1; j < number; j++)
    {
      if (arr[i] > arr[j])
      {
        temp = arr[i];
        arr[i] = arr[j];
        arr[j] = temp;
      }
    }
  }
  
  // Return median
  if ((number & 1) > 0)
    temp = arr[number / 2];
  else
    temp = (arr[number / 2 - 1] + arr[number / 2]) / 2;
    
  return temp;
}

/*
 * TEMPERATURE ADJUSTMENT (Optional Enhancement)
 * If you have a temperature sensor (like DS18B20), you can update
 * the 'temperature' variable in the loop to get more accurate readings:
 * 
 * temperature = readTemperatureSensor(); // Your temp sensor function
 * 
 * This improves TDS accuracy as water conductivity changes with temperature.
 */

/*
 * CALIBRATION NOTES:
 * 1. For accurate readings, calibrate with known TDS solution
 * 2. If readings are consistently off, adjust the K factor:
 *    tdsValue = ecValue * 0.5 * 1000;  // K = 0.5 (default)
 *    Try K = 0.45 to 0.55 for your specific solution
 * 
 * 3. Test in known solutions:
 *    - Distilled water: ~0-10 ppm
 *    - Tap water: 50-300 ppm (varies by location)
 *    - Calibration solution: Check bottle label
 */