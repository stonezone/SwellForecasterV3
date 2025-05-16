"""
Logging configuration for SwellForecaster V3.

Implements three-tier logging:
- INFO: Basic operational logging
- VERBOSE: Detailed logging
- DEBUG: Full API request/response logging
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional


# Custom VERBOSE level between INFO and DEBUG
VERBOSE = 15
logging.addLevelName(VERBOSE, "VERBOSE")


class VerboseLogger(logging.Logger):
    """Logger with VERBOSE level support."""
    
    def verbose(self, message, *args, **kwargs):
        """Log a message with severity 'VERBOSE'."""
        if self.isEnabledFor(VERBOSE):
            self._log(VERBOSE, message, args, **kwargs)


# Set the custom logger class
logging.setLoggerClass(VerboseLogger)


def setup_logging(config):
    """
    Set up logging based on configuration.
    
    Args:
        config: ConfigParser object with logging settings
    """
    # Get log level from config
    log_level_str = config.get('general', 'log_level', fallback='INFO')
    if log_level_str == 'VERBOSE':
        log_level = VERBOSE
    else:
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    log_filename = os.path.join(log_dir, f"swellforecaster_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_filename,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(console_formatter)
    root_logger.addHandler(file_handler)
    
    # API debug logger for DEBUG level only
    if log_level == logging.DEBUG:
        api_logger = logging.getLogger('openai_api')
        api_logger.setLevel(logging.DEBUG)
        api_handler = logging.FileHandler(os.path.join(log_dir, 'api_debug.log'))
        api_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        api_handler.setFormatter(api_formatter)
        api_logger.addHandler(api_handler)
        api_logger.propagate = False  # Don't propagate to root logger


def get_logger(name: str) -> VerboseLogger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically module name)
        
    Returns:
        VerboseLogger instance
    """
    return logging.getLogger(name)


def log_api_request(method: str, url: str, headers: dict, body: Optional[str] = None):
    """
    Log API request details (DEBUG level only).
    
    Args:
        method: HTTP method
        url: Request URL
        headers: Request headers
        body: Request body (optional)
    """
    api_logger = logging.getLogger('openai_api')
    if api_logger.isEnabledFor(logging.DEBUG):
        api_logger.debug(f"REQUEST: {method} {url}")
        api_logger.debug(f"HEADERS: {headers}")
        if body:
            api_logger.debug(f"BODY: {body}")


def log_api_response(status_code: int, headers: dict, body: str, duration: float):
    """
    Log API response details (DEBUG level only).
    
    Args:
        status_code: HTTP status code
        headers: Response headers
        body: Response body
        duration: Request duration in seconds
    """
    api_logger = logging.getLogger('openai_api')
    if api_logger.isEnabledFor(logging.DEBUG):
        api_logger.debug(f"RESPONSE: {status_code} ({duration:.3f}s)")
        api_logger.debug(f"HEADERS: {headers}")
        api_logger.debug(f"BODY: {body}")


# Example usage with OpenAI client monkey-patching
def patch_openai_client(client):
    """
    Monkey-patch OpenAI client to log all API calls.
    
    Args:
        client: OpenAI client instance
    """
    if logging.getLogger().level == logging.DEBUG:
        import time
        import json
        
        # Store the original method
        original_request = client._client.request
        
        def logging_request(method, url, **kwargs):
            """Wrapped request method with logging."""
            start_time = time.time()
            
            # Log request
            headers = kwargs.get('headers', {})
            body = kwargs.get('json', kwargs.get('data'))
            log_api_request(method, url, headers, json.dumps(body) if body else None)
            
            # Make the actual request
            response = original_request(method, url, **kwargs)
            
            # Log response
            duration = time.time() - start_time
            try:
                response_body = response.json()
                body_str = json.dumps(response_body)
            except:
                body_str = response.text
                
            log_api_response(
                response.status_code,
                dict(response.headers),
                body_str,
                duration
            )
            
            return response
        
        # Replace the method
        client._client.request = logging_request