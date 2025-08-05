"""
Example Flask application using Lumberjack SDK with OpenTelemetry integration.
"""
import time
from flask import Flask, jsonify
from lumberjack_sdk import Log, Lumberjack
from lumberjack_sdk.lumberjack_flask import LumberjackFlask
from lumberjack_sdk.span import span_context, SpanKind

app = Flask(__name__)

# Initialize Lumberjack with OpenTelemetry
Lumberjack.init(
    project_name="flask-otel-example",
    api_key="test-api-key",
    endpoint="https://api.trylumberjack.com/logs/batch",
    debug_mode=True,
    log_to_stdout=True
)

# Instrument Flask app with OpenTelemetry
LumberjackFlask.instrument(app)

@app.route("/")
def hello():
    Log.info("Hello world endpoint called")
    return jsonify({"message": "Hello from Lumberjack + OpenTelemetry!"})

@app.route("/manual-span")
def manual_span():
    """Example using manual span creation."""
    with span_context("manual_operation", SpanKind.INTERNAL) as span:
        span.set_attribute("operation.type", "manual")
        span.set_attribute("user.id", "123")
        
        Log.info("Inside manual span", operation="custom_work")
        
        # Simulate some work
        time.sleep(0.1)
        
        span.add_event("work_completed", {"duration": "0.1s"})
    
    return jsonify({"status": "Manual span completed"})

@app.route("/error-test")
def error_test():
    """Test error handling and exception recording."""
    try:
        Log.info("About to cause an error")
        raise ValueError("This is a test error")
    except Exception as e:
        Log.error("Caught an error", error=str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/nested-spans")
def nested_spans():
    """Example with nested spans."""
    with span_context("outer_operation", SpanKind.INTERNAL) as outer_span:
        outer_span.set_attribute("level", "outer")
        Log.info("Starting outer operation")
        
        with span_context("inner_operation", SpanKind.INTERNAL) as inner_span:
            inner_span.set_attribute("level", "inner")
            Log.info("Inside inner operation")
            time.sleep(0.05)
        
        Log.info("Outer operation completed")
    
    return jsonify({"status": "Nested spans completed"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)