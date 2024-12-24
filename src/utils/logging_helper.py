# logging_helper.py

import time
import logging
import os
from datetime import datetime, timedelta

def setup_logging(log_file='logs/main.log', level=logging.INFO) -> logging.Logger:
    """
    Sets up logging to file and console with consistent formatting.

    Args:
        log_file (str): The log file path.
        level (int): The logging level (e.g., logging.INFO).
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    # Clear any existing handlers
    logging.getLogger().handlers = []

    # Create the logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Define the ISO8601 formatter for both file and stream logs
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(module)s]: %(message)s', 
        datefmt='%Y-%m-%dT%H:%M:%SZ'
    )

    # Use UTC time for logs
    logging.Formatter.converter = time.gmtime  # Ensure UTC time

    # File handler (for log file output)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Stream handler (for console output)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
