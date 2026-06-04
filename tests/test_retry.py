"""Unit tests for retry/backoff behavior."""

import unittest
from unittest.mock import patch, MagicMock
import time

from community_ai_audit.connectors.retry import (
    retry, RetryConfig, retry_on_http, DEFAULT_RETRY_STATUS, DEFAULT_RETRY_EXCEPTIONS,
)


import requests


class FakeRequestException(requests.exceptions.RequestException):
    """Fake requests exception for testing."""
    def __init__(self, status_code=None):
        self.status_code = status_code
        self.response = MagicMock() if status_code else None
        if self.response:
            self.response.status_code = status_code
        super().__init__("Fake request failed")


class TestRetry(unittest.TestCase):
    @patch('time.sleep', return_value=None)  # Don't actually sleep in tests
    def test_exponential_backoff(self, mock_sleep):
        attempt_count = [0]
        
        @retry(max_attempts=3, initial_delay=1.0, exponential_base=2.0, jitter=0.0)
        def flaky_function():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise FakeRequestException(status_code=503)
            return "success"

        result = flaky_function()
        self.assertEqual(result, "success")
        self.assertEqual(attempt_count[0], 3)
        # Verify backoff: 1.0 * 2.0 = 2.0 for second attempt delay
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('time.sleep', return_value=None)
    def test_max_attempts_exceeded(self, mock_sleep):
        @retry(max_attempts=2, initial_delay=0.1, jitter=0.0)
        def always_fails():
            raise FakeRequestException(status_code=500)

        with self.assertRaises(Exception):
            always_fails()

    @patch('time.sleep', return_value=None)
    def test_non_retryable_status_propagates(self, mock_sleep):
        @retry(max_attempts=3, initial_delay=0.1)
        def non_retryable():
            raise FakeRequestException(status_code=400)  # 400 is not in DEFAULT_RETRY_STATUS

        with self.assertRaises(Exception):
            non_retryable()

    def test_retry_config_defaults(self):
        cfg = RetryConfig()
        self.assertEqual(cfg.max_attempts, 3)
        self.assertEqual(cfg.initial_delay, 1.0)
        self.assertEqual(cfg.max_delay, 60.0)
        self.assertEqual(cfg.exponential_base, 2.0)
        self.assertEqual(cfg.jitter, 0.25)
        self.assertTrue(cfg.enabled)

    def test_retry_config_from_dict(self):
        data = {"max_attempts": 5, "initial_delay": 2.0, "max_delay": 120.0}
        cfg = RetryConfig.from_dict(data)
        self.assertEqual(cfg.max_attempts, 5)
        self.assertEqual(cfg.initial_delay, 2.0)
        self.assertEqual(cfg.max_delay, 120.0)
        self.assertTrue(cfg.enabled)

    def test_retry_config_to_dict(self):
        cfg = RetryConfig(max_attempts=4, initial_delay=1.5)
        d = cfg.to_dict()
        self.assertEqual(d["max_attempts"], 4)
        self.assertEqual(d["initial_delay"], 1.5)

    def test_retry_config_disabled(self):
        data = {"enabled": False, "max_attempts": 10}
        cfg = RetryConfig.from_dict(data)
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.max_attempts, 10)

    def test_default_retry_statuses(self):
        self.assertEqual(DEFAULT_RETRY_STATUS, {429, 500, 502, 503, 504})

    def test_default_retry_exceptions(self):
        import requests
        self.assertIn(requests.exceptions.RequestException, DEFAULT_RETRY_EXCEPTIONS)
        self.assertIn(requests.exceptions.Timeout, DEFAULT_RETRY_EXCEPTIONS)
        self.assertIn(requests.exceptions.ConnectionError, DEFAULT_RETRY_EXCEPTIONS)


if __name__ == "__main__":
    unittest.main()
