import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logging(log_file: str = 'polarise.log', level: str = 'INFO'):
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get the root logger
    root_logger = logging.getLogger()

    # Prevent adding duplicate handlers
    if not root_logger.handlers:
        # Setup file handler
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, log_file),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)

        # Setup console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # Add handlers to root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    # Set the logging level
    root_logger.setLevel(level.upper())
    
    return root_logger
