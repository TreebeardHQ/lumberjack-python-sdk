"""
Django instrumentation for Lumberjack using OpenTelemetry.

This module provides a thin wrapper around OpenTelemetry's Django instrumentation
to automatically instrument Django applications with Lumberjack's configuration.
"""
from typing import Any, Dict

from .core import Lumberjack
from .internal_utils.fallback_logger import sdk_logger

try:
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    OTEL_DJANGO_AVAILABLE = True
except ImportError:
    OTEL_DJANGO_AVAILABLE = False
    DjangoInstrumentor = None

try:
    from django.conf import settings as django_settings
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    django_settings = None


class LumberjackDjango:
    """Thin wrapper around OpenTelemetry Django instrumentation."""

    @staticmethod
    def init(**kwargs: Any) -> None:
        """Initialize Lumberjack with Django-specific configuration.

        This method should be called in your Django settings or AppConfig.
        It accepts the same parameters as Lumberjack.init() and automatically
        sets up OpenTelemetry Django instrumentation.

        Args:
            **kwargs: Configuration options passed to Lumberjack.init()
        """
        # Get Django settings if available
        if DJANGO_AVAILABLE and django_settings:
            # Merge Django settings with kwargs
            django_config: Dict[str, Any] = {}

            # Map Django settings to Lumberjack config
            if hasattr(django_settings, 'LUMBERJACK_API_KEY'):
                django_config['api_key'] = django_settings.LUMBERJACK_API_KEY
            if hasattr(django_settings, 'LUMBERJACK_PROJECT_NAME'):
                django_config['project_name'] = django_settings.LUMBERJACK_PROJECT_NAME
            if hasattr(django_settings, 'LUMBERJACK_ENDPOINT'):
                django_config['endpoint'] = django_settings.LUMBERJACK_ENDPOINT
            if hasattr(django_settings, 'LUMBERJACK_LOG_TO_STDOUT'):
                django_config['log_to_stdout'] = django_settings.LUMBERJACK_LOG_TO_STDOUT
            if hasattr(django_settings, 'LUMBERJACK_CAPTURE_STDOUT'):
                django_config['capture_stdout'] = django_settings.LUMBERJACK_CAPTURE_STDOUT
            if hasattr(django_settings, 'LUMBERJACK_CAPTURE_PYTHON_LOGGER'):
                django_config['capture_python_logger'] = django_settings.LUMBERJACK_CAPTURE_PYTHON_LOGGER
            if hasattr(django_settings, 'LUMBERJACK_DEBUG_MODE'):
                django_config['debug_mode'] = django_settings.LUMBERJACK_DEBUG_MODE
            if hasattr(django_settings, 'LUMBERJACK_BATCH_SIZE'):
                django_config['batch_size'] = django_settings.LUMBERJACK_BATCH_SIZE
            if hasattr(django_settings, 'LUMBERJACK_BATCH_AGE'):
                django_config['batch_age'] = django_settings.LUMBERJACK_BATCH_AGE

            # Kwargs override Django settings
            config = {**django_config, **kwargs}
        else:
            # Django not available, just use kwargs
            config = kwargs

        # Initialize Lumberjack (which sets up OpenTelemetry)
        Lumberjack.init(**config)
        sdk_logger.info("Lumberjack initialized for Django")

        # Set up OpenTelemetry Django instrumentation
        LumberjackDjango.instrument()

    @staticmethod
    def instrument(**kwargs: Any) -> None:
        """Instrument Django using OpenTelemetry.

        Args:
            **kwargs: Additional arguments passed to OpenTelemetry Django instrumentation
        """
        try:
            if not OTEL_DJANGO_AVAILABLE:
                sdk_logger.error(
                    "LumberjackDjango: OpenTelemetry Django instrumentation not available. "
                    "Install with: pip install opentelemetry-instrumentation-django"
                )
                return

            # Ensure Lumberjack is initialized (which sets up OpenTelemetry)
            lumberjack = Lumberjack()
            if not lumberjack.tracer:
                sdk_logger.warning(
                    "LumberjackDjango: No tracer available, instrumentation may not work"
                )

            # Use OpenTelemetry's Django instrumentation
            DjangoInstrumentor().instrument(**kwargs)
            
            sdk_logger.info("LumberjackDjango: Django instrumented with OpenTelemetry")

        except Exception as e:
            sdk_logger.error(f"LumberjackDjango: Error instrumenting Django: {e}")

    @staticmethod
    def uninstrument() -> None:
        """Uninstrument Django applications."""
        try:
            if not OTEL_DJANGO_AVAILABLE:
                sdk_logger.warning(
                    "LumberjackDjango: OpenTelemetry Django instrumentation not available"
                )
                return
                
            DjangoInstrumentor().uninstrument()
            sdk_logger.info("LumberjackDjango: Django instrumentation removed")
        except Exception as e:
            sdk_logger.error(f"LumberjackDjango: Error uninstrumenting Django: {e}")

# Note: No middleware needed! OpenTelemetry Django instrumentation
# works automatically when DjangoInstrumentor().instrument() is called.
# Just call LumberjackDjango.init() in your Django settings.