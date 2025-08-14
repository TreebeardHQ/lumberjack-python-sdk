from django.http import JsonResponse
from django.shortcuts import render
from lumberjack_sdk.log import Log
import logging
import time
import random

# Get Django logger to demonstrate Python logger integration
logger = logging.getLogger(__name__)


def home(request):
    """Home page view that demonstrates basic logging."""
    Log.info("User visited home page")
    return JsonResponse({
        "message": "Welcome to the Lumberjack Django Example",
        "status": "success"
    })


def products(request):
    """Products view that demonstrates logging with data."""
    Log.info("User requested products list")

    products_data = [
        {"id": 1, "name": "Laptop", "price": 999.99},
        {"id": 2, "name": "Mouse", "price": 29.99},
        {"id": 3, "name": "Keyboard", "price": 79.99},
    ]

    Log.info(f"Returning {len(products_data)} products")

    return JsonResponse({
        "products": products_data,
        "count": len(products_data)
    })


def slow_operation(request):
    """Slow operation to demonstrate timing and performance logging."""
    Log.info("Starting slow operation")

    # Simulate some work
    processing_time = random.uniform(0.5, 2.0)
    time.sleep(processing_time)

    Log.info(f"Slow operation completed in {processing_time:.2f} seconds")

    return JsonResponse({
        "message": "Operation completed",
        "processing_time": round(processing_time, 2)
    })


def error_example(request):
    """Example endpoint that demonstrates error logging."""
    Log.info("Error example endpoint called")
    logger.info("Django logger: Processing error example request")

    try:
        # Simulate an error condition
        if random.choice([True, False]):
            raise ValueError("Simulated error for demonstration")

        Log.info("No error occurred this time")
        logger.info("Django logger: Request completed successfully")
        return JsonResponse({"message": "Success - no error this time!"})

    except ValueError as e:
        Log.error(f"Caught error: {str(e)}")
        logger.error("Django logger: Error occurred", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


def user_profile(request, user_id):
    """User profile view that demonstrates logging with parameters."""
    Log.info(f"Fetching profile for user {user_id}")

    # Simulate user lookup
    if user_id <= 0:
        Log.warning(f"Invalid user ID requested: {user_id}")
        return JsonResponse({"error": "Invalid user ID"}, status=400)

    user_data = {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com"
    }

    Log.info(f"Successfully retrieved profile for user {user_id}")

    return JsonResponse({"user": user_data})


def logging_demo(request):
    """Demo endpoint that shows different types of logging."""
    Log.info("Starting logging demonstration")
    
    # Lumberjack Log API with structured data
    Log.info("Lumberjack structured log", 
             endpoint="/logging-demo",
             user_agent=request.META.get('HTTP_USER_AGENT', 'unknown'))
    
    # Django's built-in logger (forwarded to Lumberjack)  
    logger.info("Django logger message with trace context")
    logger.warning("Django warning message")
    
    # Print statements (if stdout capture is enabled)
    print("Print statement from Django view")
    print(f"Request method: {request.method}")
    
    return JsonResponse({
        "message": "Check your logs to see different logging approaches!",
        "lumberjack_log": "Structured logging with Lumberjack Log API",
        "django_logger": "Standard Python logging forwarded to Lumberjack", 
        "print_statements": "Print statements captured if stdout capture enabled"
    })
