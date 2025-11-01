"""
HTTP server for TDS readings from ESP32 devices
Receives JSON POST requests and stores to database
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import yaml
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.storage import append_reading, get_stats

app = FastAPI(title="TDS Monitor API", version="1.0")

def load_config():
    """Load configuration from config.yaml"""
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

@app.get("/")
async def root():
    """API status endpoint"""
    stats = get_stats()
    return {
        "status": "online",
        "service": "TDS Monitor API",
        "version": "1.0",
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status")
async def status():
    """Get database statistics"""
    return get_stats()

@app.post("/api/tds")
async def receive_tds(request: Request):
    """
    Receive TDS reading from ESP32
    
    Expected JSON body:
    {
        "device_id": "esp32-01",
        "device_ip": "192.168.1.42",  # optional, auto-detected
        "tds": 345.7,
        "voltage": 3.3,  # optional
        "timestamp": "2025-10-30T12:34:56.789Z"  # optional, auto-generated
    }
    """
    try:
        # Parse JSON payload
        payload = await request.json()
        
        # Extract data
        device_id = payload.get("device_id")
        tds = payload.get("tds")
        voltage = payload.get("voltage")
        timestamp = payload.get("timestamp")
        
        # Get device IP from request if not in payload
        device_ip = payload.get("device_ip") or request.client.host
        
        # Validate required fields
        if not device_id:
            raise HTTPException(status_code=400, detail="Missing device_id")
        if tds is None:
            raise HTTPException(status_code=400, detail="Missing tds value")
        
        # Convert TDS to float
        try:
            tds = float(tds)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tds value (must be numeric)")
        
        # Store reading
        append_reading(
            device_id=device_id,
            tds=tds,
            voltage=voltage,
            timestamp=timestamp,
            device_ip=device_ip
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Reading saved",
                "device_id": device_id,
                "tds": tds,
                "timestamp": timestamp or datetime.now().isoformat()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[HTTP] Error processing request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    print(f"[HTTP] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": str(exc)}
    )

def run_server(host="0.0.0.0", port=5000):
    """Start the HTTP server"""
    print("=" * 60)
    print("TDS Monitor - HTTP Ingestion Server")
    print("=" * 60)
    print(f"Server starting on http://{host}:{port}")
    print(f"POST endpoint: http://{host}:{port}/api/tds")
    print(f"Status page: http://{host}:{port}/")
    print("=" * 60)
    print()
    
    # Get local IP for convenience
    import socket
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"💡 Your laptop IP: {local_ip}")
        print(f"   Configure ESP32 to POST to: http://{local_ip}:{port}/api/tds")
        print()
    except:
        pass
    
    uvicorn.run(app, host=host, port=port, log_level="info")

def main():
    """Main entry point"""
    config = load_config()
    
    if not config['http']['enabled']:
        print("[HTTP] HTTP ingestion is disabled in config.yaml")
        sys.exit(0)
    
    host = config['http']['host']
    port = config['http']['port']
    
    run_server(host, port)

if __name__ == "__main__":
    main()