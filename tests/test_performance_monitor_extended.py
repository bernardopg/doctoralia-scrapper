import pytest

from src.performance_monitor import PerformanceMonitor


def test_track_operation_error_path():
    monitor = PerformanceMonitor()
    with pytest.raises(ValueError):
        with monitor.track_operation("failing_op"):
            raise ValueError("boom")
    assert len(monitor.metrics) == 1
    m = monitor.metrics[0]
    assert m.success is False
    assert m.error_message == "boom"
    assert monitor.error_counts.get("failing_op") == 1
    assert (
        monitor.operation_counts.get("failing_op") is None
        or monitor.operation_counts.get("failing_op") == 0
    )


def test_reset_clears_metrics():
    monitor = PerformanceMonitor()
    with monitor.track_operation("ok"):
        pass
    assert monitor.metrics
    monitor.reset()
    assert monitor.metrics == []
    assert monitor.operation_counts == {}
    assert monitor.error_counts == {}
