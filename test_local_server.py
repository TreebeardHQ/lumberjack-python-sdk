"""
Simple end-to-end test for the Lumberjack Local Development Server.

This script tests:
1. Starting the local server
2. Sending logs from multiple services
3. Viewing logs in real-time
"""
import time
import threading
from lumberjack_sdk import Lumberjack, Log

def test_service_a():
    """Simulate service A generating logs."""
    print("🔵 Service A: Starting...")
    
    # Initialize Lumberjack with local server enabled
    Lumberjack.init(
        project_name="test-service-a",
        local_server_enabled=True,
        debug_mode=True,
        log_to_stdout=False  # Don't duplicate to console
    )
    
    for i in range(5):
        Log.info(f"Service A processing request {i+1}", request_id=f"req-a-{i+1}", user_id=123)
        time.sleep(2)
        
        if i == 2:
            Log.warning("Service A detected slow response time", response_time_ms=1500)
        
        if i == 4:
            try:
                raise ValueError("Test error from Service A")
            except Exception as e:
                Log.error("Service A encountered an error", error=e)
    
    print("🔵 Service A: Completed")

def test_service_b():
    """Simulate service B generating logs."""
    print("🟢 Service B: Starting...")
    
    # Initialize Lumberjack with different service name
    Lumberjack.init(
        project_name="test-service-b", 
        local_server_enabled=True,
        debug_mode=True,
        log_to_stdout=False
    )
    
    time.sleep(1)  # Offset from service A
    
    for i in range(3):
        Log.info(f"Service B background task {i+1}", task_type="cleanup", items_processed=50+i*10)
        time.sleep(3)
        
        if i == 1:
            Log.debug("Service B cache hit", cache_key="user:123", hit_ratio=0.85)
    
    print("🟢 Service B: Completed")

def main():
    """Run the end-to-end test."""
    print("🌲 Lumberjack Local Server End-to-End Test")
    print("=" * 50)
    print()
    print("1. Start the local server in another terminal:")
    print("   lumberjack serve")
    print()
    print("2. Open http://localhost:8080 in your browser")
    print()
    print("3. Press Enter to start generating logs...")
    input()
    
    # Start both services in parallel
    thread_a = threading.Thread(target=test_service_a, daemon=True)
    thread_b = threading.Thread(target=test_service_b, daemon=True)
    
    thread_a.start()
    thread_b.start()
    
    # Wait for both to complete
    thread_a.join()
    thread_b.join()
    
    print()
    print("✅ Test completed!")
    print("Check the local server UI to see the logs from both services.")

if __name__ == "__main__":
    main()