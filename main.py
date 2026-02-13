# main.py
"""
SentinelX – Simplified Risk‑Based Proctoring System
Entry point for local demonstration.

Launches three concurrent processes:
1. FastAPI backend server (on port 8000)
2. Streamlit dashboard (on port 8501)
3. Simulated client that generates interaction metadata and sends risk scores

All components run in separate processes. Use Ctrl+C to terminate.
"""

import os
import sys

# Add project root to Python path so that 'client', 'server', etc. are importable
# This MUST be at the very top before any other imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # This is CORRECT: SentinalX folder
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print(f"[Main] Project root: {PROJECT_ROOT}")

import multiprocessing
import time
import uuid
import requests
from datetime import datetime

# ----------------------------------------------------------------------
# 1. Database Initialization
# ----------------------------------------------------------------------
def init_database():
    """Create database tables before starting the server."""
    from server.database import init_db
    print("[Main] Initializing database...")
    init_db()
    print("[Main] Database ready.")

# ----------------------------------------------------------------------
# 2. FastAPI Server Process
# ----------------------------------------------------------------------
def run_server():
    """Start Uvicorn server for the FastAPI application."""
    # Add path fix for child process
    import os
    import sys
    
    # FIXED: Get the actual project root - this is SentinalX folder
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # This is SentinalX/main.py location
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    
    import uvicorn
    from server.api import app
    print("[Server] Starting on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

# ----------------------------------------------------------------------
# 3. Streamlit Dashboard Process - FIXED PATH
# ----------------------------------------------------------------------
def run_dashboard():
    """Launch Streamlit dashboard using its CLI."""
    # Add path fix for child process
    import os
    import sys
    
    # FIXED: Get the actual project root
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # This is SentinalX folder
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    
    import subprocess
    
    # FIXED: Correct path to dashboard/app.py
    dashboard_path = os.path.join(PROJECT_ROOT, "dashboard", "app.py")
    
    # Verify the file exists before trying to run it
    if not os.path.exists(dashboard_path):
        print(f"[Dashboard] ERROR: File not found at {dashboard_path}")
        print(f"[Dashboard] Current directory: {os.getcwd()}")
        print(f"[Dashboard] PROJECT_ROOT: {PROJECT_ROOT}")
        return
        
    print(f"[Dashboard] Starting on http://localhost:8501")
    print(f"[Dashboard] Path: {dashboard_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])

# ----------------------------------------------------------------------
# 4. Simulated Client Process - FIXED PATH
# ----------------------------------------------------------------------
def run_simulation():
    """
    Simulate a user session:
    - Capture mock interaction events
    - Extract features every 5 seconds
    - Build baseline during first 3 minutes
    - Detect activity shifts
    - Compute risk score
    - POST to backend every 10 seconds (or after each risk update)
    """
    # ============ CRITICAL: Add path fix at the VERY TOP of the function ============
    import os
    import sys
    
    # FIXED: Get the actual project root - DO NOT go up a level!
    # __file__ in this child process is still main.py in SentinalX folder
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # This is CORRECT: SentinalX folder
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    
    # Debug: Print the path we're adding
    print(f"[Client] Added to Python path: {PROJECT_ROOT}")
    print(f"[Client] Current working directory: {os.getcwd()}")
    # ================================================================================
    
    import time
    import uuid
    import requests
    
    # Now these imports should work
    try:
        from client.interaction_listener import MockInteractionListener
        from client.feature_extractor import FeatureExtractor
        from client.baseline_builder import BaselineBuilder
        from client.activity_shift_detector import ActivityShiftDetector
        from client.risk_engine import RiskEngine
        from shared.models import RiskData, AnomalyScores
        print("[Client] All modules imported successfully")
    except ImportError as e:
        print(f"[Client] Import error: {e}")
        print(f"[Client] sys.path: {sys.path}")
        print(f"[Client] Looking for client module at: {os.path.join(PROJECT_ROOT, 'client')}")
        print(f"[Client] Does client folder exist? {os.path.exists(os.path.join(PROJECT_ROOT, 'client'))}")
        print(f"[Client] Files in client folder: {os.listdir(os.path.join(PROJECT_ROOT, 'client')) if os.path.exists(os.path.join(PROJECT_ROOT, 'client')) else 'Folder not found'}")
        raise

    print("[Client] Starting simulated interaction...")
    
    # Generate a unique session ID
    session_id = str(uuid.uuid4())
    print(f"[Client] Session ID: {session_id}")

    # Initialize components
    listener = MockInteractionListener(
        mean_event_interval=0.3,
        idle_probability=0.1,
        focus_loss_probability=0.03
    )
    extractor = FeatureExtractor(window_duration=30.0)
    baseline_builder = BaselineBuilder(calibration_duration=180.0)  # 3 minutes
    detector = ActivityShiftDetector()
    risk_engine = RiskEngine(smoothing_window=5)

    # Start the event listener
    listener.start()
    print("[Client] Interaction listener started.")

    # Wait for server to be ready
    time.sleep(2)

    # Main loop: collect events, compute features, update baseline, detect anomalies, compute risk
    last_risk_send_time = 0
    risk_send_interval = 10.0  # seconds

    try:
        while True:
            # 1. Get events from listener
            events = listener.get_events(timeout=1.0)
            for event in events:
                extractor.add_event(event)

            # 2. Compute features from current window
            features = extractor.compute_features()

            # 3. Update baseline builder (calibration phase)
            baseline_builder.update(features, features.window_end)

            # 4. Once calibrated, set baseline in detector
            if baseline_builder.is_calibrated and detector.baseline is None:
                detector.baseline = baseline_builder.baseline
                print(f"[Client] Baseline calibrated: {detector.baseline}")

            # 5. If baseline is ready, detect anomalies and compute risk
            if detector.baseline is not None:
                anomaly_scores = detector.compute_scores(features)
                risk_score = risk_engine.compute_risk(anomaly_scores)

                # Send risk data periodically
                now = time.time()
                if now - last_risk_send_time >= risk_send_interval:
                    # Prepare payload
                    payload = RiskData(
                        timestamp=now,
                        risk_score=risk_score,
                        anomaly_scores=AnomalyScores(
                            idle_burst=anomaly_scores.idle_burst,
                            focus_instability=anomaly_scores.focus_instability,
                            behavioral_drift=anomaly_scores.behavioral_drift,
                            overall=anomaly_scores.overall
                        ),
                        session_id=session_id,
                        source="simulation"
                    )
                    # POST to backend
                    try:
                        # Handle Pydantic v1 vs v2 serialization
                        if hasattr(payload, "model_dump"):
                            payload_dict = payload.model_dump()
                        else:
                            payload_dict = payload.dict()
                            
                        resp = requests.post(
                            "http://localhost:8000/risk",
                            json=payload_dict,
                            timeout=2.0
                        )
                        if resp.status_code == 200:
                            print(f"[Client] Risk sent: {risk_score:.1f}")
                            last_risk_send_time = now
                        else:
                            print(f"[Client] Failed to send risk: {resp.status_code}")
                    except Exception as e:
                        print(f"[Client] Error sending risk: {e}")

            # Sleep a bit to avoid busy loop
            time.sleep(2.0)

    except KeyboardInterrupt:
        print("[Client] Stopping...")
    finally:
        listener.stop()
        print("[Client] Shutdown complete.")

# ----------------------------------------------------------------------
# 5. Main Orchestrator
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Set multiprocessing start method
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass  # Already set

    # Initialize database before starting server
    init_database()

    # Create processes
    server_process = multiprocessing.Process(target=run_server, name="Server")
    dashboard_process = multiprocessing.Process(target=run_dashboard, name="Dashboard")
    client_process = multiprocessing.Process(target=run_simulation, name="Client")

    # Start all processes
    print("[Main] Starting SentinelX components...")
    server_process.start()
    time.sleep(2)  # Give server time to start
    dashboard_process.start()
    client_process.start()

    print("[Main] All components launched. Press Ctrl+C to stop.")

    try:
        # Wait for all processes to complete (they run indefinitely)
        server_process.join()
        dashboard_process.join()
        client_process.join()
    except KeyboardInterrupt:
        print("\n[Main] Termination signal received. Shutting down...")
        
        # Terminate all processes
        for process in [server_process, dashboard_process, client_process]:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2.0)
                
        print("[Main] Shutdown complete.")
        sys.exit(0)