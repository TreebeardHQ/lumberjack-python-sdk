"""
Unit tests for LumberjackConsoleFormatter.
"""
import json
import logging
import pytest
from datetime import datetime

from lumberjack_sdk.console_formatter import LumberjackConsoleFormatter


class TestLumberjackConsoleFormatter:
    """Test cases for LumberjackConsoleFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = LumberjackConsoleFormatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )

    def create_log_record(
        self, 
        message: str = "Test message",
        level: int = logging.INFO,
        name: str = "test.logger",
        **extra_attrs
    ) -> logging.LogRecord:
        """Create a LogRecord for testing."""
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname="test.py",
            lineno=42,
            msg=message,
            args=(),
            exc_info=None
        )
        
        # Add extra attributes
        for key, value in extra_attrs.items():
            setattr(record, key, value)
            
        return record

    def test_basic_formatting(self):
        """Test basic log message formatting without extra attributes."""
        record = self.create_log_record("Application started")
        formatted = self.formatter.format(record)
        
        # Should contain the basic format elements
        assert "[INFO]" in formatted
        assert "test.logger" in formatted
        assert "Application started" in formatted
        assert ":" in formatted  # Time format
        
        # Should not contain JSON (no extra attributes)
        assert "{" not in formatted
        assert "}" not in formatted

    def test_extra_attributes_as_json(self):
        """Test that extra attributes are formatted as JSON."""
        record = self.create_log_record(
            "User action",
            user_id=123,
            action="login",
            ip_address="192.168.1.1"
        )
        formatted = self.formatter.format(record)
        
        # Should contain basic message
        assert "User action" in formatted
        
        # Should contain JSON attributes
        assert '{"user_id":123,"action":"login","ip_address":"192.168.1.1"}' in formatted

    def test_filters_standard_attributes(self):
        """Test that standard logging attributes are filtered out."""
        record = self.create_log_record(
            "Test message",
            user_id=456,  # This should appear
        )
        
        # Manually add some standard attributes that shouldn't appear
        # (these are actual standard LogRecord attribute names)
        record.thread = 12345
        record.process = 67890
        record.created = 1234567890.123
        
        formatted = self.formatter.format(record)
        
        # User attribute should appear
        assert '"user_id":456' in formatted
        
        # Standard attributes should not appear
        assert 'thread' not in formatted
        assert 'process' not in formatted
        assert 'created' not in formatted

    def test_filters_internal_attributes(self):
        """Test that internal SDK and OpenTelemetry attributes are filtered."""
        record = self.create_log_record(
            "Test message",
            user_id=789,  # This should appear
            otel_trace_id="abc123",  # This should be filtered
            tb_rv2_span_id="def456",  # This should be filtered
            _private_attr="secret"  # This should be filtered
        )
        
        formatted = self.formatter.format(record)
        
        # User attribute should appear
        assert '"user_id":789' in formatted
        
        # Internal attributes should not appear
        assert 'otel_trace_id' not in formatted
        assert 'tb_rv2_span_id' not in formatted
        assert '_private_attr' not in formatted

    def test_exception_handling(self):
        """Test proper exception formatting."""
        # Create an exception
        try:
            raise ValueError("Test error message")
        except ValueError:
            exc_info = True
            import sys
            exc_info = sys.exc_info()
        
        record = self.create_log_record(
            "Operation failed",
            level=logging.ERROR,
            user_id=999
        )
        record.exc_info = exc_info
        
        formatted = self.formatter.format(record)
        
        # Should contain the error message
        assert "Operation failed" in formatted
        
        # Should contain user data
        assert '"user_id":999' in formatted
        
        # Should contain exception traceback
        assert "Traceback" in formatted
        assert "ValueError: Test error message" in formatted

    def test_exception_without_extra_attributes(self):
        """Test exception formatting when no extra attributes present."""
        try:
            raise RuntimeError("Something went wrong")
        except RuntimeError:
            import sys
            exc_info = sys.exc_info()
        
        record = self.create_log_record(
            "Critical error",
            level=logging.ERROR
        )
        record.exc_info = exc_info
        
        formatted = self.formatter.format(record)
        
        # Should contain the error message
        assert "Critical error" in formatted
        
        # Should contain exception traceback
        assert "Traceback" in formatted
        assert "RuntimeError: Something went wrong" in formatted
        
        # Should not contain JSON (no extra attributes)
        assert '{"' not in formatted

    def test_empty_extra_attributes(self):
        """Test handling when extra attributes dict is empty."""
        record = self.create_log_record("Simple message")
        formatted = self.formatter.format(record)
        
        # Should contain basic message
        assert "Simple message" in formatted
        
        # Should not contain JSON
        assert "{" not in formatted

    def test_complex_object_serialization(self):
        """Test handling of complex objects that need string conversion."""
        complex_obj = {"nested": {"data": [1, 2, 3]}}
        record = self.create_log_record(
            "Complex data",
            user_id=111,
            complex_data=complex_obj
        )
        
        formatted = self.formatter.format(record)
        
        # Should contain basic message
        assert "Complex data" in formatted
        
        # Should contain JSON with complex object serialized
        assert '"user_id":111' in formatted
        assert '"complex_data":' in formatted
        assert '"nested"' in formatted

    def test_non_serializable_object_fallback(self):
        """Test fallback when JSON serialization fails."""
        # Create an object that can't be JSON serialized
        class NonSerializable:
            def __str__(self):
                return "NonSerializable()"
        
        non_serializable = NonSerializable()
        
        # Mock the JSON serialization to force failure
        original_dumps = json.dumps
        
        def failing_dumps(*args, **kwargs):
            if any(isinstance(arg, NonSerializable) for arg in args):
                raise TypeError("Not JSON serializable")
            return original_dumps(*args, **kwargs)
        
        import lumberjack_sdk.console_formatter
        lumberjack_sdk.console_formatter.json.dumps = failing_dumps
        
        try:
            record = self.create_log_record(
                "Test message",
                user_id=222,
                bad_obj=non_serializable
            )
            
            formatted = self.formatter.format(record)
            
            # Should contain basic message
            assert "Test message" in formatted
            
            # Should contain string representation as fallback
            assert "user_id" in formatted
            assert "bad_obj" in formatted
            
        finally:
            # Restore original dumps
            lumberjack_sdk.console_formatter.json.dumps = original_dumps

    def test_get_extra_attributes_method(self):
        """Test the _get_extra_attributes method directly."""
        record = self.create_log_record(
            "Test",
            user_id=333,
            action="test",
            otel_should_be_filtered="yes",
            tb_rv2_also_filtered="yes",
            _private_filtered="yes"
        )
        
        extras = self.formatter._get_extra_attributes(record)
        
        # Should include user attributes
        assert extras["user_id"] == 333
        assert extras["action"] == "test"
        
        # Should exclude filtered attributes
        assert "otel_should_be_filtered" not in extras
        assert "tb_rv2_also_filtered" not in extras
        assert "_private_filtered" not in extras
        
        # Should exclude standard logging attributes
        assert "name" not in extras
        assert "levelname" not in extras
        assert "message" not in extras

    def test_format_extras_method(self):
        """Test the _format_extras method directly."""
        extras = {
            "user_id": 444,
            "action": "format_test",
            "data": [1, 2, 3]
        }
        
        result = self.formatter._format_extras(extras)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["user_id"] == 444
        assert parsed["action"] == "format_test"
        assert parsed["data"] == [1, 2, 3]
        
        # Should be compact (no spaces)
        assert " " not in result.replace('"format_test"', '')  # Allow space in string values

    def test_different_log_levels(self):
        """Test formatting with different log levels."""
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL")
        ]
        
        for level_num, level_name in levels:
            record = self.create_log_record(
                f"{level_name} message",
                level=level_num,
                test_level=level_name
            )
            
            formatted = self.formatter.format(record)
            
            # Should contain correct level
            assert f"[{level_name}]" in formatted
            assert f"{level_name} message" in formatted
            assert f'"test_level":"{level_name}"' in formatted

    def test_custom_format_string(self):
        """Test with different format string."""
        custom_formatter = LumberjackConsoleFormatter(
            fmt='[%(levelname)s] %(name)s - %(message)s',  # No timestamp
            datefmt='%H:%M:%S'
        )
        
        record = self.create_log_record(
            "Custom format test",
            test_attr="custom"
        )
        
        formatted = custom_formatter.format(record)
        
        # Should match custom format
        assert formatted.startswith("[INFO] test.logger - Custom format test")
        assert '"test_attr":"custom"' in formatted
        
        # Should not contain timestamp (not in format)
        assert ":" not in formatted.split(" - ")[0]  # No colon in the level part