# 🌲 Running Flask Basic with Lumberjack Local Server

Follow these steps to see the flask_basic example working with the new local development server.

## Step 1: Install Dependencies

```bash
# Install the SDK with local server support
pip install -e ".[local-server,flask]"
```

## Step 2: Start the Local Server

In **Terminal 1**, start the Lumberjack local server:

```bash
# From the project root
lumberjack serve

# Or with custom options:
# lumberjack serve --port 8080 --db-path ./flask_logs.db
```

This will:
- ✅ Start the log collector on port 4317
- ✅ Start the web UI on http://localhost:8080
- ✅ Auto-open your browser to the log viewer

## Step 3: Run Flask Basic

In **Terminal 2**, start the Flask application:

```bash
# Navigate to flask_basic example
cd examples/flask_basic

# Run the Flask app
python app.py
```

The Flask app will start on http://localhost:5000 and automatically connect to the local server.

## Step 4: Generate Some Logs

Open a **third terminal** or use your browser to make requests:

```bash
# Test different endpoints to generate logs
curl http://localhost:5000/products
curl http://localhost:5000/products/1
curl "http://localhost:5000/products?category=electronics&min_price=50"
curl http://localhost:5000/error  # This will generate an error log
```

Or visit these URLs in your browser:
- http://localhost:5000/products
- http://localhost:5000/products/1  
- http://localhost:5000/error

## Step 5: Watch the Logs!

Go back to your browser at http://localhost:8080 and you'll see:

📊 **Real-time log viewer** showing:
- 🔵 **Service**: "flask-basic-example" 
- 📝 **Log messages** from your Flask app
- 🕐 **Timestamps** for each request
- 🎯 **Log levels** (INFO, WARNING, ERROR)
- 🏷️ **Attributes** like request details, product IDs, etc.
- 🔍 **Trace context** linking related logs

### What You'll See:

1. **Flask HTTP requests** - Automatic instrumentation via LumberjackFlask
2. **Custom log messages** - From Log.info(), Log.error(), etc. calls
3. **Python logger output** - Flask's built-in logging forwarded to Lumberjack
4. **Print statements** - The `print("here we go...")` captured as logs
5. **Error logs** - Exception details with full stacktraces

## Step 6: Try the Search Features

In the log viewer UI:
- 🔍 **Search**: Type "product" to find product-related logs
- 🏷️ **Filter by level**: Select "ERROR" to see only errors  
- 👁️ **Column visibility**: Hide/show different columns
- ⏸️ **Pause tailing**: Scroll up to pause auto-scrolling

## Step 7: Claude Code Integration (Optional)

If you want to search logs from Claude Code:

```bash
# Setup MCP integration
lumberjack claude init

# Restart Claude Code
# Then you can ask Claude things like:
# "Search for error logs from flask-basic-example"
# "What products were requested in the last 5 minutes?"
# "Show me recent warning logs"
```

## Example Log Output

You should see logs like this in the viewer:

```
[13:45:23.123] INFO  flask-basic-example: Processing product list request
  category=electronics | min_price=50

[13:45:23.145] INFO  flask-basic-example: Product found  
  product_id=1

[13:45:30.001] ERROR flask-basic-example: division by zero
  [Full stacktrace displayed in red]
```

## Troubleshooting

### Local Server Not Connecting
- Make sure the local server is running (`lumberjack serve`)
- Check if port 4317 is available
- Look for connection messages in the Flask terminal

### No Logs Appearing  
- Verify the Flask app shows: "Local server exporter enabled for service: flask-basic-example"
- Check the browser's Network tab for WebSocket connection
- Refresh the browser page

### Port Conflicts
```bash
# Use different ports if needed
lumberjack serve --port 3000  # For web UI
# Flask will still connect to GRPC on 4317
```

## What Makes This Cool?

🚀 **Multi-terminal workflow**: 
- Terminal 1: Log server running
- Terminal 2: Flask app running  
- Terminal 3: Making requests
- Browser: Watching logs in real-time

🎯 **Zero-configuration**: The Flask app automatically detects and connects to the local server

⚡ **Real-time**: Logs appear instantly as requests are made

🔍 **Rich context**: See HTTP traces, custom attributes, and full error details

Perfect for debugging Flask applications during development! 🌲✨