"""
Test script to demonstrate flask_basic with local server.

This script makes requests to the Flask app while the local server is running,
showing how logs appear in real-time in the web UI.
"""
import time
import requests
import sys

def test_flask_with_local_server():
    """Test the Flask app with local server integration."""
    
    flask_url = "http://localhost:5000"
    local_server_url = "http://localhost:8080"
    
    print("🌲 Flask Basic + Local Server Test")
    print("=" * 40)
    print()
    
    # Check if services are running
    try:
        # Check local server
        response = requests.get(f"{local_server_url}/api/stats", timeout=2)
        if response.status_code == 200:
            print("✅ Local server is running")
        else:
            print("❌ Local server responded with error")
            return
    except requests.exceptions.RequestException:
        print("❌ Local server is not running!")
        print("   Start it with: lumberjack serve")
        return
    
    try:
        # Check Flask app
        response = requests.get(f"{flask_url}/products", timeout=2)
        if response.status_code == 200:
            print("✅ Flask app is running")
        else:
            print("❌ Flask app responded with error")
            return
    except requests.exceptions.RequestException:
        print("❌ Flask app is not running!")
        print("   Start it with: cd examples/flask_basic && python app.py")
        return
    
    print("✅ Both services are running!")
    print()
    print(f"🌐 Local server UI: {local_server_url}")
    print(f"🐍 Flask app: {flask_url}")
    print()
    print("🎬 Starting test requests...")
    print("   Watch the logs appear in real-time at the local server UI!")
    print()
    
    # Test scenarios
    scenarios = [
        {
            "name": "📦 List all products",
            "url": "/products",
            "description": "Should show product listing logs"
        },
        {
            "name": "🔍 Search electronics",
            "url": "/products?category=electronics&min_price=50",
            "description": "Should show search with parameters"
        },
        {
            "name": "🎯 Get specific product",
            "url": "/products/1",
            "description": "Should show product details logs"
        },
        {
            "name": "❓ Get non-existent product",
            "url": "/products/999",
            "description": "Should show 'not found' warning"
        },
        {
            "name": "💥 Trigger error",
            "url": "/error",
            "description": "Should show exception with full stacktrace"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. {scenario['name']}")
        print(f"   {scenario['description']}")
        
        try:
            response = requests.get(f"{flask_url}{scenario['url']}", timeout=5)
            status_icon = "✅" if response.status_code < 400 else "⚠️"
            print(f"   {status_icon} Response: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {e}")
        
        print()
        time.sleep(2)  # Give time to see logs appear
    
    print("🎉 Test completed!")
    print()
    print("🔍 What to look for in the local server UI:")
    print("   • Service name: 'flask-basic-example'")
    print("   • Different log levels: INFO, WARNING, ERROR")
    print("   • Request parameters in log attributes")
    print("   • Red-colored stacktrace for the error endpoint")
    print("   • Trace IDs linking related logs")
    print()
    print("💡 Try the search features:")
    print("   • Search for 'product' to find product-related logs")
    print("   • Filter by 'ERROR' level to see only the exception")
    print("   • Use column visibility to hide/show details")

if __name__ == "__main__":
    test_flask_with_local_server()