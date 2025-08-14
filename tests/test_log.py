"""Tests for OpenTelemetry log forwarding functionality."""
import logging
import sys
from io import StringIO
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Sequence

import pytest
from opentelemetry.sdk._logs import LogData
from opentelemetry.sdk._logs.export import LogExportResult

from lumberjack_sdk.core import Lumberjack
from lumberjack_sdk.log import Log
from lumberjack_sdk.logging_instrumentation import enable_python_logger_forwarding, disable_python_logger_forwarding
from lumberjack_sdk.exporters import LumberjackLogExporter


class MockLogExporter:
    """Mock log exporter to capture exported logs."""
    
    def __init__(self):
        self.exported_logs: List[Dict[str, Any]] = []
        self.export_calls = 0
    
    def export(self, batch: Sequence[LogData]) -> LogExportResult:
        """Mock export method that captures logs."""
        self.export_calls += 1
        for log_data in batch:
            log_record = log_data.log_record
            self.exported_logs.append({
                'timestamp': log_record.timestamp,
                'severity_number': log_record.severity_number,
                'body': log_record.body,
                'attributes': dict(log_record.attributes) if log_record.attributes else {},
                'trace_id': log_record.trace_id,
                'span_id': log_record.span_id
            })
        return LogExportResult.SUCCESS
    
    def shutdown(self) -> None:
        pass
    
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


@pytest.fixture
def mock_exporter():
    """Fixture that provides a mock log exporter."""
    return MockLogExporter()


@pytest.fixture
def lumberjack_with_mock_exporter(mock_exporter):
    """Setup Lumberjack with mock exporter."""
    # Reset OpenTelemetry global providers to allow re-initialization
    from opentelemetry import _logs as logs
    from opentelemetry import trace
    logs.set_logger_provider(None)  # type: ignore[attr-defined]
    trace.set_tracer_provider(None)  # type: ignore[attr-defined]
    
    Lumberjack.reset()
    
    # Initialize Lumberjack with our custom mock exporter
    Lumberjack.init(
        api_key="test-key",
        endpoint="http://test.com",
        custom_log_exporter=mock_exporter
    )
    
    instance = Lumberjack()
    
    yield instance, mock_exporter
    
    # Cleanup
    disable_python_logger_forwarding()
    Lumberjack.reset()
    
    # Reset providers again for next test
    logs.set_logger_provider(None)  # type: ignore[attr-defined]
    trace.set_tracer_provider(None)  # type: ignore[attr-defined]


def test_log_api_forwards_to_exporter(lumberjack_with_mock_exporter):
    """Test that Log.info/debug/error methods forward to the exporter."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    # Log messages using our Log API
    Log.info("Test info message", extra_data="test")
    Log.error("Test error message", error_code=500)
    Log.debug("Test debug message")
    
    # Force flush to ensure logs are exported
    if instance.log_processor:
        instance.log_processor.force_flush()
    
    # Check that logs were exported
    assert len(mock_exporter.exported_logs) >= 3
    
    # Find our logs (filter out any SDK logs)
    exported_messages = [log['body'] for log in mock_exporter.exported_logs]
    assert "Test info message" in exported_messages
    assert "Test error message" in exported_messages
    assert "Test debug message" in exported_messages
    
    # Check attributes are preserved
    info_log = next(log for log in mock_exporter.exported_logs if log['body'] == "Test info message")
    assert 'extra_data' in info_log['attributes']
    assert info_log['attributes']['extra_data'] == "test"


def test_python_logger_forwards_to_exporter(lumberjack_with_mock_exporter):
    """Test that Python logging.Logger messages forward to the exporter."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    # Enable Python logger forwarding
    enable_python_logger_forwarding(level=logging.DEBUG)
    
    # Create a test logger and log messages
    test_logger = logging.getLogger("test.app")
    test_logger.info("Python logger info message")
    test_logger.error("Python logger error message")
    test_logger.debug("Python logger debug message")
    
    # Force flush
    if instance.log_processor:
        instance.log_processor.force_flush()
    
    # Check that Python logs were exported
    exported_messages = [log['body'] for log in mock_exporter.exported_logs]
    assert "Python logger info message" in exported_messages
    assert "Python logger error message" in exported_messages
    assert "Python logger debug message" in exported_messages
    
    # Verify SDK logs are NOT exported (should be filtered out)
    sdk_messages = [log['body'] for log in mock_exporter.exported_logs if 'lumberjack' in str(log.get('body', '')).lower()]
    assert len(sdk_messages) == 0


