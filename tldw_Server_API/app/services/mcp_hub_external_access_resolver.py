from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo


@dataclass
class McpHubExternalAccessResolver:
    """Resolve effective external server access for an assignment."""

    repo: McpHubRepo

    async def resolve(
        self,
        *,
        assignment_id: int,
        effective_policy: dict[str, Any],
    ) -> dict[str, Any]:
        assignment = await self.repo.get_policy_assignment(int(assignment_id))
        if not assignment:
            return {"servers": []}
        return await self.resolve_for_sources(
            sources=[
                {
                    "assignment_id": int(assignment.get("id")),
                    "profile_id": assignment.get("profile_id"),
                }
            ],
            effective_policy=effective_policy,
        )

    async def resolve_for_sources(
        self,
        *,
        sources: list[dict[str, Any]],
        effective_policy: dict[str, Any],
    ) -> dict[str, Any]:
        states: dict[str, dict[str, Any]] = {}

        for source in sources:
            profile_id = source.get("profile_id")
            if profile_id is not None:
                for binding in await self.repo.list_credential_bindings(
                    binding_target_type="profile",
                    binding_target_id=str(profile_id),
                ):
                    server_id = str(binding.get("external_server_id") or "")
                    if not server_id or str(binding.get("binding_mode") or "grant") != "grant":
                        continue
                    state = states.setdefault(server_id, {"granted_by": None, "disabled_by_assignment": False})
                    state["granted_by"] = "profile"
                    state["disabled_by_assignment"] = False

            assignment_id = source.get("assignment_id")
            if assignment_id is None:
                continue
            for binding in await self.repo.list_credential_bindings(
                binding_target_type="assignment",
                binding_target_id=str(assignment_id),
            ):
                server_id = str(binding.get("external_server_id") or "")
                if not server_id:
                    continue
                state = states.setdefault(server_id, {"granted_by": None, "disabled_by_assignment": False})
                if str(binding.get("binding_mode") or "grant") == "disable":
                    state["disabled_by_assignment"] = True
                    if state.get("granted_by") is None:
                        state["granted_by"] = "assignment"
                else:
                    state["granted_by"] = "assignment"
                    state["disabled_by_assignment"] = False

        return {"servers": await self._build_server_rows(states=states, effective_policy=effective_policy)}

    async def _build_server_rows(
        self,
        *,
        states: dict[str, dict[str, Any]],
        effective_policy: dict[str, Any],
    ) -> list[dict[str, Any]]:
        policy_document = dict(effective_policy.get("policy_document") or {})
        capabilities = set(
            effective_policy.get("capabilities")
            or policy_document.get("capabilities")
            or []
        )
        allows_external = "network.external" in capabilities
        rows: list[dict[str, Any]] = []
        for server_id in sorted(states.keys()):
            server = await self.repo.get_external_server(server_id)
            if not server:
                continue
            state = states.get(server_id) or {}
            disabled = bool(state.get("disabled_by_assignment"))
            secret_available = bool(server.get("secret_configured"))
            server_source = str(server.get("server_source") or "managed")
            superseded_by = server.get("superseded_by_server_id")
            enabled = bool(server.get("enabled"))
            runtime_executable = bool(
                allows_external
                and not disabled
                and secret_available
                and server_source == "managed"
                and not superseded_by
                and enabled
            )
            blocked_reason = None
            if disabled:
                blocked_reason = "disabled_by_assignment"
            elif server_source != "managed":
                blocked_reason = "legacy_server_not_bindable"
            elif superseded_by:
                blocked_reason = "server_superseded"
            elif not enabled:
                blocked_reason = "server_disabled"
            elif not allows_external:
                blocked_reason = "external_capability_not_granted"
            elif not secret_available:
                blocked_reason = "missing_secret"

            rows.append(
                {
                    "server_id": server_id,
                    "server_name": server.get("name"),
                    "granted_by": state.get("granted_by"),
                    "disabled_by_assignment": disabled,
                    "server_source": server_source,
                    "superseded_by_server_id": superseded_by,
                    "secret_available": secret_available,
                    "runtime_executable": runtime_executable,
                    "blocked_reason": blocked_reason,
                }
            )
        return rows


async def get_mcp_hub_external_access_resolver() -> McpHubExternalAccessResolver:
    """Resolve the external-access resolver backed by the current AuthNZ database."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    return McpHubExternalAccessResolver(repo=repo)
