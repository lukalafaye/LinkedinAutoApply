"""
Logging Configuration - Centralized Logging Setup

This module provides a centralized logging configuration for the LinkedIn bot application.
It sets up formatted console and file logging with appropriate levels and handlers.

Date: 2025
"""

import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str = None, verbose: bool = False) -> logging.Logger:
    """
    Set up logging configuration with console and optional file output.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        verbose: If True, console will show DEBUG messages; if False, only INFO and above
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("linkedin_bot")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler - level depends on verbose flag
    console_handler = logging.StreamHandler(sys.stdout)
    console_level = logging.DEBUG if verbose else logging.INFO
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def configure_verbose_logging(verbose: bool = False):
    """
    Reconfigure the existing logger to enable/disable verbose console output.
    
    Args:
        verbose: If True, console will show DEBUG messages; if False, only INFO and above
    """
    global logger
    
    # Update the logger level to DEBUG if verbose is enabled
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # Find the console handler and update its level
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            console_level = logging.DEBUG if verbose else logging.INFO
            handler.setLevel(console_level)
            break


# Create default logger instance with file output
# Always write detailed logs to log.txt for debugging
logger = setup_logging(log_level="DEBUG", log_file="log.txt", verbose=False)
