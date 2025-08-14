import logging
import time
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from lumberjack_sdk import Log, Lumberjack, LumberjackFastAPI

# Initialize FastAPI app
app = FastAPI(title="Lumberjack FastAPI Example", version="1.0.0")

# Get Python logger for demonstration
logger = logging.getLogger(__name__)

# Initialize Lumberjack
Lumberjack.init(
    api_key="",  # Empty for fallback mode
    project_name="fastapi-basic-example",
    log_to_stdout=True,  # Enable for development
    capture_python_logger=True,  # Capture FastAPI's built-in logging
    capture_stdout=True,  # Capture print statements
    debug_mode=True
)

# Instrument FastAPI with Lumberjack
LumberjackFastAPI.instrument(app)


@app.get("/")
async def home() -> Dict[str, str]:
    """Home endpoint with basic logging."""
    Log.info("User visited home page")
    return {
        "message": "Welcome to the Lumberjack FastAPI Example",
        "status": "success"
    }


@app.get("/products")
async def list_products(category: str = None, min_price: float = None) -> Dict[str, Any]:
    """Products endpoint that demonstrates logging with parameters."""
    Log.info("Processing product list request", category=category, min_price=min_price)
    
    # Sample products data
    products = [
        {"id": 1, "name": "Laptop", "price": 999.99, "category": "electronics"},
        {"id": 2, "name": "Mouse", "price": 29.99, "category": "electronics"},
        {"id": 3, "name": "Keyboard", "price": 79.99, "category": "electronics"},
        {"id": 4, "name": "Coffee", "price": 12.99, "category": "food"},
    ]
    
    # Filter by category
    if category:
        products = [p for p in products if p["category"] == category]
    
    # Filter by minimum price
    if min_price:
        products = [p for p in products if p["price"] >= min_price]
    
    Log.info(f"Returning {len(products)} products")
    
    return {
        "products": products,
        "count": len(products),
        "filters": {"category": category, "min_price": min_price}
    }


@app.get("/products/{product_id}")
async def get_product(product_id: int) -> Dict[str, Any]:
    """Get single product by ID."""
    Log.info("Fetching product details", product_id=product_id)
    
    if product_id <= 0:
        Log.warning("Invalid product ID requested", product_id=product_id)
        raise HTTPException(status_code=400, detail="Invalid product ID")
    
    if product_id > 100:  # Simulate not found
        Log.warning("Product not found", product_id=product_id)
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Simulate product data
    product = {
        "id": product_id,
        "name": f"Product {product_id}",
        "price": 49.99 + (product_id * 10),
        "category": "sample"
    }
    
    Log.info("Product found successfully", product_id=product_id)
    
    return {"product": product}


@app.get("/slow")
async def slow_operation() -> Dict[str, Any]:
    """Slow operation to demonstrate timing and performance logging."""
    Log.info("Starting slow operation")
    
    # Simulate some async work
    import asyncio
    processing_time = 1.5
    await asyncio.sleep(processing_time)
    
    Log.info(f"Slow operation completed in {processing_time} seconds")
    
    return {
        "message": "Operation completed",
        "processing_time": processing_time
    }


@app.get("/error")
async def error_example() -> Dict[str, Any]:
    """Example endpoint that demonstrates error logging."""
    Log.info("Error example endpoint called")
    logger.info("FastAPI logger: Processing error example request")
    
    try:
        # Simulate an error condition
        import random
        if random.choice([True, False]):
            raise ValueError("Simulated error for demonstration")
        
        Log.info("No error occurred this time")
        logger.info("FastAPI logger: Request completed successfully")
        return {"message": "Success - no error this time!"}
    
    except ValueError as e:
        Log.error("Caught error in FastAPI endpoint", exception=e)
        logger.error("FastAPI logger: Error occurred", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logging-demo")
async def logging_demo(request: Request) -> Dict[str, Any]:
    """Demo endpoint that shows different types of logging."""
    Log.info("Starting comprehensive logging demonstration")
    
    # Lumberjack Log API with structured data
    Log.info("FastAPI structured log", 
             endpoint="/logging-demo",
             method=request.method,
             user_agent=request.headers.get("user-agent", "unknown"))
    
    # FastAPI's built-in logger (forwarded to Lumberjack)
    logger.info("FastAPI logger message with trace context")
    logger.warning("FastAPI warning message")
    
    # Print statements (if stdout capture is enabled)
    print("Print statement from FastAPI endpoint")
    print(f"Request method: {request.method}")
    print(f"Request URL: {request.url}")
    
    return {
        "message": "Check your logs to see different logging approaches!",
        "lumberjack_log": "Structured logging with Lumberjack Log API",
        "fastapi_logger": "Standard Python logging forwarded to Lumberjack",
        "print_statements": "Print statements captured if stdout capture enabled"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with logging."""
    Log.error("Unhandled exception in FastAPI", 
              path=str(request.url.path),
              method=request.method,
              exception=exc)
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    
    print("Starting FastAPI server...")
    print("Visit http://localhost:8002/docs for interactive API documentation")
    
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")