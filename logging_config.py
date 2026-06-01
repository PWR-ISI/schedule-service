"""
Logging configuration with CloudWatch and Sentry support.
"""
import json
import logging
import logging.handlers
import os
from pythonjsonlogger import jsonlogger
from django.conf import settings


class CloudWatchFormatter(logging.Formatter):
    """Format logs for CloudWatch with structured fields."""

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        return json.dumps(log_data)


def configure_logging():
    """Configure logging for the application."""

    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "json")  # json or text

    # Create formatters
    if log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s %(module)s %(funcName)s %(lineno)d"
        )
        cloudwatch_formatter = formatter
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        cloudwatch_formatter = CloudWatchFormatter()

    # Console handler (always present)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # File handler for production
    if not settings.DEBUG:
        file_handler = logging.handlers.RotatingFileHandler(
            filename="/var/log/app/application.log",
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(cloudwatch_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    if not settings.DEBUG:
        root_logger.addHandler(file_handler)

    # Configure Django loggers
    django_logger = logging.getLogger("django")
    django_logger.setLevel(log_level)

    # Configure application loggers
    app_logger = logging.getLogger("apps")
    app_logger.setLevel(log_level)

    # Configure database logger
    db_logger = logging.getLogger("django.db.backends")
    if settings.DEBUG:
        db_logger.setLevel(logging.DEBUG)
    else:
        db_logger.setLevel(logging.WARNING)

    # Sentry integration (if configured)
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn and not settings.DEBUG:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.django import DjangoIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[
                    DjangoIntegration(),
                    LoggingIntegration(
                        level=logging.INFO,
                        event_level=logging.ERROR,
                    ),
                ],
                traces_sample_rate=0.1,
                environment=os.getenv("ENVIRONMENT", "production"),
                debug=False,
            )
        except ImportError:
            root_logger.warning("Sentry SDK not installed, skipping Sentry integration")


# Configure on import
configure_logging()
