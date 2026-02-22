#!/usr/bin/env python3
"""
Enhanced Logging Utilities - Structured logging with contextual information.

Provides utilities for better error tracking, correlation, and debugging
throughout the DailyTrending.info pipeline.
"""

import logging
import time
import functools
import uuid
from typing import Optional, Dict, Any, Callable, Iterator, List
from contextlib import contextmanager
from datetime import datetime


class StructuredLogger:
    """
    Wrapper for standard logger that adds structured context to log messages.

    Usage:
        logger = StructuredLogger("my_module")
        logger.info("Operation completed", extra={"duration_ms": 123, "items_processed": 45})
    """

    def __init__(self, name: str, correlation_id: Optional[str] = None):
        """
        Initialize structured logger.

        Args:
            name: Logger name (usually module name)
            correlation_id: Optional correlation ID for tracking related operations
        """
        self.logger = logging.getLogger(name)
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.context: Dict[str, Any] = {}

    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add correlation ID and context to extra fields.

        Args:
            extra: Optional additional fields

        Returns:
            Combined context dictionary
        """
        combined = {"correlation_id": self.correlation_id, **self.context}
        if extra:
            combined.update(extra)
        return combined

    def set_context(self, **kwargs: Any) -> None:
        """
        Set persistent context fields for all subsequent logs.

        Usage:
            logger.set_context(user_id="123", session_id="abc")
        """
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all persistent context fields."""
        self.context.clear()

    def debug(
        self,
        msg: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log debug message with context."""
        self.logger.debug(msg, extra=self._add_context(extra), exc_info=exc_info)

    def info(
        self,
        msg: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log info message with context."""
        self.logger.info(msg, extra=self._add_context(extra), exc_info=exc_info)

    def warning(
        self,
        msg: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log warning message with context."""
        self.logger.warning(msg, extra=self._add_context(extra), exc_info=exc_info)

    def error(
        self,
        msg: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = True,
    ) -> None:
        """Log error message with context and exception info."""
        self.logger.error(msg, extra=self._add_context(extra), exc_info=exc_info)

    def critical(
        self,
        msg: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = True,
    ) -> None:
        """Log critical message with context and exception info."""
        self.logger.critical(msg, extra=self._add_context(extra), exc_info=exc_info)


@contextmanager
def log_operation(
    logger: StructuredLogger, operation: str, **context: Any
) -> Iterator[Dict[str, Any]]:
    """
    Context manager for logging operations with timing and error handling.

    Usage:
        with log_operation(logger, "fetch_images", source="pexels"):
            # ... operation code ...
            pass

    Args:
        logger: StructuredLogger instance
        operation: Name of the operation
        **context: Additional context fields

    Yields:
        Dict containing operation metadata (duration, success, etc.)
    """
    start_time = time.time()
    operation_id = str(uuid.uuid4())

    metadata = {
        "operation": operation,
        "operation_id": operation_id,
        "start_time": datetime.now().isoformat(),
        **context,
    }

    logger.info(f"Starting operation: {operation}", extra=metadata)

    try:
        yield metadata
        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Completed operation: {operation}",
            extra={**metadata, "duration_ms": round(duration_ms, 2), "success": True},
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        logger.error(
            f"Failed operation: {operation}",
            extra={
                **metadata,
                "duration_ms": round(duration_ms, 2),
                "success": False,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        raise


def log_api_call(
    logger: StructuredLogger,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for logging API calls with enhanced context.

    Usage:
        @log_api_call(logger)
        def fetch_from_api(url, params):
            # ... API call code ...
            return response

    Args:
        logger: StructuredLogger instance

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = func.__name__
            call_id = str(uuid.uuid4())
            start_time = time.time()

            # Extract common parameters
            url = kwargs.get("url", args[0] if args else "unknown")
            params = kwargs.get("params", {})

            logger.debug(
                f"API call starting: {func_name}",
                extra={
                    "function": func_name,
                    "call_id": call_id,
                    "url": url,
                    "params": params,
                },
            )

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"API call succeeded: {func_name}",
                    extra={
                        "function": func_name,
                        "call_id": call_id,
                        "url": url,
                        "duration_ms": round(duration_ms, 2),
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"API call failed: {func_name}",
                    extra={
                        "function": func_name,
                        "call_id": call_id,
                        "url": url,
                        "duration_ms": round(duration_ms, 2),
                        "success": False,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "status_code": getattr(e, "status_code", None),
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_performance_metrics(
    logger: StructuredLogger, metrics: Dict[str, Any]
) -> None:
    """
    Log performance metrics in a structured format.

    Usage:
        log_performance_metrics(logger, {
            'operation': 'pipeline_execution',
            'total_time_seconds': 45.2,
            'trends_collected': 150,
            'images_fetched': 30,
            'cache_hit_rate': 0.75
        })

    Args:
        logger: StructuredLogger instance
        metrics: Dictionary of metric name-value pairs
    """
    logger.info(
        "Performance metrics",
        extra={
            "metric_type": "performance",
            "timestamp": datetime.now().isoformat(),
            **metrics,
        },
    )


def log_quality_metrics(logger: StructuredLogger, metrics: Dict[str, Any]) -> None:
    """
    Log quality metrics in a structured format.

    Usage:
        log_quality_metrics(logger, {
            'operation': 'trend_collection',
            'total_trends': 150,
            'fresh_trends': 120,
            'freshness_ratio': 0.8,
            'deduplication_rate': 0.15
        })

    Args:
        logger: StructuredLogger instance
        metrics: Dictionary of metric name-value pairs
    """
    logger.info(
        "Quality metrics",
        extra={
            "metric_type": "quality",
            "timestamp": datetime.now().isoformat(),
            **metrics,
        },
    )


class ErrorCollector:
    """
    Collect errors during pipeline execution for batch reporting.

    Usage:
        collector = ErrorCollector()

        with collector.capture("fetch_images", source="pexels"):
            # ... code that might error ...
            pass

        if collector.has_errors():
            collector.log_summary(logger)
    """

    def __init__(self) -> None:
        """Initialize error collector."""
        self.errors: List[Dict[str, Any]] = []

    @contextmanager
    def capture(self, operation: str, **context: Any) -> Iterator[None]:
        """
        Capture errors from an operation without raising.

        Args:
            operation: Name of the operation
            **context: Additional context for the error

        Yields:
            None
        """
        try:
            yield
        except Exception as e:
            self.errors.append(
                {
                    "operation": operation,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat(),
                    **context,
                }
            )

    def has_errors(self) -> bool:
        """Check if any errors were collected."""
        return len(self.errors) > 0

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get list of collected errors."""
        return self.errors

    def log_summary(self, logger: StructuredLogger) -> None:
        """
        Log summary of all collected errors.

        Args:
            logger: StructuredLogger instance
        """
        if not self.has_errors():
            return

        logger.warning(
            f"Error summary: {len(self.errors)} errors occurred",
            extra={"error_count": len(self.errors), "errors": self.errors},
        )

    def clear(self) -> None:
        """Clear all collected errors."""
        self.errors.clear()


# Example usage in module
if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(correlation_id)s]",
    )

    # Create structured logger
    logger = StructuredLogger("example")

    # Simple logging with context
    logger.info(
        "Pipeline started", extra={"version": "1.0.0", "environment": "production"}
    )

    # Operation tracking
    with log_operation(logger, "fetch_trends", source="hackernews", limit=25):
        time.sleep(0.1)  # Simulate work

    # Error collection
    collector = ErrorCollector()

    with collector.capture("operation_1"):
        pass  # Success

    with collector.capture("operation_2", source="api"):
        raise ValueError("Test error")  # Error captured

    if collector.has_errors():
        collector.log_summary(logger)
