import time

import utils
from flask import Flask, jsonify, request
from lumberjack_sdk import Log, Lumberjack, LumberjackFlask
import logging

app = Flask(__name__)

logger = logging.getLogger(__name__)

# Initialize Lumberjack (without local server for now to test basic functionality)
Lumberjack.init(
    project_name="flask-basic-example",
    api_key="",  # Empty for fallback mode
    local_server_enabled=True,  # Re-enable local server to test the fix
    log_to_stdout=True,  # Also show in terminal
    capture_python_logger=True,  # Capture Flask's built-in logging
    capture_stdout=True,  # Capture print statements
    debug_mode=True  # Enable debug mode to see LogRecord debugging
)

LumberjackFlask.instrument(app)

# Configure threading support
app.config['THREADING_ENABLED'] = True  # Enable/disable threading per request
if app.config['THREADING_ENABLED']:
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.protocol_version = "HTTP/1.1"  # Enable keep-alive connections


@app.route("/products")
def list_products():
    # Start a trace for this request

    try:
        category = request.args.get("category")
        min_price = request.args.get("min_price")

        Log.info("Processing product list request",
                 category=category,
                 min_price=min_price)

        products = utils.get_products(
            category=category,
            min_price=float(min_price) if min_price else None
        )

        return jsonify({"products": products})
    except ValueError as e:
        Log.error("Invalid request parameters", error=str(e))
        return jsonify({"error": str(e)}), 400


@app.route("/products/<product_id>")
def get_product(product_id):

    try:
        Log.info("Fetching product details", product_id=product_id)

        product = utils.get_product_by_id(product_id)
        if product:
            Log.info("Product found", product_id=product_id)
            return jsonify(product)

        Log.warning("Product not found", product_id=product_id)
        return jsonify({"error": "Product not found"}), 404
    except ValueError as e:
        Log.error("Error fetching product", error=str(e))
        return jsonify({"error": str(e)}), 400


@app.route("/long-operation")
def long_operation():

    try:
        Log.info("Starting long operation")
        # Simulate a long-running operation
        time.sleep(30)

        Log.info("Long operation completed")
        return jsonify({"status": "completed", "duration": "30 seconds"})
    except Exception as e:
        Log.error("Error in long operation", error=str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health_check():
    start_time = time.time()
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    try:
        Log.info("Health check initiated", 
                client_ip=client_ip, 
                user_agent=user_agent,
                endpoint="/health")
        
        # Simulate various log levels with more detailed information
        Log.debug("Starting comprehensive health validation", 
                 checks=["database", "external_service", "memory", "disk_space"])
        
        # Check database connectivity (simulated)
        db_check_start = time.time()
        db_status = "healthy"
        db_response_time = round((time.time() - db_check_start) * 1000, 2)
        Log.info("Database connectivity verified", 
                status=db_status, 
                response_time_ms=db_response_time,
                connection_pool="active")
        
        # Check external service (simulated)
        service_check_start = time.time()
        external_service_status = "operational"
        service_response_time = round((time.time() - service_check_start) * 1000, 2)
        Log.info("External service availability confirmed", 
                status=external_service_status,
                response_time_ms=service_response_time,
                service_endpoint="api.external.com")
        
        # Additional system checks
        memory_usage = "normal"  # Simulated
        disk_space = "sufficient"  # Simulated
        Log.debug("System resource check completed",
                 memory_usage=memory_usage,
                 disk_space=disk_space,
                 cpu_load="low")
        
        total_duration = round((time.time() - start_time) * 1000, 2)
        
        if db_status == "healthy" and external_service_status == "operational":
            Log.info("Health check completed successfully", 
                    overall_status="healthy",
                    total_duration_ms=total_duration,
                    checks_passed=4,
                    checks_failed=0)
            return jsonify({
                "status": "healthy",
                "timestamp": time.time(),
                "duration_ms": total_duration,
                "services": {
                    "database": {"status": db_status, "response_time_ms": db_response_time},
                    "external_service": {"status": external_service_status, "response_time_ms": service_response_time},
                    "memory": memory_usage,
                    "disk": disk_space
                }
            })
        else:
            Log.warning("Health check detected system issues", 
                       overall_status="degraded",
                       db_status=db_status, 
                       external_service_status=external_service_status,
                       total_duration_ms=total_duration,
                       requires_attention=True)
            return jsonify({
                "status": "degraded",
                "timestamp": time.time(),
                "duration_ms": total_duration,
                "services": {
                    "database": {"status": db_status, "response_time_ms": db_response_time},
                    "external_service": {"status": external_service_status, "response_time_ms": service_response_time},
                    "memory": memory_usage,
                    "disk": disk_space
                }
            }), 503
            
    except Exception as e:
        error_duration = round((time.time() - start_time) * 1000, 2)
        Log.error("Health check encountered critical failure", 
                 error=str(e),
                 error_type=type(e).__name__,
                 duration_ms=error_duration,
                 client_ip=client_ip,
                 severity="critical")
        return jsonify({
            "status": "error", 
            "error": str(e),
            "timestamp": time.time(),
            "duration_ms": error_duration
        }), 500


@app.route("/error")
def error():

    try:
        Log.info("hitting a bug")
        print("here we go...")
        logger.warning("WARNING..")
        # Simulate a long-running operation
        1/0

        Log.info("Didn't hit the bug!")
        return jsonify({"status": "completed", "duration": "30 seconds"})
    except Exception as e:
        logger.error("unknown error", exc_info=e)
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    # Configure the development server to use threading
    app.run(debug=True, threaded=app.config['THREADING_ENABLED'], port=5000)
