"""
Fallback logger for Lumberjack.
"""
import logging


class FallbackFormatter(logging.Formatter):
    """Custom formatter that uses logger_name from extra if available, otherwise falls back to name."""
    
    def format(self, record):
        # Use logger_name from extra if available, otherwise fall back to the logger's name
        if hasattr(record, 'logger_name') and record.logger_name:
            original_name = record.name
            record.name = record.logger_name
            try:
                result = super().format(record)
            finally:
                # Restore original name
                record.name = original_name
            return result
        else:
            return super().format(record)


fallback_logger = logging.getLogger('lumberjack')
fallback_logger.propagate = False
if not fallback_logger.handlers:
    handler = logging.StreamHandler()
    formatter = FallbackFormatter(
        '%(asctime)s - %(name)s - %(levelname)-7s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    fallback_logger.addHandler(handler)

fallback_logger.setLevel(logging.INFO)


sdk_logger = logging.getLogger('lumberjack.sdk')
sdk_logger.propagate = False
if not sdk_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)-7s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    sdk_logger.addHandler(handler)

sdk_logger.setLevel(logging.INFO)
