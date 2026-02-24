"""
Performance monitoring and metrics collection for the Doctoralia scraper.
"""

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psutil


@dataclass
class PerformanceMetrics:
    """Performance metrics for scraping operations."""

    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    reviews_processed: int = 0
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None


class PerformanceMonitor:
    """
    Monitor performance of scraping operations and system resources.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.metrics: List[PerformanceMetrics] = []
        self.operation_counts = defaultdict(int)
        self.error_counts = defaultdict(int)

    @contextmanager
    def track_operation(self, operation_name: str):
        """Context manager to track operation performance."""
        start_time = time.time()
        metrics = PerformanceMetrics(
            operation_name=operation_name, start_time=start_time
        )

        try:
            # Record initial resource usage
            process = psutil.Process()
            metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            metrics.cpu_usage_percent = process.cpu_percent()

            yield metrics

            metrics.success = True
            self.operation_counts[operation_name] += 1

        except Exception as e:
            metrics.success = False
            metrics.error_message = str(e)
            self.error_counts[operation_name] += 1
            raise
        finally:
            end_time = time.time()
            metrics.end_time = end_time
            metrics.duration = end_time - start_time

            # Record final resource usage
            if metrics.memory_usage_mb is not None:
                process = psutil.Process()
                final_memory = process.memory_info().rss / 1024 / 1024
                metrics.memory_usage_mb = max(metrics.memory_usage_mb, final_memory)

            self.metrics.append(metrics)
            self._log_metrics(metrics)

    def _log_metrics(self, metrics: PerformanceMetrics) -> None:
        """Log performance metrics."""
        if metrics.success:
            self.logger.info(
                f"✅ {metrics.operation_name} completed in {metrics.duration:.2f}s "
                f"(Memory: {metrics.memory_usage_mb:.1f}MB, "
                f"CPU: {metrics.cpu_usage_percent:.1f}%)"
            )
        else:
            self.logger.error(
                f"❌ {metrics.operation_name} failed after {metrics.duration:.2f}s: "
                f"{metrics.error_message}"
            )

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.metrics:
            return {"message": "No metrics collected"}

        total_operations = len(self.metrics)
        successful_operations = sum(1 for m in self.metrics if m.success)
        total_duration = sum(m.duration or 0 for m in self.metrics)
        avg_duration = total_duration / total_operations if total_operations > 0 else 0

        # Calculate success rate
        success_rate = (
            (successful_operations / total_operations * 100)
            if total_operations > 0
            else 0
        )

        # Get memory usage stats
        memory_usages = [
            m.memory_usage_mb for m in self.metrics if m.memory_usage_mb is not None
        ]
        avg_memory = sum(memory_usages) / len(memory_usages) if memory_usages else 0
        max_memory = max(memory_usages) if memory_usages else 0

        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "success_rate_percent": round(success_rate, 2),
            "total_duration_seconds": round(total_duration, 2),
            "average_duration_seconds": round(avg_duration, 2),
            "average_memory_mb": round(avg_memory, 2),
            "max_memory_mb": round(max_memory, 2),
            "operation_counts": dict(self.operation_counts),
            "error_counts": dict(self.error_counts),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.metrics.clear()
        self.operation_counts.clear()
        self.error_counts.clear()
