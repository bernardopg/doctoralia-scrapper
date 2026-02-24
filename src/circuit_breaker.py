"""
Circuit Breaker pattern para proteger contra falhas em cascata
"""

import threading
import time
from enum import Enum
from typing import Any, Callable, Tuple, Type, Union


class CircuitBreakerOpenException(Exception):
    """Exceção levantada quando o circuit breaker está aberto (OPEN)"""

    def __init__(self, recovery_timeout: float):
        self.recovery_timeout = recovery_timeout
        super().__init__(
            f"Circuit breaker is OPEN. Retry after {recovery_timeout:.1f}s"
        )


class CircuitState(Enum):
    """Estados do circuit breaker"""

    CLOSED = "closed"  # Funcionamento normal
    OPEN = "open"  # Circuito aberto (não executa)
    HALF_OPEN = "half_open"  # Teste se pode fechar


class CircuitBreaker:
    """
    Implementação do padrão Circuit Breaker para prevenir falhas em cascata
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Union[
            Type[BaseException], Tuple[Type[BaseException], ...]
        ] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitState.CLOSED
        self._lock = threading.Lock()

    def __call__(self, func: Callable) -> Callable:
        """Decorator para aplicar circuit breaker"""

        def wrapper(*args, **kwargs) -> Any:
            with self._lock:
                if self.state == CircuitState.OPEN:
                    if time.time() - self.last_failure_time >= self.recovery_timeout:
                        self.state = CircuitState.HALF_OPEN
                        self.failure_count = 0
                    else:
                        raise CircuitBreakerOpenException(self.recovery_timeout)

                try:
                    result = func(*args, **kwargs)
                    self._on_success()
                    return result

                except Exception as e:
                    # Only treat configured exception types as circuit failures.
                    # Unexpected exception types are re-raised without affecting the circuit state.
                    if isinstance(e, self.expected_exception):
                        self._on_failure()
                    raise

        return wrapper

    def _on_success(self):
        """Chamado quando uma operação é bem-sucedida"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        """Chamado quando uma operação falha"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def reset(self):
        """Reset circuit breaker state to initial values"""
        with self._lock:
            self.failure_count = 0
            self.last_failure_time = 0.0
            self.state = CircuitState.CLOSED

    @property
    def status(self) -> dict:
        """Status atual do circuit breaker"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "time_to_retry": max(
                0, self.recovery_timeout - (time.time() - self.last_failure_time)
            ),
        }
