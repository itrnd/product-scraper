import functools
import random
import time
import logging
import json
import sys
from datetime import datetime


CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "C$": "CAD",
}


def retry(retries=3, backoff_factor=0.5, error_types=(Exception,)):
    """Retry decorator with exponential backoff for handling transient errors.

    Args:
        retries (int): Maximum number of retries. Default is 3.
        backoff_factor (float): Factor to determine the exponential backoff time. Default is 0.5.
        error_types (tuple): Types of exceptions to catch and retry. Default is (Exception,).

    Returns:
        The decorated function.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = None
            if args and hasattr(args[0], "logger"):
                logger = args[0].logger

            if logger is None:
                logger = logging.getLogger("retry")
                if not logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)
                    logger.setLevel(logging.INFO)

            retry_count = 0
            while retry_count < retries:
                try:
                    return func(*args, **kwargs)
                except error_types as e:
                    retry_count += 1
                    if retry_count >= retries:
                        logger.error(
                            f"Failed after {retries} retries",
                            extra={
                                "function": func.__name__,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "retries": retries,
                            },
                        )
                        raise

                    backoff_time = backoff_factor * (2 ** (retry_count - 1))
                    jitter = random.uniform(0, 0.1 * backoff_time)
                    sleep_time = backoff_time + jitter

                    logger.warning(
                        f"Retry attempt {retry_count}/{retries}",
                        extra={
                            "function": func.__name__,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "retry_count": retry_count,
                            "max_retries": retries,
                            "sleep_time": round(sleep_time, 2),
                        },
                    )
                    time.sleep(sleep_time)

        return wrapper

    return decorator


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs log records as JSON."""

    def format(self, record):
        """Format the log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            str: The formatted log record as a JSON string.
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        standard_attrs = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "taskName",
            "thread",
            "threadName",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data)


def setup_logger(config):
    """Set up the logger based on the configuration.

    Args:
        config (dict): The configuration dictionary.

    Returns:
        logging.Logger: The configured logger.
    """
    log_level = getattr(logging, config.get("level", "INFO"))
    log_format = config.get("format", "")
    log_file = config.get("file")
    log_console = config.get("console", True)

    logger = logging.getLogger("product_scraper")
    logger.setLevel(log_level)

    formatter: logging.Formatter
    if log_format.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if log_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
