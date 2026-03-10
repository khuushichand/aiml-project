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
                    await self._apply_binding(
                        states=states,
                        server_id=server_id,
                        slot_name=binding.get("slot_name"),
                        binding_mode="grant",
                        granted_by="profile",
                    )

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
                await self._apply_binding(
                    states=states,
                    server_id=server_id,
                    slot_name=binding.get("slot_name"),
                    binding_mode=str(binding.get("binding_mode") or "grant"),
                    granted_by="assignment",
                )

        return {"servers": await self._build_server_rows(states=states, effective_policy=effective_policy)}

    async def _apply_binding(
        self,
        *,
        states: dict[str, dict[str, Any]],
        server_id: str,
        slot_name: Any,
        binding_mode: str,
        granted_by: str,
    ) -> None:
        server_state = states.setdefault(
            server_id,
            {
                "granted_by": None,
                "disabled_by_assignment": False,
                "slots": {},
            },
        )
        slots = await self.repo.list_external_server_credential_slots(server_id=server_id)
        normalized_slot_name = str(slot_name or "").strip().lower()
        target_slot_names: list[str] = []
        if slots:
            if normalized_slot_name:
                target_slot_names = [normalized_slot_name]
            else:
                default_slot = await self.repo.get_external_server_default_slot(server_id=server_id)
                if default_slot is not None:
                    target_slot_names = [str(default_slot.get("slot_name") or "").strip().lower()]
        if target_slot_names:
            slot_states = server_state.setdefault("slots", {})
            for target_slot_name in target_slot_names:
                slot_state = slot_states.setdefault(
                    target_slot_name,
                    {"granted_by": None, "disabled_by_assignment": False},
                )
                if binding_mode == "disable":
                    slot_state["disabled_by_assignment"] = True
                    if slot_state.get("granted_by") is None:
                        slot_state["granted_by"] = granted_by
                else:
                    slot_state["granted_by"] = granted_by
                    slot_state["disabled_by_assignment"] = False
            return

        if binding_mode == "disable":
            server_state["disabled_by_assignment"] = True
            if server_state.get("granted_by") is None:
                server_state["granted_by"] = granted_by
        else:
            server_state["granted_by"] = granted_by
            server_state["disabled_by_assignment"] = False

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
            slots = await self.repo.list_external_server_credential_slots(server_id=server_id)
            server_source = str(server.get("server_source") or "managed")
            superseded_by = server.get("superseded_by_server_id")
            enabled = bool(server.get("enabled"))
            if slots:
                slot_rows: list[dict[str, Any]] = []
                active_slot_states = dict(state.get("slots") or {})
                for slot in slots:
                    slot_name = str(slot.get("slot_name") or "").strip().lower()
                    slot_state = dict(active_slot_states.get(slot_name) or {})
                    granted_by = slot_state.get("granted_by")
                    disabled = bool(slot_state.get("disabled_by_assignment"))
                    secret_available = bool(slot.get("secret_configured"))
                    runtime_usable = bool(
                        granted_by
                        and allows_external
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
                    elif granted_by and not secret_available:
                        blocked_reason = "missing_secret"
                    elif granted_by is None:
                        blocked_reason = "not_granted"
                    slot_rows.append(
                        {
                            "slot_name": slot.get("slot_name"),
                            "display_name": slot.get("display_name"),
                            "granted_by": granted_by,
                            "disabled_by_assignment": disabled,
                            "secret_available": secret_available,
                            "runtime_usable": runtime_usable,
                            "blocked_reason": blocked_reason,
                        }
                    )

                runtime_executable = any(bool(slot.get("runtime_usable")) for slot in slot_rows)
                disabled = any(bool(slot.get("disabled_by_assignment")) for slot in slot_rows)
                secret_available = any(bool(slot.get("secret_available")) for slot in slot_rows)
                blocked_reason = None
                if disabled and not runtime_executable:
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
                elif not runtime_executable:
                    blocked_reason = "no_usable_slots"

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
                        "slots": slot_rows,
                    }
                )
                continue

            disabled = bool(state.get("disabled_by_assignment"))
            secret_available = bool(server.get("secret_configured"))
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
                    "slots": [],
                }
            )
        return rows


async def get_mcp_hub_external_access_resolver() -> McpHubExternalAccessResolver:
    """Resolve the external-access resolver backed by the current AuthNZ database."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    return McpHubExternalAccessResolver(repo=repo)
