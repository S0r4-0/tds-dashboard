"""
Serial ingestion module for TDS readings from Arduino
Reads CSV lines from serial port and stores to database
"""
import serial
import time
import yaml
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.storage import append_reading

def load_config():
    """Load configuration from config.yaml"""
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def parse_serial_line(line):
    """
    Parse CSV line from Arduino
    Expected format: device_id,tds,voltage,timestamp
    Example: arduino-01,345.7,5.0,2025-10-30T12:34:56
    
    Returns tuple: (device_id, tds, voltage, timestamp) or None if invalid
    """
    try:
        parts = line.split(",")
        if len(parts) < 2:
            return None
        
        device_id = parts[0].strip()
        tds = float(parts[1].strip())
        voltage = float(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else None
        timestamp = parts[3].strip() if len(parts) > 3 and parts[3].strip() else None
        
        return device_id, tds, voltage, timestamp
    except (ValueError, IndexError) as e:
        print(f"[SERIAL] Parse error: {e} | Line: {line}")
        return None

def read_serial_loop(port, baudrate, timeout=1):
    """
    Main loop to read serial port and save readings
    
    Args:
        port: Serial port (e.g., COM3, /dev/ttyUSB0)
        baudrate: Baud rate (typically 115200)
        timeout: Serial read timeout in seconds
    """
    print(f"[SERIAL] Connecting to {port} at {baudrate} baud...")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Wait for Arduino reset
        print(f"[SERIAL] Connected! Reading data...")
        
        while True:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if not line:
                        continue
                    
                    print(f"[SERIAL] Raw: {line}")
                    
                    # Parse and store
                    parsed = parse_serial_line(line)
                    if parsed:
                        device_id, tds, voltage, timestamp = parsed
                        append_reading(
                            device_id=device_id,
                            tds=tds,
                            voltage=voltage,
                            timestamp=timestamp,
                            device_ip="SERIAL"  # Mark as serial connection
                        )
                    else:
                        print(f"[SERIAL] Skipping invalid line: {line}")
                
                time.sleep(0.1)  # Small delay to prevent CPU spinning
                
            except KeyboardInterrupt:
                print("\n[SERIAL] Stopping...")
                break
            except Exception as e:
                print(f"[SERIAL] Error reading line: {e}")
                continue
    
    except serial.SerialException as e:
        print(f"[SERIAL] Failed to connect: {e}")
        print(f"[SERIAL] Make sure:")
        print(f"  1. Arduino is connected to {port}")
        print(f"  2. No other program is using the port")
        print(f"  3. You have permissions (Linux: sudo usermod -a -G dialout $USER)")
        sys.exit(1)
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("[SERIAL] Port closed")

def main():
    """Main entry point"""
    config = load_config()
    
    if not config['serial']['enabled']:
        print("[SERIAL] Serial ingestion is disabled in config.yaml")
        sys.exit(0)
    
    port = config['serial']['port']
    baudrate = config['serial']['baudrate']
    timeout = config['serial']['timeout']
    
    print("=" * 60)
    print("TDS Monitor - Serial Ingestion")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Baudrate: {baudrate}")
    print(f"Expected format: device_id,tds,voltage,timestamp")
    print("=" * 60)
    print()
    
    read_serial_loop(port, baudrate, timeout)

if __name__ == "__main__":
    main()