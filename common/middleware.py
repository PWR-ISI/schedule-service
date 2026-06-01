"""
Middleware for monitoring, logging, and metrics collection.
"""
import logging
import time
import uuid
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Log all requests with request ID, duration, and response status."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate request ID
        request.request_id = str(uuid.uuid4())
        request.start_time = time.time()

        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "user_id": getattr(request, "user_id", None),
            },
        )

        response = self.get_response(request)

        # Calculate duration
        duration = time.time() - request.start_time

        # Log response
        logger.info(
            "Request completed",
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": int(duration * 1000),
                "user_id": getattr(request, "user_id", None),
            },
        )

        # Add request ID to response headers for tracing
        response["X-Request-ID"] = request.request_id

        # Log slow requests
        if duration > 1.0:  # > 1 second
            logger.warning(
                "Slow request detected",
                extra={
                    "request_id": request.request_id,
                    "method": request.method,
                    "path": request.path,
                    "duration_ms": int(duration * 1000),
                },
            )

        return response


class MetricsMiddleware:
    """Collect metrics for monitoring."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.request_count = {}
        self.error_count = {}

    def __call__(self, request):
        path = request.path
        method = request.method

        # Track request count
        key = f"{method} {path}"
        self.request_count[key] = self.request_count.get(key, 0) + 1

        response = self.get_response(request)

        # Track errors
        if response.status_code >= 400:
            error_key = f"{method} {path} {response.status_code}"
            self.error_count[error_key] = self.error_count.get(error_key, 0) + 1

        return response


class UserContextMiddleware:
    """Add user context to logs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add user_id to logger context
        user_id = getattr(request, "user_id", None)
        if user_id:
            logger.info(
                "User request",
                extra={"user_id": user_id, "path": request.path},
            )

        response = self.get_response(request)
        return response


class ErrorHandlingMiddleware:
    """Catch unhandled errors and log them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception as exc:
            request_id = getattr(request, "request_id", "unknown")
            logger.exception(
                "Unhandled exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.path,
                    "user_id": getattr(request, "user_id", None),
                },
            )
            raise

        return response
