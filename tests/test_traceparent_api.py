"""
Tests for the traceparent API module.
"""
import pytest
from unittest.mock import Mock, patch

from opentelemetry import trace
from opentelemetry.trace import SpanContext, TraceFlags, Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider

from lumberjack_sdk.traceparent_api import (
    get_current_traceparent,
    get_trace_context_info,
    format_traceparent,
    parse_traceparent
)


@pytest.fixture
def setup_tracer():
    """Set up OpenTelemetry tracer for testing."""
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(__name__)
    return tracer


def test_get_current_traceparent_with_active_span(setup_tracer):
    """Test getting traceparent with an active span."""
    tracer = setup_tracer
    
    with tracer.start_as_current_span("test-span") as span:
        traceparent = get_current_traceparent()
        
        assert traceparent is not None
        assert isinstance(traceparent, str)
        
        # Validate format: 00-{32 hex}-{16 hex}-{2 hex}
        parts = traceparent.split('-')
        assert len(parts) == 4
        assert parts[0] == "00"  # version
        assert len(parts[1]) == 32  # trace_id
        assert len(parts[2]) == 16  # span_id
        assert len(parts[3]) == 2   # flags
        
        # Verify it matches the actual span context
        span_context = span.get_span_context()
        expected_trace_id = format(span_context.trace_id, '032x')
        expected_span_id = format(span_context.span_id, '016x')
        assert parts[1] == expected_trace_id
        assert parts[2] == expected_span_id


def test_get_current_traceparent_without_active_span():
    """Test getting traceparent when no span is active."""
    # Ensure no active span
    traceparent = get_current_traceparent()
    assert traceparent is None


def test_get_trace_context_info_with_active_span(setup_tracer):
    """Test getting detailed trace context info with an active span."""
    tracer = setup_tracer
    
    with tracer.start_as_current_span("test-span") as span:
        info = get_trace_context_info()
        
        assert info is not None
        assert isinstance(info, dict)
        
        # Check all expected fields are present
        assert 'traceparent' in info
        assert 'trace_id' in info
        assert 'span_id' in info
        assert 'parent_span_id' in info
        assert 'flags' in info
        assert 'is_sampled' in info
        
        # Validate field formats
        assert len(info['trace_id']) == 32
        assert len(info['span_id']) == 16
        assert len(info['flags']) == 2
        assert isinstance(info['is_sampled'], bool)
        
        # Verify traceparent format
        expected_traceparent = f"00-{info['trace_id']}-{info['span_id']}-{info['flags']}"
        assert info['traceparent'] == expected_traceparent


def test_get_trace_context_info_without_active_span():
    """Test getting trace context info when no span is active."""
    info = get_trace_context_info()
    assert info is None


def test_get_trace_context_info_with_nested_spans(setup_tracer):
    """Test getting trace context info with nested spans."""
    tracer = setup_tracer
    
    with tracer.start_as_current_span("parent-span") as parent_span:
        parent_context = parent_span.get_span_context()
        parent_span_id = format(parent_context.span_id, '016x')
        
        with tracer.start_as_current_span("child-span") as child_span:
            info = get_trace_context_info()
            
            assert info is not None
            # Trace ID should be the same for parent and child
            assert info['trace_id'] == format(parent_context.trace_id, '032x')
            # Span ID should be different
            assert info['span_id'] != parent_span_id


def test_format_traceparent_valid_inputs():
    """Test formatting a traceparent with valid inputs."""
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    span_id = "00f067aa0ba902b7"
    
    # Test with sampled=True
    result = format_traceparent(trace_id, span_id, sampled=True)
    assert result == f"00-{trace_id}-{span_id}-01"
    
    # Test with sampled=False
    result = format_traceparent(trace_id, span_id, sampled=False)
    assert result == f"00-{trace_id}-{span_id}-00"


def test_format_traceparent_invalid_trace_id():
    """Test formatting with invalid trace ID."""
    with pytest.raises(ValueError, match="trace_id must be 32 hex characters"):
        format_traceparent("invalid", "00f067aa0ba902b7")
    
    with pytest.raises(ValueError, match="Invalid hex format"):
        format_traceparent("gggggggggggggggggggggggggggggggg", "00f067aa0ba902b7")


def test_format_traceparent_invalid_span_id():
    """Test formatting with invalid span ID."""
    with pytest.raises(ValueError, match="span_id must be 16 hex characters"):
        format_traceparent("4bf92f3577b34da6a3ce929d0e0e4736", "invalid")
    
    with pytest.raises(ValueError, match="Invalid hex format"):
        format_traceparent("4bf92f3577b34da6a3ce929d0e0e4736", "gggggggggggggggg")


def test_parse_traceparent_valid():
    """Test parsing a valid traceparent string."""
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    result = parse_traceparent(traceparent)
    
    assert result is not None
    assert result['version'] == '00'
    assert result['trace_id'] == '4bf92f3577b34da6a3ce929d0e0e4736'
    assert result['span_id'] == '00f067aa0ba902b7'
    assert result['flags'] == '01'
    assert result['is_sampled'] is True


def test_parse_traceparent_not_sampled():
    """Test parsing a traceparent with not-sampled flag."""
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00"
    result = parse_traceparent(traceparent)
    
    assert result is not None
    assert result['flags'] == '00'
    assert result['is_sampled'] is False


def test_parse_traceparent_invalid_format():
    """Test parsing invalid traceparent formats."""
    # Wrong number of parts
    assert parse_traceparent("00-invalid") is None
    
    # Wrong version
    assert parse_traceparent("01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01") is None
    
    # Wrong trace ID length
    assert parse_traceparent("00-invalid-00f067aa0ba902b7-01") is None
    
    # Wrong span ID length
    assert parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-invalid-01") is None
    
    # Wrong flags length
    assert parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-invalid") is None
    
    # Invalid hex
    assert parse_traceparent("00-gggggggggggggggggggggggggggggggg-00f067aa0ba902b7-01") is None


def test_roundtrip_format_and_parse():
    """Test that format and parse are inverse operations."""
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    span_id = "00f067aa0ba902b7"
    
    # Format a traceparent
    formatted = format_traceparent(trace_id, span_id, sampled=True)
    
    # Parse it back
    parsed = parse_traceparent(formatted)
    
    assert parsed is not None
    assert parsed['trace_id'] == trace_id
    assert parsed['span_id'] == span_id
    assert parsed['is_sampled'] is True


def test_get_current_traceparent_with_non_recording_span():
    """Test getting traceparent with a non-recording span."""
    with patch('opentelemetry.trace.get_current_span') as mock_get_span:
        mock_span = Mock()
        mock_span.is_recording.return_value = False
        mock_get_span.return_value = mock_span
        
        traceparent = get_current_traceparent()
        assert traceparent is None


def test_get_current_traceparent_with_invalid_span_context():
    """Test getting traceparent with an invalid span context."""
    with patch('opentelemetry.trace.get_current_span') as mock_get_span:
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        
        mock_context = Mock()
        mock_context.is_valid = False
        mock_span.get_span_context.return_value = mock_context
        mock_get_span.return_value = mock_span
        
        traceparent = get_current_traceparent()
        assert traceparent is None