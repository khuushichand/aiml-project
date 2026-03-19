from __future__ import annotations

from dataclasses import dataclass

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.secret_backends.base import SecretBackend
from tldw_Server_API.app.core.AuthNZ.secret_backends.local_encrypted import (
    LocalEncryptedSecretBackend,
)


@dataclass(frozen=True)
class SecretBackendDescriptor:
    name: str
    display_name: str
    capabilities: dict[str, bool]
    backend_cls: type[SecretBackend]


_SECRET_BACKENDS: dict[str, SecretBackendDescriptor] = {
    LocalEncryptedSecretBackend.backend_name: SecretBackendDescriptor(
        name=LocalEncryptedSecretBackend.backend_name,
        display_name=LocalEncryptedSecretBackend.display_name,
        capabilities=dict(LocalEncryptedSecretBackend.capabilities),
        backend_cls=LocalEncryptedSecretBackend,
    ),
}


def get_secret_backend(name: str, *, db_pool: DatabasePool) -> SecretBackend:
    descriptor = _SECRET_BACKENDS.get(name)
    if descriptor is None:
        raise ValueError(f"Unknown secret backend: {name}")
    return descriptor.backend_cls(db_pool=db_pool)


def list_secret_backend_descriptors() -> list[SecretBackendDescriptor]:
    return list(_SECRET_BACKENDS.values())
