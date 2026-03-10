from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

        profile_id = assignment.get("profile_id")
        granted_server_ids: set[str] = set()
        if profile_id is not None:
            for binding in await self.repo.list_credential_bindings(
                binding_target_type="profile",
                binding_target_id=str(profile_id),
            ):
                if str(binding.get("binding_mode") or "grant") == "grant":
                    granted_server_ids.add(str(binding.get("external_server_id") or ""))

        disabled_server_ids: set[str] = set()
        for binding in await self.repo.list_credential_bindings(
            binding_target_type="assignment",
            binding_target_id=str(assignment_id),
        ):
            server_id = str(binding.get("external_server_id") or "")
            if not server_id:
                continue
            if str(binding.get("binding_mode") or "grant") == "disable":
                disabled_server_ids.add(server_id)
            else:
                granted_server_ids.add(server_id)

        allows_external = "network.external" in set(
            effective_policy.get("capabilities") or []
        )
        rows: list[dict[str, Any]] = []
        for server_id in sorted(granted_server_ids | disabled_server_ids):
            server = await self.repo.get_external_server(server_id)
            if not server:
                continue
            disabled = server_id in disabled_server_ids
            secret_available = bool(server.get("secret_configured"))
            runtime_executable = bool(
                allows_external
                and not disabled
                and secret_available
                and str(server.get("server_source") or "managed") == "managed"
                and not server.get("superseded_by_server_id")
                and bool(server.get("enabled"))
            )
            blocked_reason = None
            if disabled:
                blocked_reason = "disabled_by_assignment"
            elif not allows_external:
                blocked_reason = "external_capability_not_granted"
            elif not secret_available:
                blocked_reason = "missing_secret"

            rows.append(
                {
                    "server_id": server_id,
                    "server_name": server.get("name"),
                    "granted_by": "profile" if server_id in granted_server_ids else "assignment",
                    "disabled_by_assignment": disabled,
                    "server_source": server.get("server_source", "managed"),
                    "superseded_by_server_id": server.get("superseded_by_server_id"),
                    "secret_available": secret_available,
                    "runtime_executable": runtime_executable,
                    "blocked_reason": blocked_reason,
                }
            )
        return {"servers": rows}
