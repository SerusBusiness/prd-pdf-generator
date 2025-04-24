"""
Logging setup module for PRD Generator.
Provides consistent logging configuration across the application.
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

def setup_logging(log_level=logging.INFO):
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: The logging level to use (default: logging.INFO)
    
    Returns:
        Logger: Configured root logger
    """
    # Create logs directory if it doesn't exist
    base_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Configure timestamp for log filename
    timestamp = datetime.now().strftime('%Y%m%d')
    log_file = logs_dir / f"prd_generator_{timestamp}.log"
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Configure file handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(name=None):
    """
    Get a logger with the given name. If no name is provided, returns the root logger.
    
    Args:
        name: Name for the logger (usually the module name)
        
    Returns:
        Logger: The requested logger
    """
    if name:
        return logging.getLogger(name)
    return logging.getLogger()