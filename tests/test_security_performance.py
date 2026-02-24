"""
Tests for security and performance features.
"""

import time
from pathlib import Path

import pytest

from src.error_handling import EnhancedErrorHandler
from src.performance_monitor import PerformanceMetrics, PerformanceMonitor
from src.scraper import RateLimiter
from src.secure_config import ConfigValidator, SecureConfig


class TestRateLimiter:
    """Tests for the rate limiter functionality."""

    def test_rate_limiter_creation(self) -> None:
        """Test rate limiter initialization."""
        limiter = RateLimiter(requests_per_minute=10)
        assert limiter.requests_per_minute == 10
        assert limiter.requests == []
        assert abs(limiter.min_interval - 6.0) < 0.001  # 60/10

    def test_rate_limiter_wait_if_needed(self) -> None:
        """Test that rate limiter waits when needed."""
        limiter = RateLimiter(requests_per_minute=2)  # 30 second intervals

        # First request should not wait
        start_time = time.time()
        limiter.wait_if_needed()
        first_duration = time.time() - start_time
        assert first_duration < 0.1  # Should be very fast

        # Second request should not wait (30 seconds haven't passed)
        start_time = time.time()
        limiter.wait_if_needed()
        second_duration = time.time() - start_time
        assert second_duration < 0.1  # Should be very fast

        # Third request should wait
        start_time = time.time()
        limiter.wait_if_needed()
        third_duration = time.time() - start_time
        assert third_duration >= 25  # Should wait ~30 seconds minus small buffer

    def test_rate_limiter_add_delay(self) -> None:
        """Test adding random delays."""
        limiter = RateLimiter()

        start_time = time.time()
        limiter.add_delay(0.1)  # Minimum 0.1 second delay
        duration = time.time() - start_time

        assert 0.6 <= duration <= 2.2  # Should be between 0.1+0.5 and 0.1+2.0 seconds


class TestSecureConfig:
    """Tests for secure configuration management."""

    def test_secure_config_creation(self, tmp_path: Path) -> None:
        """Test secure config initialization."""
        config_file = tmp_path / "test_config.json"
        secure_config = SecureConfig(config_file, password="test_password")

        assert secure_config.config_file == config_file
        assert secure_config.password == "test_password"

    def test_encrypt_decrypt_sensitive_data(self, tmp_path: Path) -> None:
        """Test encryption and decryption of sensitive data."""
        config_file = tmp_path / "test_config.json"
        secure_config = SecureConfig(config_file, password="test_password")

        test_data = {
            "telegram": {
                "token": "bot123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
                "chat_id": "123456789",
                "enabled": True,
            },
            "database": {"password": "secret_password", "host": "localhost"},
            "normal_setting": "normal_value",
        }

        # Encrypt data
        encrypted_data = secure_config.encrypt_sensitive_data(test_data)

        # Sensitive fields should be encrypted
        assert encrypted_data["telegram"]["token"].startswith("encrypted:")
        assert encrypted_data["database"]["password"].startswith("encrypted:")
        assert encrypted_data["telegram"]["chat_id"].startswith("encrypted:")

        # Non-sensitive fields should remain unchanged
        assert encrypted_data["telegram"]["enabled"] is True
        assert encrypted_data["normal_setting"] == "normal_value"

        # Decrypt data
        decrypted_data = secure_config.decrypt_sensitive_data(encrypted_data)

        # Should match original
        assert decrypted_data["telegram"]["token"] == test_data["telegram"]["token"]
        assert (
            decrypted_data["database"]["password"] == test_data["database"]["password"]
        )
        assert decrypted_data["telegram"]["chat_id"] == test_data["telegram"]["chat_id"]


