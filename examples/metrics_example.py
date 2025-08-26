#!/usr/bin/env python3
"""
Example demonstrating Lumberjack metrics functionality.
"""

import time
import random
from lumberjack_sdk import (
    Lumberjack,
    Log,
    create_counter,
    create_histogram,
    create_up_down_counter,
    create_red_metrics,
    get_meter,
)


def simulate_service_operations():
    """Simulate a service performing operations with metrics."""
    
    # Create various metric types
    request_counter = create_counter(
        name="app_requests_total",
        unit="1",
        description="Total number of requests"
    )
    
    response_time_histogram = create_histogram(
        name="app_response_time_seconds",
        unit="s",
        description="Response time in seconds"
    )
    
    active_connections = create_up_down_counter(
        name="app_active_connections",
        unit="1",
        description="Number of active connections"
    )
    
    # Simulate some operations
    Log.info("Starting metrics example")
    
    for i in range(10):
        # Record a request
        request_counter.add(1, attributes={"endpoint": "/api/data", "method": "GET"})
        
        # Simulate varying response times
        response_time = random.uniform(0.1, 2.0)
        time.sleep(response_time)
        response_time_histogram.record(response_time, attributes={"endpoint": "/api/data"})
        
        # Simulate connection changes
        if i % 3 == 0:
            active_connections.add(1)  # New connection
            Log.info(f"New connection established (iteration {i})")
        if i % 4 == 0 and i > 0:
            active_connections.add(-1)  # Connection closed
            Log.info(f"Connection closed (iteration {i})")
        
        Log.info(f"Processed request {i+1} in {response_time:.2f} seconds")
    
    Log.info("Basic metrics example completed")


def demonstrate_red_metrics():
    """Demonstrate the RED (Rate, Errors, Duration) metrics helper."""
    
    # Create RED metrics for our service
    red_metrics = create_red_metrics("user_service")
    
    Log.info("Starting RED metrics demonstration")
    
    # Simulate successful operations
    for i in range(5):
        with red_metrics.measure(operation="get_user", attributes={"user_id": f"user_{i}"}):
            # Simulate some work
            time.sleep(random.uniform(0.05, 0.3))
            Log.info(f"Successfully fetched user_{i}")
    
    # Simulate an operation with an error
    try:
        with red_metrics.measure(operation="get_user", attributes={"user_id": "invalid"}):
            # Simulate some work
            time.sleep(0.1)
            # Simulate an error
            raise ValueError("User not found")
    except ValueError as e:
        Log.error(f"Error in operation: {e}")
    
    # Manually record metrics (alternative to context manager)
    red_metrics.record_request(attributes={"operation": "create_user"})
    start_time = time.perf_counter()
    
    # Simulate work
    time.sleep(0.2)
    
    # Record the duration
    duration = time.perf_counter() - start_time
    red_metrics.record_duration(duration, attributes={"operation": "create_user"})
    
    Log.info("RED metrics demonstration completed")


def demonstrate_observable_metrics():
    """Demonstrate observable metrics (async metrics)."""
    from opentelemetry.metrics import CallbackOptions, Observation
    
    # Get the meter directly
    meter = get_meter()
    
    # Create a callback function for CPU usage (simulated)
    def get_cpu_usage(options: CallbackOptions):
        # In a real app, you'd get actual CPU usage here
        cpu_percent = random.uniform(10, 90)
        return [Observation(value=cpu_percent, attributes={"host": "localhost"})]
    
    # Create a callback function for memory usage (simulated)
    def get_memory_usage(options: CallbackOptions):
        # In a real app, you'd get actual memory usage here
        memory_mb = random.uniform(100, 500)
        return [Observation(value=memory_mb, attributes={"host": "localhost"})]
    
    # Create observable gauges
    cpu_gauge = meter.create_observable_gauge(
        name="system_cpu_usage_percent",
        callbacks=[get_cpu_usage],
        unit="%",
        description="Current CPU usage percentage"
    )
    
    memory_gauge = meter.create_observable_gauge(
        name="system_memory_usage_mb",
        callbacks=[get_memory_usage],
        unit="MB",
        description="Current memory usage in megabytes"
    )
    
    Log.info("Observable metrics created - they will be collected periodically")
    
    # Let the observable metrics be collected a few times
    for i in range(3):
        Log.info(f"Waiting for observable metrics collection... ({i+1}/3)")
        time.sleep(5)


def main():
    """Main function to run all examples."""
    
    # Initialize Lumberjack with metrics support
    # Note: You need to provide a metrics_endpoint for metrics to be exported
    Lumberjack.init(
        project_name="metrics_example",
        # api_key="your_api_key",  # Uncomment and set your API key
        # metrics_endpoint="https://your-otel-collector/v1/metrics",  # Set your metrics endpoint
        debug_mode=True,
        log_to_stdout=True
    )
    
    try:
        Log.info("=== Lumberjack Metrics Example ===")
        
        # Run different metric demonstrations
        Log.info("\n--- Basic Metrics ---")
        simulate_service_operations()
        
        Log.info("\n--- RED Metrics Helper ---")
        demonstrate_red_metrics()
        
        Log.info("\n--- Observable Metrics ---")
        demonstrate_observable_metrics()
        
        Log.info("\n=== All examples completed successfully ===")
        
    except Exception as e:
        Log.error(f"Error in metrics example: {e}", exc_info=True)
    
    finally:
        # Shutdown to ensure all metrics are flushed
        Log.info("Shutting down Lumberjack...")
        Lumberjack.get_instance().shutdown()


if __name__ == "__main__":
    main()