import logging
from enum import Enum

class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class AppLogger:
    """
    A simplified centralized logger class for the Assistant application.
    Provides both console and file logging with fixed configuration.
    """
    
    _instance = None
    _logger = None
    ENABLE_LOGS = False  # Set to False to disable all logging output
    
    def __new__(cls):
        """Singleton pattern to ensure only one logger instance"""
        if cls._instance is None:
            cls._instance = super(AppLogger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """Initialize the logging configuration with fixed settings"""
        app_name = "Assistant"
        
        # Fixed log format for consistency
        log_format = "%(asctime)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s"
        time_format = "%H:%M:%S"
         
        # Create logger - set to DEBUG level to capture everything
        self._logger = logging.getLogger(app_name)
        self._logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if self._logger.handlers:
            return

        # Single formatter for both console and file
        formatter = logging.Formatter(
            log_format,
            datefmt=time_format
        )

        # Console handler - always show logs
        # For EXE builds, this will output to the allocated console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)  # Show everything in console
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)       
    
    def log(self, level: LogLevel, message: str, *args, **kwargs):
        """
        General log method that accepts LogLevel enum
        
        Args:
            level (LogLevel): The log level
            message (str): The message to log
            *args: Additional arguments for string formatting
            **kwargs: Additional keyword arguments
        """
        if self.ENABLE_LOGS:
            self._logger.log(level.value, message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message"""
        if self.ENABLE_LOGS:
            self._logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message"""
        if self.ENABLE_LOGS:
            self._logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message"""
        if self.ENABLE_LOGS:
            self._logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message"""
        if self.ENABLE_LOGS:
            self._logger.error(message, *args, **kwargs)
        
    def critical(self, message: str, *args, **kwargs):
        """Log critical message"""
        if self.ENABLE_LOGS:
            self._logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log error message with full exception traceback and details"""
        if self.ENABLE_LOGS:
            self._logger.exception(message, *args, **kwargs)


# Global logger instance for easy import
logger = AppLogger()
