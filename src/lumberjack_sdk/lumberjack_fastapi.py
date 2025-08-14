"""
FastAPI instrumentation for Lumberjack using OpenTelemetry.

This module provides a thin wrapper around OpenTelemetry's FastAPI instrumentation
to automatically instrument FastAPI applications with Lumberjack's configuration.
"""
from typing import Any, Callable, Optional, Sequence

from .core import Lumberjack
from .internal_utils.fallback_logger import sdk_logger

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    OTEL_FASTAPI_AVAILABLE = True
except ImportError:
    OTEL_FASTAPI_AVAILABLE = False
    FastAPIInstrumentor = None


class LumberjackFastAPI:
    """Thin wrapper around OpenTelemetry FastAPI instrumentation."""

    @staticmethod
    def instrument(
        app: Any,
        server_request_hook: Optional[Callable[..., Any]] = None,
        client_request_hook: Optional[Callable[..., Any]] = None,
        client_response_hook: Optional[Callable[..., Any]] = None,
        tracer_provider: Optional[Any] = None,
        excluded_urls: Optional[Sequence[str]] = None,
        meter_provider: Optional[Any] = None,
        **kwargs: Any
    ) -> None:
        """Instrument a FastAPI application using OpenTelemetry.

        Args:
            app: The FastAPI application to instrument
            server_request_hook: Optional callback for server request processing
            client_request_hook: Optional callback for client request processing
            client_response_hook: Optional callback for client response processing
            tracer_provider: Optional tracer provider (uses global if not provided)
            excluded_urls: Optional list of URLs to exclude from tracing
            meter_provider: Optional meter provider for metrics
            **kwargs: Additional arguments passed to OpenTelemetry FastAPI instrumentation
        
        Note:
            If tracer_provider is not provided, the global tracer provider
            set up by Lumberjack core will be used automatically.
        """
        if not app:
            sdk_logger.error("LumberjackFastAPI: No app provided")
            return

        if getattr(app, "_lumberjack_instrumented", False):
            sdk_logger.debug("LumberjackFastAPI: Application already instrumented")
            return

        try:
            if not OTEL_FASTAPI_AVAILABLE:
                sdk_logger.error(
                    "LumberjackFastAPI: OpenTelemetry FastAPI instrumentation not available. "
                    "Install with: pip install opentelemetry-instrumentation-fastapi"
                )
                return

            # Ensure Lumberjack is initialized (which sets up OpenTelemetry)
            lumberjack = Lumberjack()
            if not lumberjack.tracer:
                sdk_logger.warning(
                    "LumberjackFastAPI: No tracer available, instrumentation may not work"
                )

            # Use OpenTelemetry's FastAPI instrumentation
            if FastAPIInstrumentor:
                # Build kwargs for instrument_app
                instrument_kwargs: dict[str, Any] = {}
                if server_request_hook is not None:
                    instrument_kwargs["server_request_hook"] = server_request_hook
                if client_request_hook is not None:
                    instrument_kwargs["client_request_hook"] = client_request_hook
                if client_response_hook is not None:
                    instrument_kwargs["client_response_hook"] = client_response_hook
                if tracer_provider is not None:
                    instrument_kwargs["tracer_provider"] = tracer_provider
                if excluded_urls is not None:
                    instrument_kwargs["excluded_urls"] = excluded_urls
                if meter_provider is not None:
                    instrument_kwargs["meter_provider"] = meter_provider
                
                # Add any additional kwargs
                instrument_kwargs.update(kwargs)
                
                FastAPIInstrumentor().instrument_app(app, **instrument_kwargs)
            
            sdk_logger.info("LumberjackFastAPI: FastAPI application instrumented with OpenTelemetry")
            app._lumberjack_instrumented = True

        except Exception as e:
            sdk_logger.error(f"LumberjackFastAPI: Error instrumenting FastAPI app: {e}")

    @staticmethod
    def uninstrument() -> None:
        """Uninstrument FastAPI applications."""
        try:
            if not OTEL_FASTAPI_AVAILABLE:
                sdk_logger.warning(
                    "LumberjackFastAPI: OpenTelemetry FastAPI instrumentation not available"
                )
                return
                
            if FastAPIInstrumentor:
                FastAPIInstrumentor().uninstrument()
            sdk_logger.info("LumberjackFastAPI: FastAPI instrumentation removed")
        except Exception as e:
            sdk_logger.error(f"LumberjackFastAPI: Error uninstrumenting FastAPI: {e}")

# Note: No middleware needed! OpenTelemetry FastAPI instrumentation
# works automatically when FastAPIInstrumentor().instrument_app() is called.
# Just call LumberjackFastAPI.instrument(app) after creating your FastAPI app.