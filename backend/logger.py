"""Logging utilities for Avatar RAG."""
import logging
import sys

def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Setup a logger with consistent formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper()))
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def log_info(message: str):
    """Log info message."""
    logger = logging.getLogger(__name__)
    logger.info(message)

def log_error(message: str, exc_info=False):
    """Log error message."""
    logger = logging.getLogger(__name__)
    logger.error(message, exc_info=exc_info)

def log_warning(message: str):
    """Log warning message."""
    logger = logging.getLogger(__name__)
    logger.warning(message)

def log_debug(message: str):
    """Log debug message."""
    logger = logging.getLogger(__name__)
    logger.debug(message)
