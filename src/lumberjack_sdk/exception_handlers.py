"""
Exception handling for Lumberjack.

This module provides exception handlers that integrate with OpenTelemetry
to record exceptions in spans when available, or log them directly.
"""
import asyncio
import sys
import threading
from typing import Any, Optional, Type

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode # type: ignore[attr-defined]

from .internal_utils.fallback_logger import sdk_logger


def _handle_exception(exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: Any) -> None:
    """
    Handle unhandled exceptions in the main thread.
    
    Records the exception to the current span if available, otherwise logs it.
    
    Args:
        exc_type: The type of the exception
        exc_value: The exception instance
        exc_traceback: The traceback object
    """
    try:
        # Try to record exception in current span
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.record_exception(exc_value)
            current_span.set_status(Status(StatusCode.ERROR, str(exc_value)))
            sdk_logger.debug("Recorded exception in OpenTelemetry span")
        else:
            # No active span, log directly
            from .log import Log
            Log.error(
                "Unhandled exception in main thread",
                error=exc_value,
            )
        
        # Call the original exception handler
        original_hook = ExceptionHandlers.get_original_excepthook()
        if original_hook is not None:
            original_hook(exc_type, exc_value, exc_traceback)
            
    except Exception as e:
        sdk_logger.error(f"Error in exception handler: {e}")


def _handle_threading_exception(args: threading.ExceptHookArgs) -> None:
    """
    Handle unhandled exceptions in threads.
    
    Records the exception to the current span if available, otherwise logs it.
    
    Args:
        args: The exception hook arguments containing exception info
    """
    try:
        # Try to record exception in current span
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            if args.exc_value:
                current_span.record_exception(args.exc_value)
                current_span.set_status(Status(StatusCode.ERROR, str(args.exc_value)))
            if args.thread and args.thread.name:
                current_span.set_attribute("thread.name", args.thread.name)
            if args.thread and args.thread.ident is not None:
                current_span.set_attribute("thread.id", args.thread.ident)
            sdk_logger.debug("Recorded thread exception in OpenTelemetry span")
        else:
            # No active span, log directly
            from .log import Log
            Log.error(
                "Unhandled exception in thread",
                thread_name=args.thread.name if args.thread else None,
                thread_id=args.thread.ident if args.thread else None,
                error=args.exc_value,
            )
        
        # Call the original exception handler
        original_hook = ExceptionHandlers.get_original_threading_excepthook()
        if original_hook is not None:
            original_hook(args)
            
    except Exception as e:
        sdk_logger.error(f"Error in threading exception handler: {e}")


def _handle_async_exception(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """
    Handle unhandled exceptions in async contexts.
    
    Records the exception to the current span if available, otherwise logs it.
    
    Args:
        loop: The event loop where the exception occurred
        context: Dictionary containing exception information
    """
    try:
        exception = context.get('exception')
        
        # Try to record exception in current span
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            if exception:
                current_span.record_exception(exception)
                current_span.set_status(Status(StatusCode.ERROR, str(exception)))
            else:
                # No exception object, just record the error message
                message = context.get('message', 'Unknown async error')
                current_span.add_event("async_error", {"message": message})
                current_span.set_status(Status(StatusCode.ERROR, message))
            
            # Add context information
            if context.get('future'):
                current_span.set_attribute("async.future", str(context['future']))
            if context.get('task'):
                current_span.set_attribute("async.task", str(context['task']))
            
            sdk_logger.debug("Recorded async exception in OpenTelemetry span")
        else:
            # No active span, log directly
            from .log import Log
            if exception:
                Log.error(
                    "Unhandled exception in async context",
                    error=exception,
                    future=context.get('future'),
                    task=context.get('task'),
                    async_message=context.get('message'),
                )
            else:
                Log.error(
                    "Error in async context",
                    async_message=context.get('message'),
                    future=context.get('future'),
                    task=context.get('task'),
                )
        
        # Call the original exception handler
        original_handler = ExceptionHandlers.get_original_loop_exception_handler()
        if original_handler is not None:
            original_handler(loop, context)
            
    except Exception as e:
        sdk_logger.error(f"Error in async exception handler: {e}")


class ExceptionHandlers:
    """Manages exception handler registration and cleanup."""
    
    _registered: bool = False
    _original_excepthook: Optional[Any] = None
    _original_threading_excepthook: Optional[Any] = None
    _original_loop_exception_handler: Optional[Any] = None
    
    @classmethod
    def register(cls) -> None:
        """Register all exception handlers."""
        if cls._registered:
            return
            
        # Store original handlers
        cls._original_excepthook = sys.excepthook
        cls._original_threading_excepthook = getattr(threading, 'excepthook', None)
        
        # Register new handlers
        sys.excepthook = _handle_exception
        if hasattr(threading, 'excepthook'):
            threading.excepthook = _handle_threading_exception
        
        # Register async handler for current event loop if available
        try:
            loop = asyncio.get_running_loop()
            cls._original_loop_exception_handler = loop.get_exception_handler()
            loop.set_exception_handler(_handle_async_exception)
        except RuntimeError:
            # No event loop running yet, that's fine
            pass
        
        cls._registered = True
        sdk_logger.debug("Exception handlers registered")
    
    @classmethod
    def unregister(cls) -> None:
        """Restore original exception handlers."""
        if not cls._registered:
            return
            
        # Restore original handlers
        if cls._original_excepthook:
            sys.excepthook = cls._original_excepthook
        
        if cls._original_threading_excepthook and hasattr(threading, 'excepthook'):
            threading.excepthook = cls._original_threading_excepthook
        
        # Restore async handler
        try:
            loop = asyncio.get_running_loop()
            if cls._original_loop_exception_handler:
                loop.set_exception_handler(cls._original_loop_exception_handler)
        except RuntimeError:
            # No event loop running, that's fine
            pass
        
        cls._registered = False
        sdk_logger.debug("Exception handlers unregistered")
    
    @classmethod
    def get_original_excepthook(cls) -> Optional[Any]:
        """Get the original excepthook."""
        return cls._original_excepthook
    
    @classmethod
    def get_original_threading_excepthook(cls) -> Optional[Any]:
        """Get the original threading excepthook."""
        return cls._original_threading_excepthook
    
    @classmethod
    def get_original_loop_exception_handler(cls) -> Optional[Any]:
        """Get the original async loop exception handler."""
        return cls._original_loop_exception_handler