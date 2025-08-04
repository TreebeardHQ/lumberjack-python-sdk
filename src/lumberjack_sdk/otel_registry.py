"""
Registry interface for OpenTelemetry integration.

This module provides an interface for the custom OTEL exporters to access
registered objects and attach them to spans.
"""
import threading
from typing import Any, Dict, List, Optional

from .otel_context import OTelLoggingContext
from .internal_utils.fallback_logger import sdk_logger


class OTelObjectRegistry:
    """Registry interface for OTEL exporters to access registered objects."""

    def __init__(self):
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._context_objects: Dict[str, List[str]] = {}  # context_key -> list of object ids
        self._lock = threading.Lock()

    def register_object(self, formatted_obj: Dict[str, Any]) -> None:
        """Register an object in the registry.
        
        Args:
            formatted_obj: Object with 'name', 'id', and 'fields' keys
        """
        with self._lock:
            object_id = formatted_obj.get('id')
            if not object_id:
                return
            
            # Store the object
            self._objects[object_id] = formatted_obj
            
            # Store context association for current trace context
            trace_id = OTelLoggingContext.get_trace_id()
            if trace_id:
                if trace_id not in self._context_objects:
                    self._context_objects[trace_id] = []
                if object_id not in self._context_objects[trace_id]:
                    self._context_objects[trace_id].append(object_id)
            
            sdk_logger.debug(f"Registered object {object_id} in OTEL registry")

    def get_objects_for_context(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all objects associated with the current or specified trace context.
        
        Args:
            trace_id: Optional trace ID. If None, uses current trace ID.
            
        Returns:
            List of registered objects for the context
        """
        if trace_id is None:
            trace_id = OTelLoggingContext.get_trace_id()
        
        if not trace_id:
            return []
        
        with self._lock:
            object_ids = self._context_objects.get(trace_id, [])
            objects = []
            for obj_id in object_ids:
                if obj_id in self._objects:
                    objects.append(self._objects[obj_id])
            return objects

    def get_object_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific object by ID.
        
        Args:
            object_id: The object ID to retrieve
            
        Returns:
            The object if found, None otherwise
        """
        with self._lock:
            return self._objects.get(object_id)

    def get_all_objects(self) -> List[Dict[str, Any]]:
        """Get all registered objects.
        
        Returns:
            List of all registered objects
        """
        with self._lock:
            return list(self._objects.values())

    def clear_context_objects(self, trace_id: Optional[str] = None) -> None:
        """Clear objects associated with a trace context.
        
        Args:
            trace_id: Optional trace ID. If None, uses current trace ID.
        """
        if trace_id is None:
            trace_id = OTelLoggingContext.get_trace_id()
        
        if not trace_id:
            return
        
        with self._lock:
            if trace_id in self._context_objects:
                del self._context_objects[trace_id]

    def attach_to_context(self, formatted_obj: Dict[str, Any]) -> None:
        """Attach a registered object to the current OTEL context.
        
        This method handles both registering the object and setting context
        attributes for backward compatibility.
        
        Args:
            formatted_obj: The formatted object with name, id, and fields
        """
        # Register the object
        self.register_object(formatted_obj)
        
        # Set context attributes for backward compatibility
        object_name = formatted_obj.get('name', '')
        object_id = formatted_obj.get('id', '')
        
        if object_name and object_id:
            # Create context key as {name}_id
            context_key = f"{object_name}_id"
            
            # Set the context value to the object's ID
            OTelLoggingContext.set(context_key, object_id)
            
            # Set span attribute if there's an active span
            current_span = OTelLoggingContext.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute(f"lb_register.{context_key}", object_id)
            
            sdk_logger.debug(f"Attached object to OTEL context: {context_key} = {object_id}")

    def get_context_attributes(self) -> Dict[str, Any]:
        """Get all context attributes for registered objects.
        
        Returns:
            Dictionary of context attributes
        """
        context_data = OTelLoggingContext.get_all()
        
        # Extract object-related context attributes
        object_attrs = {}
        for key, value in context_data.items():
            if key.endswith('_id') and not key.startswith('_'):
                object_attrs[key] = value
        
        return object_attrs

    def cleanup_old_contexts(self, max_age_seconds: int = 3600) -> None:
        """Clean up old trace contexts to prevent memory leaks.
        
        Args:
            max_age_seconds: Maximum age of contexts to keep
        """
        # Note: This is a simplified cleanup. In practice, you might want
        # to track creation times of contexts and clean up based on that.
        with self._lock:
            # For now, just limit the number of contexts
            if len(self._context_objects) > 1000:
                # Remove oldest half (simplified approach)
                contexts_to_remove = list(self._context_objects.keys())[:500]
                for context_id in contexts_to_remove:
                    del self._context_objects[context_id]
                sdk_logger.debug(f"Cleaned up {len(contexts_to_remove)} old trace contexts")


# Global registry instance
_global_registry = OTelObjectRegistry()


def get_global_registry() -> OTelObjectRegistry:
    """Get the global object registry instance.
    
    Returns:
        The global OTelObjectRegistry instance
    """
    return _global_registry