import logging

DEFAULT_DATE_FORMAT = '%y%m%d %H:%M:%S'
DEFAULT_LOG_FORMAT = '[%(levelname)1.1s %(asctime)s %(process)d %(module)s:%(lineno)d] %(message)s'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False
_null_handler = logging.NullHandler()
logger.addHandler(_null_handler)


def set_handler(handler: logging.Handler):
    """Set the handler of the logger.

    Args:
        handler (logging.Handler): The handler to be set.
    """
    logger.handlers = [handler]


def setup_logger(
    date_format: str = DEFAULT_DATE_FORMAT,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_level: int = logging.DEBUG
):
    """Setup a console logger.

    Args:
        date_format (str): The date format of the logger.
        log_format (str): The log format of the logger.
        log_level (int): The log level of the logger.
    """
    logger.removeHandler(_null_handler)
    if logger.handlers:
        for handler in logger.handlers:
            _setup_handler(handler, date_format, log_format, log_level)
    else:
        handler = logging.StreamHandler()
        _setup_handler(handler, date_format, log_format, log_level)
        logger.addHandler(handler)


def _setup_handler(
    handler: logging.Handler,
    date_format: str,
    log_format: str,
    log_level: int = logging.DEBUG
):
    """Setup a handler for the logger.

    Args:
        handler (logging.Handler): The handler to be setup.
        date_format (str): The date format of the handler.
        log_format (str): The log format of the handler.
        log_level (int): The log level of the handler.
    """
    handler.setLevel(log_level)
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    handler.setFormatter(formatter)
