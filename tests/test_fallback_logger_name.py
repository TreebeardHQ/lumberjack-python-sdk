"""
Tests for fallback logger name functionality.
"""
import io
import sys
from unittest.mock import patch

import pytest
from opentelemetry.sdk._logs import LogData, LogRecord
from opentelemetry._logs import SeverityNumber
from opentelemetry.sdk.resources import Resource

from lumberjack_sdk.fallback_exporters import FallbackLogExporter
from lumberjack_sdk.constants import LOGGER_NAME_KEY_RESERVED_V2


def test_fallback_logger_uses_logger_name_from_attributes():
    """Test that fallback logger uses the logger name from log record attributes."""
    # Create a log exporter
    exporter = FallbackLogExporter()
    
    # Create a log record with logger name in attributes
    log_record = LogRecord(
        timestamp=1234567890000000000,
        observed_timestamp=1234567890000000000,
        trace_id=None,
        span_id=None,
        trace_flags=None,
        severity_text="INFO",
        severity_number=SeverityNumber.INFO,
        body="Test message from custom logger",
        resource=Resource.create({}),
        attributes={
            LOGGER_NAME_KEY_RESERVED_V2: "my.custom.logger",
            "code.file.path": "/path/to/myfile.py",
            "code.function.name": "test_function",
            "code.line.number": 42,
            "extra_field": "value"
        }
    )
    
    log_data = LogData(log_record=log_record)
    
    # Capture stdout to check the output
    captured_output = io.StringIO()
    with patch('sys.stderr', captured_output):
        exporter.export([log_data])
    
    output = captured_output.getvalue()
    
    # Should show the custom logger name instead of 'lumberjack'
    assert "my.custom.logger" in output
    assert "Test message from custom logger" in output
    assert "lumberjack" not in output  # Should not show the default name
    
    # Should show code location in file#function:line format
    assert "[myfile.py#test_function:42]" in output
    
    # Should NOT show logger in the attributes section (it's now in the logger name)
    assert "logger=" not in output
    
    # Should still show extra attributes
    assert "extra_field=value" in output


def test_fallback_logger_uses_semantic_convention_logger_name():
    """Test that fallback logger uses semantic convention logger_name attribute."""
    exporter = FallbackLogExporter()
    
    # Create a log record with semantic convention logger_name
    log_record = LogRecord(
        timestamp=1234567890000000000,
        observed_timestamp=1234567890000000000,
        trace_id=None,
        span_id=None,
        trace_flags=None,
        severity_text="INFO",
        severity_number=SeverityNumber.INFO,
        body="Test message with semantic logger name",
        resource=Resource.create({}),
        attributes={
            "logger_name": "semantic.convention.logger",
            "other_field": "test"
        }
    )
    
    log_data = LogData(log_record=log_record)
    
    # Capture stdout to check the output
    captured_output = io.StringIO()
    with patch('sys.stderr', captured_output):
        exporter.export([log_data])
    
    output = captured_output.getvalue()
    
    # Should show the semantic convention logger name
    assert "semantic.convention.logger" in output
    assert "Test message with semantic logger name" in output


def test_fallback_logger_prefers_reserved_key_over_semantic():
    """Test that reserved key takes precedence over semantic convention."""
    exporter = FallbackLogExporter()
    
    # Create a log record with both logger name attributes
    log_record = LogRecord(
        timestamp=1234567890000000000,
        observed_timestamp=1234567890000000000,
        trace_id=None,
        span_id=None,
        trace_flags=None,
        severity_text="INFO",
        severity_number=SeverityNumber.INFO,
        body="Test precedence",
        resource=Resource.create({}),
        attributes={
            LOGGER_NAME_KEY_RESERVED_V2: "reserved.key.logger",
            "logger_name": "semantic.logger",
        }
    )
    
    log_data = LogData(log_record=log_record)
    
    # Capture stdout to check the output
    captured_output = io.StringIO()
    with patch('sys.stderr', captured_output):
        exporter.export([log_data])
    
    output = captured_output.getvalue()
    
    # Should show the reserved key logger name
    assert "reserved.key.logger" in output
    assert "semantic.logger" not in output


def test_fallback_logger_falls_back_to_default_when_no_logger_name():
    """Test that fallback logger uses default 'lumberjack' when no logger name in attributes."""
    exporter = FallbackLogExporter()
    
    # Create a log record without logger name
    log_record = LogRecord(
        timestamp=1234567890000000000,
        observed_timestamp=1234567890000000000,
        trace_id=None,
        span_id=None,
        trace_flags=None,
        severity_text="INFO",
        severity_number=SeverityNumber.INFO,
        body="Test message without logger name",
        resource=Resource.create({}),
        attributes={
            "some_field": "value"
        }
    )
    
    log_data = LogData(log_record=log_record)
    
    # Capture stdout to check the output
    captured_output = io.StringIO()
    with patch('sys.stderr', captured_output):
        exporter.export([log_data])
    
    output = captured_output.getvalue()
    
    # Should fall back to default 'lumberjack' name
    assert "lumberjack" in output
    assert "Test message without logger name" in output


def test_fallback_logger_handles_empty_logger_name():
    """Test that fallback logger handles empty logger name gracefully."""
    exporter = FallbackLogExporter()
    
    # Create a log record with empty logger name
    log_record = LogRecord(
        timestamp=1234567890000000000,
        observed_timestamp=1234567890000000000,
        trace_id=None,
        span_id=None,
        trace_flags=None,
        severity_text="INFO",
        severity_number=SeverityNumber.INFO,
        body="Test message with empty logger name",
        resource=Resource.create({}),
        attributes={
            LOGGER_NAME_KEY_RESERVED_V2: "",
        }
    )
    
    log_data = LogData(log_record=log_record)
    
    # Capture stdout to check the output
    captured_output = io.StringIO()
    with patch('sys.stderr', captured_output):
        exporter.export([log_data])
    
    output = captured_output.getvalue()
    
    # Should fall back to default 'lumberjack' name when logger name is empty
    assert "lumberjack" in output
    assert "Test message with empty logger name" in output