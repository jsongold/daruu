"""Tests for Supabase resilience module."""

import time

import pytest
from app.infrastructure.supabase.resilience import (
    is_retryable_error,
    with_retry,
    with_retry_result,
)


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_500_error_is_retryable(self):
        """500 Internal Server Error should be retryable."""
        error = Exception("HTTP 500 Internal Server Error")
        assert is_retryable_error(error) is True

    def test_502_error_is_retryable(self):
        """502 Bad Gateway should be retryable."""
        error = Exception("502 Bad Gateway from Cloudflare")
        assert is_retryable_error(error) is True

    def test_503_error_is_retryable(self):
        """503 Service Unavailable should be retryable."""
        error = Exception("503 Service Unavailable")
        assert is_retryable_error(error) is True

    def test_504_error_is_retryable(self):
        """504 Gateway Timeout should be retryable."""
        error = Exception("504 Gateway Timeout")
        assert is_retryable_error(error) is True

    def test_timeout_error_is_retryable(self):
        """Timeout errors should be retryable."""
        error = Exception("Connection timeout after 30 seconds")
        assert is_retryable_error(error) is True

    def test_connection_error_is_retryable(self):
        """Connection errors should be retryable."""
        error = Exception("Connection refused by server")
        assert is_retryable_error(error) is True

    def test_cloudflare_error_is_retryable(self):
        """Cloudflare errors should be retryable."""
        error = Exception("Error from Cloudflare: Gateway timeout")
        assert is_retryable_error(error) is True

    def test_rate_limit_error_is_retryable(self):
        """Rate limit errors should be retryable."""
        error = Exception("Rate limit exceeded, please retry later")
        assert is_retryable_error(error) is True

    def test_404_error_is_not_retryable(self):
        """404 Not Found should NOT be retryable."""
        error = Exception("HTTP 404 Not Found")
        assert is_retryable_error(error) is False

    def test_400_error_is_not_retryable(self):
        """400 Bad Request should NOT be retryable."""
        error = Exception("HTTP 400 Bad Request")
        assert is_retryable_error(error) is False

    def test_validation_error_is_not_retryable(self):
        """Validation errors should NOT be retryable."""
        error = Exception("Validation failed: field_id is required")
        assert is_retryable_error(error) is False

    def test_generic_error_is_not_retryable(self):
        """Generic errors without transient patterns should NOT be retryable."""
        error = Exception("Unknown error occurred")
        assert is_retryable_error(error) is False


class TestWithRetry:
    """Tests for with_retry decorator."""

    def test_successful_call_returns_immediately(self):
        """Successful calls should return without retrying."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retries_on_retryable_error(self):
        """Should retry on retryable errors."""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01)
        def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("502 Bad Gateway")
            return "success"

        result = failing_then_succeeding()
        assert result == "success"
        assert call_count == 2

    def test_raises_after_max_retries(self):
        """Should raise after exhausting retries."""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise Exception("500 Internal Server Error")

        with pytest.raises(Exception) as exc_info:
            always_failing()

        assert "500" in str(exc_info.value)
        assert call_count == 3  # Initial + 2 retries

    def test_does_not_retry_non_retryable_error(self):
        """Should not retry non-retryable errors."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        def non_retryable_failure():
            nonlocal call_count
            call_count += 1
            raise Exception("Validation error: invalid field")

        with pytest.raises(Exception) as exc_info:
            non_retryable_failure()

        assert "Validation" in str(exc_info.value)
        assert call_count == 1  # No retries

    def test_exponential_backoff(self):
        """Should use exponential backoff between retries."""
        call_times: list[float] = []

        @with_retry(max_retries=2, base_delay=0.1, max_delay=1.0)
        def timed_failure():
            call_times.append(time.time())
            raise Exception("500 Internal Server Error")

        with pytest.raises(Exception):
            timed_failure()

        assert len(call_times) == 3
        # First retry delay should be ~0.1s
        first_delay = call_times[1] - call_times[0]
        assert 0.08 < first_delay < 0.15  # Allow some tolerance
        # Second retry delay should be ~0.2s
        second_delay = call_times[2] - call_times[1]
        assert 0.15 < second_delay < 0.3


class TestWithRetryResult:
    """Tests for with_retry_result decorator."""

    def test_successful_call_returns_value(self):
        """Successful calls should return the value."""

        @with_retry_result(max_retries=3, base_delay=0.01)
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    def test_returns_none_on_non_retryable_error(self):
        """Should return None on non-retryable errors."""

        @with_retry_result(max_retries=3, base_delay=0.01)
        def non_retryable_failure():
            raise Exception("404 Not Found")

        result = non_retryable_failure()
        assert result is None

    def test_returns_none_after_exhausted_retries(self):
        """Should return None after exhausting retries."""
        call_count = 0

        @with_retry_result(max_retries=2, base_delay=0.01)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise Exception("502 Bad Gateway")

        result = always_failing()
        assert result is None
        assert call_count == 3  # Initial + 2 retries

    def test_retries_and_succeeds(self):
        """Should retry and return success value."""
        call_count = 0

        @with_retry_result(max_retries=3, base_delay=0.01)
        def eventual_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("500 Internal Server Error")
            return "success"

        result = eventual_success()
        assert result == "success"
        assert call_count == 2
