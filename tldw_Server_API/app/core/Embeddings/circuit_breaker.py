# circuit_breaker.py
# Backward-compatibility shim — delegates to the unified Infrastructure module.
#
# All consumers that import from Embeddings.circuit_breaker continue to work.
# Prefer importing directly from Infrastructure.circuit_breaker for new code.

from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (  # noqa: F401
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
    registry,
)
from tldw_Server_API.app.core.Infrastructure.circuit_breaker import (
    CircuitBreakerOpenError as CircuitBreakerError,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    "circuit_breaker",
    "registry",
]
