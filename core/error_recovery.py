"""Error handling and recovery utilities for Assistant."""
import traceback
import psutil
from functools import wraps
from typing import Callable, Any, Optional, Type
from .app_logger import logger


class ErrorRecovery:
    """Handles errors and provides recovery mechanisms."""
    
    def __init__(self):
        self.error_count = {}
        self.max_retries = 3
        self.recovery_strategies = {}
    
    def register_recovery_strategy(self, error_type: Type[Exception], strategy: Callable):
        """Register a recovery strategy for a specific error type."""
        self.recovery_strategies[error_type] = strategy
    
    def handle_error(self, error: Exception, context: str = "") -> bool:
        """
        Handle an error with logging and optional recovery.
        
        Returns:
            bool: True if error was handled/recovered, False otherwise
        """
        error_key = f"{context}:{type(error).__name__}"
        self.error_count[error_key] = self.error_count.get(error_key, 0) + 1
        
        logger.error(f"Error in {context}: {error}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        
        # Try recovery strategy if available
        for error_type, strategy in self.recovery_strategies.items():
            if isinstance(error, error_type):
                try:
                    logger.info(f"Attempting recovery for {error_type.__name__}")
                    strategy(error, context)
                    return True
                except Exception as recovery_error:
                    logger.error(f"Recovery strategy failed: {recovery_error}")
                    break
        
        # If too many errors of the same type, suggest restart
        if self.error_count[error_key] >= self.max_retries:
            logger.critical(f"Too many errors of type {error_key}. Consider restarting the application.")
            return False
        
        return False
    
    def retry_on_failure(self, max_retries: int = 3, delay: float = 1.0, 
                        exceptions: tuple = (Exception,)):
        """Decorator to retry function on failure."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            logger.info(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                            if delay > 0:
                                import time
                                time.sleep(delay)
                        else:
                            logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                
                # If we get here, all retries failed
                raise last_exception
            return wrapper
        return decorator
    
    def safe_execute(self, func: Callable, *args, default_return=None, context: str = "", **kwargs) -> Any:
        """
        Safely execute a function with error handling.
        
        Returns:
            Function result on success, default_return on failure
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.handle_error(e, context or func.__name__)
            return default_return
    
    def get_error_summary(self) -> dict:
        """Get a summary of all errors encountered."""
        return self.error_count.copy()


# Recovery strategies
def microphone_recovery_strategy(error: Exception, context: str):
    """Recovery strategy for microphone-related errors."""
    logger.info("Attempting to reinitialize microphone...")
    # Reset global microphone variable in speech recognizer
    try:
        from .app_speech import speech_recognizer
        speech_recognizer._microphone = None
        speech_recognizer._calibrated_at = 0.0
        logger.info("Microphone reset successful")
    except Exception as e:
        logger.warning(f"Could not reset microphone: {e}")


# Global error recovery instance
error_recovery = ErrorRecovery()

# Register default recovery strategies
error_recovery.register_recovery_strategy(OSError, microphone_recovery_strategy)


def handle_critical_error(error: Exception, context: str = ""):
    """Handle critical errors that might require application restart."""
    logger.critical(f"Critical error in {context}: {error}")
    logger.critical(f"Traceback: {traceback.format_exc()}")
    
    # Log system state for debugging
    try:        
        process = psutil.Process()
        logger.critical(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
        logger.critical(f"CPU usage: {process.cpu_percent()}%")
    except Exception:
        pass
    
    # Could add automatic restart logic here if needed
    logger.critical("Application may need to be restarted")


def safe_import(module_name: str, fallback_action: Optional[Callable] = None) -> Any:
    """
    Safely import a module with fallback action.
    
    Args:
        module_name: Name of the module to import
        fallback_action: Optional function to call if import fails
        
    Returns:
        Imported module or None if import failed
    """
    try:
        return __import__(module_name)
    except ImportError as e:
        logger.warning(f"Failed to import {module_name}: {e}")
        if fallback_action:
            fallback_action(e)
        return None
