"""
OpenTelemetry-based Flask instrumentation for Lumberjack.

This module provides Flask integration using OpenTelemetry's tracing system.
"""
import importlib
import traceback

from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import Status, StatusCode, SpanKind

from .core import Lumberjack
from .internal_utils.fallback_logger import sdk_logger


class OTelLumberjackFlask:
    """OpenTelemetry-based Flask instrumentation for Lumberjack."""

    @staticmethod
    def _get_request():
        """Get Flask request object."""
        try:
            return importlib.import_module("flask").request
        except Exception as e:
            sdk_logger.error(
                f"Error in OTelLumberjackFlask._get_request : {str(e)}: {traceback.format_exc()}")
            return None

    @staticmethod
    def instrument(app) -> None:
        """Instrument a Flask application with OpenTelemetry tracing.

        Args:
            app: The Flask application to instrument
        """
        if not app:
            sdk_logger.error("OTelLumberjackFlask: No app provided")
            return

        if getattr(app, "_otel_lumberjack_instrumented", False):
            return

        try:
            sdk_logger.info("OTelLumberjackFlask: Instrumenting Flask application with OTEL")

            # Get the tracer
            tracer = trace.get_tracer(__name__)

            @app.before_request
            def start_trace():
                """Start a new OTEL span when a request starts."""
                try:
                    request = OTelLumberjackFlask._get_request()
                    if not request:
                        return

                    # Get the route pattern (e.g., '/user/<id>' instead of '/user/123')
                    if request.url_rule:
                        route_pattern = request.url_rule.rule
                    else:
                        route_pattern = f"[unmatched] {request.path}"
                    
                    # Create a name in the format "METHOD /path/pattern"
                    span_name = f"{request.method} {route_pattern}"

                    # Extract context from HTTP headers for distributed tracing
                    parent_context = extract(request.headers)

                    # Start span with extracted context
                    span = tracer.start_span(
                        name=span_name,
                        kind=SpanKind.SERVER,
                        context=parent_context
                    )

                    # Set HTTP attributes using OTEL semantic conventions
                    span.set_attribute("http.method", request.method)
                    span.set_attribute("http.url", request.url)
                    span.set_attribute("http.route", route_pattern)
                    span.set_attribute("http.scheme", request.scheme)
                    span.set_attribute("http.target", request.path)
                    
                    if request.remote_addr:
                        span.set_attribute("http.client_ip", request.remote_addr)

                    # User agent information
                    if request.user_agent:
                        span.set_attribute("http.user_agent", request.user_agent.string)
                        if request.user_agent.platform:
                            span.set_attribute("user_agent.platform", request.user_agent.platform)
                        if request.user_agent.browser:
                            span.set_attribute("user_agent.browser", request.user_agent.browser)
                        if request.user_agent.version:
                            span.set_attribute("user_agent.version", request.user_agent.version)

                    # Headers
                    if request.headers.get("Referer"):
                        span.set_attribute("http.referer", request.headers.get("Referer"))
                    if request.headers.get("X-Forwarded-For"):
                        span.set_attribute("http.x_forwarded_for", request.headers.get("X-Forwarded-For"))
                    if request.headers.get("X-Real-IP"):
                        span.set_attribute("http.x_real_ip", request.headers.get("X-Real-IP"))

                    # Query parameters
                    if request.args:
                        for key, value in request.args.to_dict(flat=True).items():
                            span.set_attribute(f"http.query.{key}", value)

                    # Store span in Flask's g object for access in other parts of the request
                    try:
                        flask = importlib.import_module("flask")
                        flask.g._otel_lumberjack_span = span
                    except Exception:
                        pass  # g not available, that's ok

                except Exception as e:
                    sdk_logger.error(
                        f"Error in OTelLumberjackFlask.start_trace : {str(e)}: {traceback.format_exc()}")

            @app.after_request
            def finalize_span(response):
                """Finalize the span with response information."""
                try:
                    # Get the span from Flask's g object or current context
                    span = None
                    try:
                        flask = importlib.import_module("flask")
                        span = getattr(flask.g, '_otel_lumberjack_span', None)
                    except Exception:
                        pass
                    
                    if not span:
                        span = trace.get_current_span()
                    
                    if span and span.is_recording():
                        # Set response attributes
                        span.set_attribute("http.status_code", response.status_code)
                        
                        # Set span status based on HTTP status code
                        if response.status_code >= 400:
                            span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                        elif response.status_code >= 300:
                            # Redirects are not errors
                            span.set_status(Status(StatusCode.OK))
                        else:
                            span.set_status(Status(StatusCode.OK))

                except Exception as e:
                    sdk_logger.error(
                        f"Error in OTelLumberjackFlask.finalize_span: {str(e)}: {traceback.format_exc()}")
                
                return response

            @app.teardown_request
            def end_span_on_teardown(exc):
                """End the span when the request ends."""
                try:
                    # Get the span from Flask's g object or current context
                    span = None
                    try:
                        flask = importlib.import_module("flask")
                        span = getattr(flask.g, '_otel_lumberjack_span', None)
                    except Exception:
                        pass
                    
                    if not span:
                        span = trace.get_current_span()

                    if span and span.is_recording():
                        if exc:
                            # Record exception and set error status
                            span.record_exception(exc)
                            span.set_status(Status(StatusCode.ERROR, str(exc)))
                        
                        # End the span
                        span.end()

                except Exception as e:
                    sdk_logger.error(
                        f"Error in OTelLumberjackFlask.end_span_on_teardown: {str(e)}: {traceback.format_exc()}")

            app._otel_lumberjack_instrumented = True
            
        except Exception as e:
            sdk_logger.error(
                f"Error in OTelLumberjackFlask.instrument: {str(e)}: {traceback.format_exc()}")


# Backward compatibility alias
LumberjackFlask = OTelLumberjackFlask