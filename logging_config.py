# logging_config.py
# --- Configuration for application-wide logging ---

import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(app):
    """
    Configures a rotating file logger for the Flask application.
    """
    # Create a logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Define the log file path
    log_file = os.path.join(log_dir, 'scorm_processor.log')

    # Create a rotating file handler.
    # This creates a new log file when the current one reaches 5MB,
    # and it keeps a backup of the last 5 log files.
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5
    )

    # Define the format for the log messages
    # Example: 2023-10-27 10:30:00,500 - INFO - [in /app/app.py:123] - Log message here
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [in %(pathname)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(log_formatter)

    # Set the logging level (e.g., INFO, DEBUG, ERROR)
    file_handler.setLevel(logging.INFO)

    # Add the handler to the Flask app's logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

    # Also log to the console (useful for Docker logs)
    # You can comment this out if you only want file-based logs
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    app.logger.addHandler(console_handler)

    app.logger.info('Logging has been successfully configured.')