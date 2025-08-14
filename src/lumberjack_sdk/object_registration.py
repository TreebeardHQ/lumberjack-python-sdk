"""
Object registration module for Lumberjack SDK.

This module handles object registration, batching, and export functionality
that is separate from OpenTelemetry logging and tracing.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from opentelemetry import trace

from .batch import ObjectBatch
from .config import LumberjackConfig
from .object_exporter import ObjectExporter
from .internal_utils.fallback_logger import sdk_logger


class ObjectRegistration:
    """Manages object registration, batching, and export for Lumberjack."""
    
    _exporter: Optional[ObjectExporter]
    
    def __init__(self, config: LumberjackConfig):
        """Initialize object registration with configuration.
        
        Args:
            config: Lumberjack configuration object
        """
        self._config = config
        self._using_fallback = config.is_fallback_mode()
        
        # Initialize object batch
        self._object_batch = ObjectBatch(
            max_size=config.batch_size, 
            max_age=config.batch_age
        )
        
        # Initialize exporter if not in fallback mode
        if not self._using_fallback:
            self._exporter = ObjectExporter(
                api_key=config.api_key or "",
                objects_endpoint=config.objects_endpoint or "",
                project_name=config.project_name
            )
        else:
            self._exporter = None
    
    def register_object(self, obj: Any = None, **kwargs: Any) -> None:
        """Register objects for tracking in Lumberjack.

        Args:
            obj: Object to register (optional, can be dict or object with attributes)
            **kwargs: Object data to register as keyword arguments. Should include an 'id' field.
        """
        # Handle single object registration
        if obj is not None:
            data_to_register = obj
            formatted_obj = self._format_object(data_to_register)
            if formatted_obj is not None:
                self._attach_to_context(formatted_obj)
                if not self._using_fallback and self._object_batch.add(formatted_obj):
                    self.flush_objects()
            return

        # Handle kwargs registration - register each key-value pair
        if not kwargs:
            sdk_logger.warning("No object or kwargs provided for registration")
            return

        for key, value in kwargs.items():
            if not isinstance(value, dict):
                # Add the key as an attribute to help with naming
                value._kwarg_key = key

            formatted_obj = self._format_object(value)
            if formatted_obj is not None:
                self._attach_to_context(formatted_obj)
                if not self._using_fallback and self._object_batch.add(formatted_obj):
                    self.flush_objects()

    def _format_object(self, obj_data: Union[Dict[str, Any], Any]) -> Optional[Dict[str, Any]]:
        """Format and validate an object for registration.

        Args:
            obj_data: Raw object data (dict or object with attributes)

        Returns:
            Formatted object or None if validation fails
        """
        # Convert object to dict if needed
        if not isinstance(obj_data, dict):
            # Get class name if it's a class instance
            class_name = obj_data.__class__.__name__ if hasattr(
                obj_data, '__class__') else None

            # Convert object attributes to dict
            try:
                if hasattr(obj_data, '__dict__'):
                    obj_dict = obj_data.__dict__.copy()
                else:
                    # Try to convert using vars()
                    obj_dict = vars(obj_data)
            except TypeError:
                sdk_logger.warning(
                    "Cannot convert object to dictionary for registration")
                return None
        else:
            obj_dict = obj_data.copy()
            class_name = None

        # Check for ID field and warn if missing
        if 'id' not in obj_dict:
            sdk_logger.warning(
                "Object registered without 'id' field. This may cause issues with object tracking.")
            return None

        name = None
        if class_name:
            name = class_name.lower()
        if not name and hasattr(obj_data, '_kwarg_key'):
            name = obj_data._kwarg_key.lower()

        obj_id = obj_dict.get('id')

        # Validate and filter fields
        fields = {}
        for key, value in obj_dict.items():
            if key in ['name', 'id']:
                continue

            field_value = self._format_field(key, value)
            if field_value:
                fields[key] = field_value

        return {
            'name': name,
            'id': obj_id,
            'fields': fields
        }

    def _format_field(self, key: str, value: Any) -> Any:
        """Format and validate a field for object registration.

        Args:
            key: Field name
            value: Field value

        Returns:
            Formatted field value if valid for registration, None otherwise
        """
        # Check for numbers
        if isinstance(value, (int, float)):
            return value

        # Check for booleans
        if isinstance(value, bool):
            return value

        # Check for dates
        if isinstance(value, datetime):
            return value.isoformat()

        # Check for searchable strings (under 1024 chars)
        if isinstance(value, str):
            if len(value) <= 1024:
                # Simple heuristic: if it looks like metadata (short, no newlines)
                # rather than body text
                valid = '\n' not in value and '\r' not in value
                if valid:
                    return value

        return None

    def _attach_to_context(self, formatted_obj: Dict[str, Any]) -> None:
        """Attach the registered object to the current trace context.

        Args:
            formatted_obj: The formatted object with name, id, and fields
        """
        object_name = formatted_obj.get('name', '')
        object_id = formatted_obj.get('id', '')

        if object_name and object_id:
            # Create context key as {name}_id
            context_key = f"{object_name}_id"

            # Object context now handled via OpenTelemetry span attributes
            span = trace.get_current_span()
            if span:
                span.set_attribute(f"lb_register.{context_key}", object_id)

            sdk_logger.debug(
                f"Attached object to context: {context_key} = {object_id}")

    def flush_objects(self) -> int:
        """Flush all pending object registrations.

        Returns:
            Number of objects flushed
        """
        objects = self._object_batch.get_objects()
        count = len(objects)
        if objects and self._exporter:
            # Pass None as callback since object registration doesn't handle config updates
            self._exporter.send_objects_async(
                objects, getattr(self._config, '_config_version', None), 
                None
            )

        return count
    
    def get_object_batch(self) -> ObjectBatch:
        """Get the object batch instance.
        
        Returns:
            The ObjectBatch instance
        """
        return self._object_batch
    
    def update_config(self, config: LumberjackConfig) -> None:
        """Update the configuration.
        
        Args:
            config: New configuration
        """
        self._config = config
        self._using_fallback = config.is_fallback_mode()
        
        # Update batch settings if needed
        if hasattr(self._object_batch, 'max_size'):
            self._object_batch.max_size = config.batch_size
        if hasattr(self._object_batch, 'max_age'):
            self._object_batch.max_age = config.batch_age
    
    def update_exporter(self, exporter: Optional[ObjectExporter]) -> None:
        """Update the exporter.
        
        Args:
            exporter: New exporter instance
        """
        self._exporter = exporter
    
    def shutdown(self) -> None:
        """Shutdown object registration and cleanup resources."""
        # Flush any remaining objects
        self.flush_objects()
        
        # Stop the exporter worker if it exists
        if self._exporter:
            self._exporter.stop_worker()
            self._exporter = None
        
        sdk_logger.debug("Object registration shutdown complete")