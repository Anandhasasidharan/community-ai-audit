"""
Shared retry utility for all connectors.
Provides configurable exponential-backoff retry with jitter for
HTTP-based SIEM integrations.
"""

from __future__ import annotations

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

import requests

log = logging.getLogger(__name__)

# Default retryable HTTP status codes across SIEM platforms
DEFAULT_RETRY_STATUS = {429, 500, 502, 503, 504}
DEFAULT_RETRY_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    requests.exceptions.RequestException,
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
)


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.25,
    retry_statuses: Optional[set[int]] = None,
    retry_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """Decorator for retrying a function call with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including the first).
        initial_delay: Starting delay in seconds.
        max_delay: Maximum delay cap in seconds.
        exponential_base: Base for exponential backoff.
        jitter: Random jitter fraction [0, 1] added to each delay.
        retry_statuses: HTTP status codes to retry on. None uses DEFAULT_RETRY_STATUS.
        retry_exceptions: Exception types to retry on. None uses DEFAULT_RETRY_EXCEPTIONS.
        on_retry: Optional callback(exception, attempt) called on each retry.

    Returns:
        Decorated function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            statuses = retry_statuses if retry_statuses is not None else DEFAULT_RETRY_STATUS
            exceptions = retry_exceptions if retry_exceptions is not None else DEFAULT_RETRY_EXCEPTIONS

            delay = initial_delay
            last_exc: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    # Check if HTTP status warrants retry
                    http_status = getattr(exc, "response", None)
                    if http_status is not None and http_status.status_code not in statuses:
                        # Non-retryable HTTP error — propagate immediately
                        raise

                    if attempt == max_attempts:
                        log.error(
                            "All %d retry attempts exhausted for %s: %s",
                            max_attempts, func.__name__, exc,
                        )
                        raise

                    # Compute delay with jitter
                    sleep_time = min(delay, max_delay)
                    jitter_amount = sleep_time * jitter * random.random()
                    actual_delay = sleep_time + jitter_amount

                    log.warning(
                        "Retry %d/%d for %s in %.1fs — %s",
                        attempt, max_attempts, func.__name__, actual_delay, exc,
                    )
                    if on_retry:
                        on_retry(exc, attempt)

                    time.sleep(actual_delay)
                    delay = min(delay * exponential_base, max_delay)

            # Should not reach here, but raise last exception if we do
            if last_exc is not None:
                raise last_exc

        return wrapper

    return decorator


def retry_on_http(
    func: Callable[..., requests.Response],
    max_attempts: int = 3,
    statuses: Optional[set[int]] = None,
) -> requests.Response:
    """Direct (non-decorator) retry wrapper for HTTP requests.

    Use when you need to wrap a specific call inline rather than a full method.
    """
    statuses = statuses or DEFAULT_RETRY_STATUS
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            resp = func()
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in statuses:
                if attempt < max_attempts:
                    jitter = delay * 0.25 * random.random()
                    time.sleep(delay + jitter)
                    delay = min(delay * 2, 60.0)
                    continue
            raise
        except Exception:
            raise


class RetryConfig:
    """Structured retry configuration for connectors."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: float = 0.25,
        enabled: bool = True,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.enabled = enabled

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "RetryConfig":
        if not data:
            return cls()
        enabled = data.get("enabled", True)
        return cls(
            max_attempts=int(data.get("max_attempts", 3)),
            initial_delay=float(data.get("initial_delay", 1.0)),
            max_delay=float(data.get("max_delay", 60.0)),
            exponential_base=float(data.get("exponential_base", 2.0)),
            jitter=float(data.get("jitter", 0.25)),
            enabled=enabled,
        )

    def to_dict(self) -> dict:
        return {
            "max_attempts": self.max_attempts,
            "initial_delay": self.initial_delay,
            "max_delay": self.max_delay,
            "exponential_base": self.exponential_base,
            "jitter": self.jitter,
            "enabled": self.enabled,
        }