def test_print_statements_forward_to_exporter(lumberjack_with_mock_exporter):
    """Test that print() statements are captured and forwarded to the exporter."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    # Enable stdout override to capture print statements
    instance.enable_stdout_override()
    
    original_stdout = sys.stdout
    try:
        # Capture what would be printed
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Execute print statements
        print("Test print statement 1")
        print("Test print statement 2")
        
        # Force flush
        if instance._log_processor:
            instance._log_processor.force_flush()
        
        # Check that print statements were exported
        exported_messages = [log['body'] for log in mock_exporter.exported_logs]
        assert "Test print statement 1" in exported_messages
        assert "Test print statement 2" in exported_messages
        
        # Check that prints have correct source attribute
        print_logs = [log for log in mock_exporter.exported_logs if "Test print statement" in str(log.get('body', ''))]
        assert len(print_logs) >= 2
        for log in print_logs:
            # StdoutOverride should set source to 'print'
            assert log['attributes'].get('source') == 'print'
            
    finally:
        sys.stdout = original_stdout
        instance.disable_stdout_override()


def test_trace_context_propagation(lumberjack_with_mock_exporter):
    """Test that trace context is properly propagated to logs."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    # Enable Python logger forwarding
    enable_python_logger_forwarding()
    
    # Create a span context
    from lumberjack_sdk.span import start_span, end_span
    
    span = start_span("test-span")
    try:
        # Log within the span
        Log.info("Message within span")
        
        test_logger = logging.getLogger("test.trace")
        test_logger.warning("Python log within span")
        
        # Force flush
        if instance._log_processor:
            instance._log_processor.force_flush()
        
        # Check that logs have trace context
        span_logs = [log for log in mock_exporter.exported_logs 
                    if log['trace_id'] is not None and log['trace_id'] != 0]
        assert len(span_logs) >= 2
        
        # All logs in the span should have the same trace_id
        trace_ids = set(log['trace_id'] for log in span_logs)
        assert len(trace_ids) == 1  # All should have same trace_id
        
    finally:
        end_span(span)


def test_exception_logging(lumberjack_with_mock_exporter):
    """Test that exceptions are properly logged with traceback."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    try:
        raise ValueError("Test exception for logging")
    except ValueError as e:
        # Log the exception
        Log.error("An error occurred", exception=e)
    
    # Force flush
    if instance.log_processor:
        instance.log_processor.force_flush()
    
    # Find the error log
    error_logs = [log for log in mock_exporter.exported_logs if log['body'] == "An error occurred"]
    assert len(error_logs) >= 1
    
    error_log = error_logs[0]
    assert 'exception' in error_log['attributes']


def test_sdk_logs_excluded(lumberjack_with_mock_exporter):
    """Test that our own SDK logs are excluded from forwarding."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    # Enable Python logger forwarding
    enable_python_logger_forwarding(level=logging.DEBUG)
    
    # Create various loggers including SDK loggers
    sdk_logger = logging.getLogger("lumberjack.test")
    sdk_fallback = logging.getLogger("lumberjack.sdk")
    app_logger = logging.getLogger("myapp")
    
    # Log messages from different sources
    sdk_logger.info("SDK internal message - should be filtered")
    sdk_fallback.debug("SDK fallback message - should be filtered")  
    app_logger.info("Application message - should be forwarded")
    
    # Force flush
    if instance.log_processor:
        instance.log_processor.force_flush()
    
    # Check results
    exported_messages = [log['body'] for log in mock_exporter.exported_logs]
    
    # SDK messages should NOT be in exported logs
    assert "SDK internal message - should be filtered" not in exported_messages
    assert "SDK fallback message - should be filtered" not in exported_messages
    
    # Application messages SHOULD be in exported logs
    assert "Application message - should be forwarded" in exported_messages


def test_log_levels_mapping(lumberjack_with_mock_exporter):
    """Test that log levels are correctly mapped to OpenTelemetry severity."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    # Log messages at different levels
    Log.debug("Debug level")
    Log.info("Info level") 
    Log.warning("Warning level")
    Log.error("Error level")
    Log.critical("Critical level")
    
    # Force flush
    if instance.log_processor:
        instance.log_processor.force_flush()
    
    # Debug: print what we actually got
    print(f"Total exported logs: {len(mock_exporter.exported_logs)}")
    for i, log in enumerate(mock_exporter.exported_logs):
        print(f"Log {i}: {log['body']} -> {log['severity_number']}")
    
    # Check severity numbers are correct
    log_by_message = {log['body']: log for log in mock_exporter.exported_logs}
    
    # OpenTelemetry severity number mappings
    from opentelemetry._logs import SeverityNumber
    
    assert log_by_message["Debug level"]['severity_number'] == SeverityNumber.DEBUG
    assert log_by_message["Info level"]['severity_number'] == SeverityNumber.INFO
    assert log_by_message["Warning level"]['severity_number'] == SeverityNumber.WARN
    assert log_by_message["Error level"]['severity_number'] == SeverityNumber.ERROR
    assert log_by_message["Critical level"]['severity_number'] == SeverityNumber.FATAL


def test_structured_logging_attributes(lumberjack_with_mock_exporter):
    """Test that structured logging attributes are preserved."""
    instance, mock_exporter = lumberjack_with_mock_exporter
    
    # Log with structured data
    Log.info("User action", {
        "user_id": 12345,
        "action": "login",
        "ip_address": "192.168.1.100",
        "metadata": {
            "browser": "Chrome",
            "version": "95.0"
        }
    })
    
    # Force flush
    if instance.log_processor:
        instance.log_processor.force_flush()
    
    # Find the log
    user_logs = [log for log in mock_exporter.exported_logs if log['body'] == "User action"]
    assert len(user_logs) >= 1
    
    user_log = user_logs[0]
    attrs = user_log['attributes']
    
    # Check that structured attributes are preserved
    assert attrs.get('user_id') == 12345
    assert attrs.get('action') == "login"
    assert attrs.get('ip_address') == "192.168.1.100"
    assert 'metadata' in attrs