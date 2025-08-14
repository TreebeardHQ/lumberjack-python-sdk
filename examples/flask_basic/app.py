import time

import utils
from flask import Flask, jsonify, request
from lumberjack_sdk import Log, Lumberjack, LumberjackFlask
import logging

app = Flask(__name__)

logger = logging.getLogger(__name__)

# Initialize Lumberjack
Lumberjack.init(
    api_key="",
    endpoint="https://your-logging-endpoint.com/logs"
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
    app.run(debug=True, threaded=app.config['THREADING_ENABLED'])
