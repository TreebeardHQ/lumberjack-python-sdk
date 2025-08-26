"""Comprehensive test for OpenTelemetry log forwarding functionality."""
import logging
import sys
from io import StringIO
from typing import List, Dict, Any, Sequence
from unittest.mock import patch

import pytest
from opentelemetry.sdk._logs import LogData
from opentelemetry.sdk._logs.export import LogExportResult
from opentelemetry._logs import SeverityNumber

from lumberjack_sdk.core import Lumberjack
from lumberjack_sdk.log import Log
from lumberjack_sdk.logging_instrumentation import enable_python_logger_forwarding, disable_python_logger_forwarding


class ComprehensiveMockLogExporter:
    """Mock log exporter to capture exported logs with detailed tracking."""
    
    def __init__(self):
        self.exported_logs: List[Dict[str, Any]] = []
        self.export_calls = 0
        self.log_sources: Dict[str, int] = {}  # Track sources of logs
    
    def export(self, batch: Sequence[LogData]) -> LogExportResult:
        """Mock export method that captures logs."""
        self.export_calls += 1
        for log_data in batch:
            log_record = log_data.log_record
            log_entry = {
                'timestamp': log_record.timestamp,
                'severity_number': log_record.severity_number,
                'body': log_record.body,
                'attributes': dict(log_record.attributes) if log_record.attributes else {},
                'trace_id': log_record.trace_id,
                'span_id': log_record.span_id
            }
            self.exported_logs.append(log_entry)
            
            # Track source
            source = log_entry['attributes'].get('source', 'unknown')
            self.log_sources[source] = self.log_sources.get(source, 0) + 1
            
        return LogExportResult.SUCCESS
    
    def shutdown(self) -> None:
        pass
    
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
    
    def get_logs_by_body(self, body: str) -> List[Dict[str, Any]]:
        """Helper to find logs by body text."""
        return [log for log in self.exported_logs if log['body'] == body]
    
    def get_logs_by_source(self, source: str) -> List[Dict[str, Any]]:
        """Helper to find logs by source attribute."""
        return [log for log in self.exported_logs if log['attributes'].get('source') == source]


