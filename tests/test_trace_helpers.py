"""Tests for trace helper functions."""
import pytest
from unittest.mock import patch

from opentelemetry import context, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import SpanContext, TraceFlags

from lumberjack_sdk.trace_helpers import (
    establish_trace_context,
    extract_trace_context,
    get_span_context_from_headers,
    inject_trace_context,
    parse_traceparent,
    start_span_with_remote_parent,
)


class TestTraceHelpers:
    """Test suite for trace helper functions."""
    
    @pytest.fixture(autouse=True)
    def setup_tracer_provider(self):
        """Set up a tracer provider for tests."""
        # Set up a proper tracer provider for testing
        tracer_provider = TracerProvider()
        trace.set_tracer_provider(tracer_provider)
        yield
        # Clean up after test
        trace.set_tracer_provider(None)
    
    def test_extract_trace_context_with_valid_header_dict(self):
        """Test extracting trace context from valid headers dict."""
        headers = {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        }
        
        ctx = extract_trace_context(headers)
        assert ctx is not None
        
        span = trace.get_current_span(ctx)
        span_context = span.get_span_context()
        assert span_context.is_valid
        assert format(span_context.trace_id, '032x') == '4bf92f3577b34da6a3ce929d0e0e4736'
        assert format(span_context.span_id, '016x') == '00f067aa0ba902b7'
    
    def test_extract_trace_context_with_valid_header_string(self):
        """Test extracting trace context from valid header string."""
        header = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        
        ctx = extract_trace_context(header)
        assert ctx is not None
        
        span = trace.get_current_span(ctx)
        span_context = span.get_span_context()
        assert span_context.is_valid
        assert format(span_context.trace_id, '032x') == '4bf92f3577b34da6a3ce929d0e0e4736'
        assert format(span_context.span_id, '016x') == '00f067aa0ba902b7'
    
    def test_extract_trace_context_with_invalid_header(self):
        """Test extracting trace context from invalid header."""
        invalid_headers = [
            'invalid-header',
            '00-invalid-trace-id-00f067aa0ba902b7-01',
            '00-4bf92f3577b34da6a3ce929d0e0e4736-invalid-span-01',
            '',
            None
        ]
        
        for invalid_header in invalid_headers:
            if invalid_header is not None:
                ctx = extract_trace_context(invalid_header)
                assert ctx is None
    
    def test_get_span_context_from_headers_with_valid_headers(self):
        """Test getting span context from valid headers."""
        headers = {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        }
        
        span_context = get_span_context_from_headers(headers)
        assert span_context is not None
        assert span_context.is_valid
        assert format(span_context.trace_id, '032x') == '4bf92f3577b34da6a3ce929d0e0e4736'
        assert format(span_context.span_id, '016x') == '00f067aa0ba902b7'
    
    def test_get_span_context_from_headers_with_invalid_headers(self):
        """Test getting span context from invalid headers."""
        invalid_cases = [
            {'traceparent': 'invalid'},
            {'other-header': 'value'},
            {},
            'invalid-string'
        ]
        
        for invalid_case in invalid_cases:
            span_context = get_span_context_from_headers(invalid_case)
            assert span_context is None
    
    def test_inject_trace_context_default(self):
        """Test injecting current trace context."""
        headers = inject_trace_context()
        assert isinstance(headers, dict)
        # Should have at least traceparent when there's an active context
    
    def test_inject_trace_context_into_existing_carrier(self):
        """Test injecting trace context into existing headers."""
        existing_headers = {'content-type': 'application/json'}
        headers = inject_trace_context(carrier=existing_headers)
        
        assert headers is existing_headers  # Should modify the same dict
        assert 'content-type' in headers
        # Additional trace headers may be added depending on current context
    
    def test_start_span_with_remote_parent_valid_headers(self):
        """Test starting span with valid remote parent."""
        headers = {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        }
        
        with start_span_with_remote_parent('test-operation', headers) as span:
            span_context = span.get_span_context()
            assert span_context.is_valid
            # Should be child of the remote parent
            assert format(span_context.trace_id, '032x') == '4bf92f3577b34da6a3ce929d0e0e4736'
    
    def test_start_span_with_remote_parent_invalid_headers(self):
        """Test starting span with invalid headers falls back to new root span."""
        invalid_headers = {'other': 'header'}
        
        with start_span_with_remote_parent('test-operation', invalid_headers) as span:
            span_context = span.get_span_context()
            assert span_context.is_valid
            # Should be a new root span, not connected to the invalid parent
    
    def test_start_span_with_custom_tracer(self):
        """Test starting span with custom tracer."""
        headers = {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        }
        
        custom_tracer = trace.get_tracer('custom-tracer')
        with start_span_with_remote_parent('test-op', headers, tracer=custom_tracer) as span:
            span_context = span.get_span_context()
            assert span_context.is_valid
    
    def test_parse_traceparent_valid_header(self):
        """Test parsing valid traceparent header (legacy function)."""
        header = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        
        result = parse_traceparent(header)
        assert result is not None
        assert result['version'] == '00'
        assert result['trace_id'] == '4bf92f3577b34da6a3ce929d0e0e4736'
        assert result['parent_id'] == '00f067aa0ba902b7'
        assert result['flags'] == '01'
    
    def test_parse_traceparent_invalid_header(self):
        """Test parsing invalid traceparent header (legacy function)."""
        invalid_headers = [
            'invalid',
            '00-invalid-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
            '',
            None
        ]
        
        for invalid_header in invalid_headers:
            result = parse_traceparent(invalid_header)
            assert result is None
    
    def test_establish_trace_context_valid_ids(self):
        """Test establishing trace context from valid IDs (legacy function)."""
        trace_id = '4bf92f3577b34da6a3ce929d0e0e4736'
        span_id = '00f067aa0ba902b7'
        
        span_context = establish_trace_context(trace_id, span_id)
        assert span_context.is_valid
        assert format(span_context.trace_id, '032x') == trace_id
        assert format(span_context.span_id, '016x') == span_id
        assert span_context.is_remote is True
        assert span_context.trace_flags == TraceFlags.SAMPLED
    
    def test_establish_trace_context_with_clear_existing(self):
        """Test establish_trace_context with clear_existing parameter."""
        trace_id = '4bf92f3577b34da6a3ce929d0e0e4736'
        span_id = '00f067aa0ba902b7'
        
        # Test with clear_existing=True (default)
        span_context1 = establish_trace_context(trace_id, span_id, clear_existing=True)
        assert span_context1.is_valid
        
        # Test with clear_existing=False
        span_context2 = establish_trace_context(trace_id, span_id, clear_existing=False)
        assert span_context2.is_valid
        
        # Both should produce the same result since the parameter is currently unused
        assert span_context1.trace_id == span_context2.trace_id
        assert span_context1.span_id == span_context2.span_id
    
    def test_extract_trace_context_custom_carrier_key_invalid(self):
        """Test extracting trace context with custom carrier key (should fail with W3C propagator)."""
        headers = {
            'custom-trace-header': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        }
        
        # OpenTelemetry's W3C propagator only recognizes 'traceparent', so this should return None
        ctx = extract_trace_context(headers, carrier_key='custom-trace-header')
        assert ctx is None
    
    def test_get_span_context_from_headers_custom_carrier_key_invalid(self):
        """Test getting span context with custom carrier key (should fail with W3C propagator)."""
        headers = {
            'x-trace-id': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        }
        
        # OpenTelemetry's W3C propagator only recognizes 'traceparent', so this should return None
        span_context = get_span_context_from_headers(headers, carrier_key='x-trace-id')
        assert span_context is None
    
    def test_start_span_with_remote_parent_custom_carrier_key_fallback(self):
        """Test starting span with custom carrier key falls back to new root span."""
        headers = {
            'x-custom-trace': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        }
        
        # Should fall back to creating a new root span since W3C propagator won't recognize custom header
        with start_span_with_remote_parent(
            'test-op', headers, carrier_key='x-custom-trace'
        ) as span:
            span_context = span.get_span_context()
            assert span_context.is_valid
            # This will be a new root span, not connected to the header