"""
Flask instrumentation for Lumberjack using OpenTelemetry.

This module provides a thin wrapper around OpenTelemetry's Flask instrumentation
to automatically instrument Flask applications with Lumberjack's configuration.
"""
from typing import Any, Callable, Optional, Sequence

from .core import Lumberjack
from .internal_utils.fallback_logger import sdk_logger

try:
    from opentelemetry.instrumentation.flask import FlaskInstrumentor # pyright: ignore[reportMissingTypeStubs]
    OTEL_FLASK_AVAILABLE = True
except ImportError:
    OTEL_FLASK_AVAILABLE = False  # pyright: ignore[reportConstantRedefinition]
    FlaskInstrumentor = None


class LumberjackFlask:
    """Thin wrapper around OpenTelemetry Flask instrumentation."""

    @staticmethod
    def instrument(
        app: Any,
        request_hook: Optional[Callable[..., Any]] = None,
        response_hook: Optional[Callable[..., Any]] = None,
        tracer_provider: Optional[Any] = None,
        excluded_urls: Optional[Sequence[str]] = None,
        enable_commenter: bool = True,
        commenter_options: Optional[dict[str, Any]] = None,
        meter_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> None:
        """Instrument a Flask application using OpenTelemetry.

        Args:
            app: The Flask application to instrument
            request_hook: Optional callback for request processing
            response_hook: Optional callback for response processing
            tracer_provider: Optional tracer provider (uses global if not provided)
            excluded_urls: Optional list of URLs to exclude from tracing
            enable_commenter: Enable SQL commenter (default: True)
            commenter_options: Options for SQL commenter
            meter_provider: Optional meter provider for metrics
            **kwargs: Additional arguments passed to OpenTelemetry Flask instrumentation
        
        Note:
            If tracer_provider is not provided, the global tracer provider
            set up by Lumberjack core will be used automatically.
        """
        if not app:
            sdk_logger.error("LumberjackFlask: No app provided")
            return

        if getattr(app, "_lumberjack_instrumented", False):
            sdk_logger.debug("LumberjackFlask: Application already instrumented")
            return

        try:
            if not OTEL_FLASK_AVAILABLE:
                sdk_logger.error(
                    "LumberjackFlask: OpenTelemetry Flask instrumentation not available. "
                    "Install with: pip install opentelemetry-instrumentation-flask"
                )
                return

            # Ensure Lumberjack is initialized (which sets up OpenTelemetry)
            lumberjack = Lumberjack()
            if not lumberjack.tracer:
                sdk_logger.warning(
                    "LumberjackFlask: No tracer available, instrumentation may not work"
                )

            # Use OpenTelemetry's Flask instrumentation
            if FlaskInstrumentor:
                # Build kwargs for instrument_app
                instrument_kwargs: dict[str, Any] = {}
                if request_hook is not None:
                    instrument_kwargs["request_hook"] = request_hook
                if response_hook is not None:
                    instrument_kwargs["response_hook"] = response_hook
                if tracer_provider is not None:
                    instrument_kwargs["tracer_provider"] = tracer_provider
                if excluded_urls is not None:
                    instrument_kwargs["excluded_urls"] = excluded_urls
                if enable_commenter:
                    instrument_kwargs["enable_commenter"] = enable_commenter
                if commenter_options is not None:
                    instrument_kwargs["commenter_options"] = commenter_options
                if meter_provider is not None:
                    instrument_kwargs["meter_provider"] = meter_provider
                
                # Add any additional kwargs
                instrument_kwargs.update(kwargs)
                
                FlaskInstrumentor().instrument_app(app, **instrument_kwargs) # pyright: ignore[reportUnknownMemberType]
            
            sdk_logger.info("LumberjackFlask: Flask application instrumented with OpenTelemetry")
            app._lumberjack_instrumented = True

        except Exception as e:
            sdk_logger.error(f"LumberjackFlask: Error instrumenting Flask app: {e}")

    @staticmethod
    def uninstrument() -> None:
        """Uninstrument Flask applications."""
        try:
            if not OTEL_FLASK_AVAILABLE:
                sdk_logger.warning(
                    "LumberjackFlask: OpenTelemetry Flask instrumentation not available"
                )
                return
                
            if FlaskInstrumentor:
                FlaskInstrumentor().uninstrument() # pyright: ignore[reportUnknownMemberType]
            sdk_logger.info("LumberjackFlask: Flask instrumentation removed")
        except Exception as e:
            sdk_logger.error(f"LumberjackFlask: Error uninstrumenting Flask: {e}")