class TestConfigValidator:
    """Tests for configuration validation."""

    def test_validate_url_valid(self) -> None:
        """Test URL validation with valid URLs."""
        assert ConfigValidator.validate_url("https://www.doctoralia.com.br/medico")
        assert ConfigValidator.validate_url("https://www.doctoralia.es/medico")
        assert ConfigValidator.validate_url("https://www.doctoralia.mx/medico")

    def test_validate_url_invalid(self) -> None:
        """Test URL validation with invalid URLs."""
        assert not ConfigValidator.validate_url(
            "http://www.doctoralia.com.br/medico"
        )  # HTTP not HTTPS
        assert not ConfigValidator.validate_url(
            "https://www.google.com"
        )  # Not doctoralia
        assert not ConfigValidator.validate_url("not-a-url")

    def test_validate_telegram_config_valid(self) -> None:
        """Test Telegram config validation with valid data."""
        assert ConfigValidator.validate_telegram_config(
            "bot123456789:ABCdefGHIjklMNOpqrsTUVwxyz", "123456789"
        )
        assert ConfigValidator.validate_telegram_config(
            "bot123456789:ABCdefGHIjklMNOpqrsTUVwxyz", "@mychannel"
        )

    def test_validate_telegram_config_invalid(self) -> None:
        """Test Telegram config validation with invalid data."""
        assert not ConfigValidator.validate_telegram_config(
            "", "123456789"
        )  # Empty token
        assert not ConfigValidator.validate_telegram_config(
            "bot123", ""
        )  # Empty chat_id
        assert not ConfigValidator.validate_telegram_config(
            "invalid_token", "123"
        )  # Invalid token format

    def test_sanitize_input(self) -> None:
        """Test input sanitization."""
        assert ConfigValidator.sanitize_input("Hello World!") == "Hello World"
        assert ConfigValidator.sanitize_input("Test@123") == "Test@123"
        assert (
            ConfigValidator.sanitize_input("<script>alert('xss')</script>")
            == "scriptalertxssscript"
        )
        assert ConfigValidator.sanitize_input("a" * 2000) == "a" * 1000  # Max length


class TestPerformanceMonitor:
    """Tests for performance monitoring."""

    def test_performance_monitor_creation(self) -> None:
        """Test performance monitor initialization."""
        monitor = PerformanceMonitor()
        assert monitor.metrics == []
        assert monitor.operation_counts == {}
        assert monitor.error_counts == {}

    def test_track_operation_success(self) -> None:
        """Test tracking successful operations."""
        monitor = PerformanceMonitor()

        with monitor.track_operation("test_operation") as metrics:
            metrics.reviews_processed = 5
            time.sleep(0.01)  # Small delay

        assert len(monitor.metrics) == 1
        metric = monitor.metrics[0]
        assert metric.operation_name == "test_operation"
        assert metric.success is True
        assert metric.reviews_processed == 5
        assert metric.duration is not None
        assert metric.duration >= 0.01

    def test_track_operation_failure(self) -> None:
        """Test tracking failed operations."""
        monitor = PerformanceMonitor()

        try:
            with monitor.track_operation("test_operation"):
                raise ValueError("Test error")
        except ValueError:
            pass

        assert len(monitor.metrics) == 1
        metric = monitor.metrics[0]
        assert metric.success is False
        assert metric.error_message == "Test error"

    def test_get_summary(self) -> None:
        """Test performance summary generation."""
        monitor = PerformanceMonitor()

        # Add some mock metrics
        monitor.metrics = [
            PerformanceMetrics("op1", 0, 1, 1.0, True, None, 10, 50, 10),
            PerformanceMetrics("op2", 0, 2, 2.0, False, "error", 5, 60, 15),
        ]
        monitor.operation_counts["op1"] = 1
        monitor.operation_counts["op2"] = 1
        monitor.error_counts["op2"] = 1

        summary = monitor.get_summary()

        assert summary["total_operations"] == 2
        assert summary["successful_operations"] == 1
        assert abs(summary["success_rate_percent"] - 50.0) < 0.001
        assert abs(summary["total_duration_seconds"] - 3.0) < 0.001
        assert abs(summary["average_duration_seconds"] - 1.5) < 0.001


class TestEnhancedErrorHandler:
    """Tests for enhanced error handling."""

    def test_execute_with_retry_success(self) -> None:
        """Test successful execution with retry."""
        handler = EnhancedErrorHandler(max_retries=3)
        call_count = 0

        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Temporary error")
            return "success"

        result = handler.execute_with_retry(test_func, operation_name="test")
        assert result == "success"
        assert call_count == 2  # Should retry once

    def test_execute_with_retry_failure(self) -> None:
        """Test failed execution after all retries."""
        handler = EnhancedErrorHandler(max_retries=2)

        def test_func():
            raise ConnectionError("Persistent error")

        with pytest.raises(ConnectionError):
            handler.execute_with_retry(test_func, operation_name="test")

    def test_fatal_error_no_retry(self) -> None:
        """Test that fatal errors don't trigger retries."""
        handler = EnhancedErrorHandler(max_retries=3)

        def test_func():
            raise ValueError("Fatal error")

        with pytest.raises(ValueError):
            handler.execute_with_retry(test_func, operation_name="test")
