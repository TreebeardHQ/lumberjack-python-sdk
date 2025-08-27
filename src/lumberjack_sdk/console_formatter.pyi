import logging

class LumberjackConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str: ...
