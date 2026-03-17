from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.AuthNZ.repos.managed_secret_refs_repo import (
    ManagedSecretRefsRepo,
)
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import (
    McpHubRepo,
    parse_managed_secret_ref_id,
)
from tldw_Server_API.app.core.AuthNZ.secret_backends.registry import (
    get_secret_backend,
)
from tldw_Server_API.app.services.mcp_hub_external_access_resolver import (
    McpHubExternalAccessResolver,
)

_APPROVAL_REQUIRED_BLOCKED_REASONS = {
    "disabled_by_assignment",
    "external_capability_not_granted",
    "not_granted",
}
_BACKEND_UNAVAILABLE_BLOCKED_REASONS = {
    "legacy_server_not_bindable",
    "server_disabled",
    "server_superseded",
}
_READY_STATES = {"active", "enabled", "ready"}
_MISSING_STATES = {"missing"}
_REAUTH_REQUIRED_STATES = {"reauth_required", "refresh_required", "revoked"}
_EXPIRED_STATES = {"expired"}
_APPROVAL_REQUIRED_STATES = {"approval_required"}


def _normalize_status_state(value: Any) -> str:
    return str(value or "").strip().lower()


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc)
        return value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc)
        return parsed.replace(tzinfo=timezone.utc)
    return None


@dataclass
class McpCredentialBrokerService:
    """Resolve MCP slot remediation status and brokered secret metadata."""

    repo: McpHubRepo
    external_access_resolver: McpHubExternalAccessResolver | None = None

    def __post_init__(self) -> None:
        if self.external_access_resolver is None:
            self.external_access_resolver = McpHubExternalAccessResolver(repo=self.repo)

    async def get_slot_status(
        self,
        *,
        server_id: str,
        slot_name: str,
        assignment_id: int | None = None,
        profile_id: int | None = None,
    ) -> dict[str, Any]:
        slot = await self.repo.get_external_server_credential_slot(
            server_id=server_id,
            slot_name=slot_name,
        )
        if not slot:
            raise ValueError(f"Unknown external server slot: {server_id}/{slot_name}")

        target_type, target_id, sources, effective_policy = await self._resolve_target_sources_and_policy(
            assignment_id=assignment_id,
            profile_id=profile_id,
        )
        external_access = await self.external_access_resolver.resolve_for_sources(
            sources=sources,
            effective_policy=effective_policy,
        )
        slot_access = self._find_slot_access(
            external_access=external_access,
            server_id=server_id,
            slot_name=slot_name,
        )
        binding = await self._resolve_effective_binding(
            sources=sources,
            server_id=server_id,
            slot_name=slot_name,
        )

        managed_secret_ref_id = (
            parse_managed_secret_ref_id(binding.get("credential_ref")) if binding else None
        )
        state, backend_name, expires_at = await self._resolve_slot_state(
            slot=slot,
            slot_access=slot_access,
            binding=binding,
            managed_secret_ref_id=managed_secret_ref_id,
        )

        return {
            "server_id": str(slot.get("server_id") or server_id),
            "slot_name": str(slot.get("slot_name") or slot_name),
            "binding_target_type": target_type,
            "binding_target_id": str(target_id),
            "credential_ref": str(binding.get("credential_ref") or ("slot" if slot_name else "server"))
            if binding
            else ("slot" if slot_name else "server"),
            "managed_secret_ref_id": managed_secret_ref_id,
            "state": state,
            "blocked_reason": (slot_access or {}).get("blocked_reason"),
            "backend_name": backend_name,
            "expires_at": expires_at,
        }

    async def _resolve_target_sources_and_policy(
        self,
        *,
        assignment_id: int | None,
        profile_id: int | None,
    ) -> tuple[str, int, list[dict[str, Any]], dict[str, Any]]:
        if assignment_id is not None:
            assignment = await self.repo.get_policy_assignment(int(assignment_id))
            if not assignment:
                raise ValueError(f"Unknown policy assignment: {assignment_id}")
            assignment_profile_id = assignment.get("profile_id")
            source_profile_id = int(assignment_profile_id) if assignment_profile_id is not None else None
            sources = [{"assignment_id": int(assignment_id), "profile_id": source_profile_id}]
            policy = await self._build_assignment_effective_policy(
                assignment_id=int(assignment_id),
                profile_id=source_profile_id,
            )
            return "assignment", int(assignment_id), sources, policy

        if profile_id is not None:
            profile = await self.repo.get_permission_profile(int(profile_id))
            if not profile:
                raise ValueError(f"Unknown permission profile: {profile_id}")
            sources = [{"assignment_id": None, "profile_id": int(profile_id)}]
            policy = {
                "capabilities": self._collect_capabilities(profile.get("policy_document")),
            }
            return "profile", int(profile_id), sources, policy

        raise ValueError("assignment_id or profile_id is required")

    async def _build_assignment_effective_policy(
        self,
        *,
        assignment_id: int,
        profile_id: int | None,
    ) -> dict[str, Any]:
        capabilities: set[str] = set()
        if profile_id is not None:
            profile = await self.repo.get_permission_profile(int(profile_id))
            if profile:
                capabilities.update(self._collect_capabilities(profile.get("policy_document")))
        assignment = await self.repo.get_policy_assignment(int(assignment_id))
        if assignment:
            capabilities.update(self._collect_capabilities(assignment.get("inline_policy_document")))
        return {"capabilities": sorted(capabilities)}

    @staticmethod
    def _collect_capabilities(document: Any) -> list[str]:
        if not isinstance(document, dict):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for value in document.get("capabilities") or []:
            capability = str(value or "").strip()
            if not capability or capability in seen:
                continue
            out.append(capability)
            seen.add(capability)
        return out

    @staticmethod
    def _find_slot_access(
        *,
        external_access: dict[str, Any],
        server_id: str,
        slot_name: str,
    ) -> dict[str, Any] | None:
        for server in external_access.get("servers") or []:
            if str(server.get("server_id") or "").strip() != server_id:
                continue
            for slot in server.get("slots") or []:
                if str(slot.get("slot_name") or "").strip().lower() == slot_name.strip().lower():
                    return dict(slot)
        return None

    async def _resolve_effective_binding(
        self,
        *,
        sources: list[dict[str, Any]],
        server_id: str,
        slot_name: str,
    ) -> dict[str, Any] | None:
        default_slot = await self.repo.get_external_server_default_slot(server_id=server_id)
        default_slot_name = (
            str(default_slot.get("slot_name") or "").strip().lower() if default_slot else None
        )
        effective: dict[str, Any] | None = None

        for source in sources:
            profile_id = source.get("profile_id")
            if profile_id is not None:
                for binding in await self.repo.list_credential_bindings(
                    binding_target_type="profile",
                    binding_target_id=str(profile_id),
                ):
                    if self._binding_matches_slot(
                        binding=binding,
                        server_id=server_id,
                        slot_name=slot_name,
                        default_slot_name=default_slot_name,
                    ):
                        effective = dict(binding)

            assignment_id = source.get("assignment_id")
            if assignment_id is None:
                continue
            for binding in await self.repo.list_credential_bindings(
                binding_target_type="assignment",
                binding_target_id=str(assignment_id),
            ):
                if self._binding_matches_slot(
                    binding=binding,
                    server_id=server_id,
                    slot_name=slot_name,
                    default_slot_name=default_slot_name,
                ):
                    effective = dict(binding)

        return effective

    @staticmethod
    def _binding_matches_slot(
        *,
        binding: dict[str, Any],
        server_id: str,
        slot_name: str,
        default_slot_name: str | None,
    ) -> bool:
        if str(binding.get("external_server_id") or "").strip() != server_id:
            return False
        binding_slot_name = str(binding.get("slot_name") or "").strip().lower()
        normalized_slot_name = slot_name.strip().lower()
        if binding_slot_name:
            return binding_slot_name == normalized_slot_name
        return bool(default_slot_name and default_slot_name == normalized_slot_name)

    async def _resolve_slot_state(
        self,
        *,
        slot: dict[str, Any],
        slot_access: dict[str, Any] | None,
        binding: dict[str, Any] | None,
        managed_secret_ref_id: int | None,
    ) -> tuple[str, str | None, datetime | None]:
        blocked_reason = _normalize_status_state((slot_access or {}).get("blocked_reason"))
        if blocked_reason in _APPROVAL_REQUIRED_BLOCKED_REASONS:
            return "approval_required", None, None
        if blocked_reason in _BACKEND_UNAVAILABLE_BLOCKED_REASONS:
            return "backend_unavailable", None, None
        if binding and _normalize_status_state(binding.get("binding_mode")) == "disable":
            return "approval_required", None, None
        if binding is None:
            return "approval_required", None, None

        if managed_secret_ref_id is not None:
            return await self._resolve_managed_secret_state(managed_secret_ref_id)

        if bool((slot_access or {}).get("runtime_usable")) or bool(slot.get("secret_configured")):
            return "ready", None, None
        if blocked_reason == "missing_secret" or not binding:
            return "missing", None, None
        return "missing", None, None

    async def _resolve_managed_secret_state(
        self,
        managed_secret_ref_id: int,
    ) -> tuple[str, str | None, datetime | None]:
        managed_refs_repo = ManagedSecretRefsRepo(self.repo.db_pool)
        await managed_refs_repo.ensure_tables()
        ref = await managed_refs_repo.get_ref(int(managed_secret_ref_id), include_revoked=True)
        if not ref:
            return "missing", None, None

        backend_name = str(ref.get("backend_name") or "") or None
        expires_at = _coerce_datetime(ref.get("expires_at"))
        raw_status = _normalize_status_state(ref.get("status"))
        now = datetime.now(timezone.utc)

        if ref.get("revoked_at"):
            return "reauth_required", backend_name, expires_at
        if raw_status in _REAUTH_REQUIRED_STATES:
            return "reauth_required", backend_name, expires_at
        if raw_status in _APPROVAL_REQUIRED_STATES:
            return "approval_required", backend_name, expires_at
        if raw_status in _EXPIRED_STATES or (expires_at is not None and expires_at <= now):
            return "expired", backend_name, expires_at

        if not backend_name:
            return "backend_unavailable", None, expires_at

        try:
            backend = get_secret_backend(backend_name, db_pool=self.repo.db_pool)
        except ValueError:
            return "backend_unavailable", backend_name, expires_at

        backend_status = await backend.describe_status(int(managed_secret_ref_id))
        backend_state = _normalize_status_state(backend_status.get("state"))
        if backend_state in _READY_STATES:
            return "ready", backend_name, expires_at
        if backend_state in _MISSING_STATES:
            return "missing", backend_name, expires_at
        if backend_state in _REAUTH_REQUIRED_STATES or backend_state == "revoked":
            return "reauth_required", backend_name, expires_at
        if backend_state in _EXPIRED_STATES:
            return "expired", backend_name, expires_at
        if backend_state in _APPROVAL_REQUIRED_STATES:
            return "approval_required", backend_name, expires_at
        return "backend_unavailable", backend_name, expires_at