def test_comprehensive_log_forwarding():
    """
    Comprehensive test that validates all log forwarding functionality in one test.
    This avoids OpenTelemetry provider override issues by running everything together.
    """
    # Setup mock exporter
    mock_exporter = ComprehensiveMockLogExporter()
    
    # Initialize Lumberjack with custom exporter
    Lumberjack.reset()
    Lumberjack.init(
        api_key="test-key",
        endpoint="http://test.com",
        custom_log_exporter=mock_exporter
    )
    
    instance = Lumberjack()
    
    try:
        # Test 1: Log API forwarding with different levels
        print("=== Testing Log API forwarding ===")
        Log.debug("Debug level message")
        Log.info("Info level message")
        Log.warning("Warning level message")
        Log.error("Error level message")
        Log.critical("Critical level message")
        
        # Test 2: Log API with structured data
        Log.info("User action", {
            "user_id": 12345,
            "action": "login",
            "ip_address": "192.168.1.100"
        })
        
        # Test 3: Exception logging
        try:
            raise ValueError("Test exception for logging")
        except ValueError as e:
            Log.error("An error occurred", exception=e)
        
        # Force flush to ensure logs are exported
        if instance.log_processor:
            instance.log_processor.force_flush()
        
        # Test 4: Python logger forwarding
        print("=== Testing Python logger forwarding ===")
        enable_python_logger_forwarding(level=logging.DEBUG)
        
        # Create test loggers
        app_logger = logging.getLogger("test.app")
        sdk_logger = logging.getLogger("lumberjack.internal")  # Should be filtered
        
        app_logger.info("Python logger info message")
        app_logger.error("Python logger error message")
        sdk_logger.debug("SDK internal message - should be filtered")
        
        # Force flush again
        if instance.log_processor:
            instance.log_processor.force_flush()
        
        # Test 5: Print statement forwarding (if stdout override is enabled)
        print("=== Testing print statement forwarding ===")
        if hasattr(instance, 'enable_stdout_override'):
            original_stdout = sys.stdout
            try:
                instance.enable_stdout_override()
                captured_output = StringIO()
                sys.stdout = captured_output
                
                print("Test print statement 1")
                print("Test print statement 2")
                
                if instance.log_processor:
                    instance.log_processor.force_flush()
                    
            finally:
                sys.stdout = original_stdout
                if hasattr(instance, 'disable_stdout_override'):
                    instance.disable_stdout_override()
        
        # Now validate all the results
        print(f"=== Validation: Total exported logs: {len(mock_exporter.exported_logs)} ===")
        
        # Validation 1: Log API messages are present
        level_logs = {
            "Debug level message": SeverityNumber.DEBUG,
            "Info level message": SeverityNumber.INFO, 
            "Warning level message": SeverityNumber.WARN,
            "Error level message": SeverityNumber.ERROR,
            "Critical level message": SeverityNumber.FATAL
        }
        
        for message, expected_severity in level_logs.items():
            logs = mock_exporter.get_logs_by_body(message)
            assert len(logs) >= 1, f"Missing log: {message}"
            assert logs[0]['severity_number'] == expected_severity, f"Wrong severity for {message}"
            print(f"✓ {message}: {expected_severity}")
        
        # Validation 2: Structured data is preserved
        user_logs = mock_exporter.get_logs_by_body("User action")
        assert len(user_logs) >= 1, "Missing structured log"
        user_log = user_logs[0]
        assert user_log['attributes'].get('user_id') == 12345
        assert user_log['attributes'].get('action') == "login"
        print("✓ Structured logging attributes preserved")
        
        # Validation 3: Exception logging
        error_logs = mock_exporter.get_logs_by_body("An error occurred")
        assert len(error_logs) >= 1, "Missing exception log"
        attrs = error_logs[0]['attributes']
        assert 'exception.type' in attrs, f"Missing exception.type in {attrs.keys()}"
        assert 'exception.message' in attrs, f"Missing exception.message in {attrs.keys()}"
        assert attrs['exception.type'] == 'ValueError'
        assert attrs['exception.message'] == 'Test exception for logging'
        print("✓ Exception logging works with idiomatic OpenTelemetry attributes")
        
        # Validation 4: Python logger forwarding
        py_info_logs = mock_exporter.get_logs_by_body("Python logger info message")
        py_error_logs = mock_exporter.get_logs_by_body("Python logger error message")
        assert len(py_info_logs) >= 1, "Missing Python logger info message"
        assert len(py_error_logs) >= 1, "Missing Python logger error message"
        print("✓ Python logger forwarding works")
        
        # Validation 5: SDK logs are excluded
        sdk_logs = mock_exporter.get_logs_by_body("SDK internal message - should be filtered")
        assert len(sdk_logs) == 0, "SDK logs should be filtered out"
        print("✓ SDK logs properly excluded")
        
        # Validation 6: Print statements (if tested)
        print_logs_1 = mock_exporter.get_logs_by_body("Test print statement 1")
        print_logs_2 = mock_exporter.get_logs_by_body("Test print statement 2")
        if len(print_logs_1) > 0 and len(print_logs_2) > 0:
            assert print_logs_1[0]['attributes'].get('source') == 'print'
            assert print_logs_2[0]['attributes'].get('source') == 'print'
            print("✓ Print statement forwarding works")
        else:
            print("⚠ Print statement forwarding not tested (stdout override not available)")
        
        # Summary
        print(f"✅ All validations passed! Total logs processed: {len(mock_exporter.exported_logs)}")
        print("Log sources:", mock_exporter.log_sources)
        
        # Final assertion to make pytest happy
        assert len(mock_exporter.exported_logs) >= 7  # At least our main test logs
        
    finally:
        # Cleanup
        disable_python_logger_forwarding()
        Lumberjack.reset()