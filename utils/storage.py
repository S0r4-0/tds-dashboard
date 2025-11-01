"""
Storage utility for TDS readings using SQLite
Handles concurrent writes from multiple ingestion sources
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import threading

# Thread-safe database access
db_lock = threading.Lock()
DB_PATH = "data/readings.db"

def init_database():
    """Initialize the database with required tables"""
    Path("data").mkdir(exist_ok=True)
    
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                device_ip TEXT,
                tds REAL NOT NULL,
                voltage REAL,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON readings(timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_id 
            ON readings(device_id, timestamp DESC)
        """)
        
        conn.commit()
        conn.close()

def append_reading(device_id, tds, voltage=None, timestamp=None, device_ip=None):
    """
    Append a new TDS reading to the database
    
    Args:
        device_id: Unique identifier for the device
        tds: TDS value in ppm
        voltage: Optional sensor voltage
        timestamp: ISO format timestamp (auto-generated if None)
        device_ip: IP address of the device (for ESP32)
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    
    created_at = datetime.now().isoformat()
    
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO readings (device_id, device_ip, tds, voltage, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (device_id, device_ip, tds, voltage, timestamp, created_at))
        
        conn.commit()
        conn.close()
    
    print(f"[STORAGE] Saved: {device_id} | TDS: {tds} ppm | IP: {device_ip}")

def last_n_readings(minutes=None, limit=1000, device_id=None):
    """
    Retrieve recent readings as a pandas DataFrame
    
    Args:
        minutes: Only get readings from last N minutes (None = all)
        limit: Maximum number of readings to return
        device_id: Filter by specific device (None = all devices)
    
    Returns:
        pandas DataFrame with columns: id, device_id, device_ip, tds, voltage, timestamp
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        
        query = "SELECT id, device_id, device_ip, tds, voltage, timestamp, created_at FROM readings"
        conditions = []
        params = []
        
        if minutes:
            cutoff_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()
            conditions.append("timestamp >= ?")
            params.append(cutoff_time)
        
        if device_id:
            conditions.append("device_id = ?")
            params.append(device_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
    
    if not df.empty:
        # Convert timestamp to datetime for better plotting
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        # Sort ascending for charts
        df = df.sort_values('timestamp')
    
    return df

def get_latest_by_device():
    """
    Get the latest reading for each device
    
    Returns:
        pandas DataFrame with one row per device (latest reading)
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        
        query = """
            SELECT device_id, device_ip, tds, voltage, timestamp, created_at,
                   MAX(timestamp) as last_seen
            FROM readings
            GROUP BY device_id
            ORDER BY last_seen DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
    
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['last_seen'] = pd.to_datetime(df['last_seen'])
    
    return df

def get_device_list():
    """Get list of all unique devices that have sent data"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT device_id, MAX(timestamp) as last_seen
            FROM readings
            GROUP BY device_id
            ORDER BY last_seen DESC
        """)
        
        devices = cursor.fetchall()
        conn.close()
    
    return devices

def export_csv(path="data/tds_export.csv", device_id=None, days=None):
    """
    Export readings to CSV file
    
    Args:
        path: Output file path
        device_id: Export only specific device (None = all)
        days: Only export last N days (None = all)
    """
    minutes = days * 24 * 60 if days else None
    df = last_n_readings(minutes=minutes, limit=100000, device_id=device_id)
    
    if not df.empty:
        df.to_csv(path, index=False)
        print(f"[STORAGE] Exported {len(df)} readings to {path}")
        return path
    else:
        print("[STORAGE] No data to export")
        return None

def clear_old_readings(days=30):
    """Delete readings older than N days"""
    cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()
    
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff_time,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
    
    print(f"[STORAGE] Deleted {deleted} old readings")
    return deleted

def get_stats():
    """Get database statistics"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM readings")
        total_readings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT device_id) FROM readings")
        total_devices = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM readings")
        date_range = cursor.fetchone()
        
        conn.close()
    
    return {
        "total_readings": total_readings,
        "total_devices": total_devices,
        "earliest": date_range[0],
        "latest": date_range[1]
    }

# Initialize database on import
init_database()