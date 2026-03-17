from __future__ import annotations

from typing import Any


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _claim_value(claims: dict[str, Any], mapping_key: str | None, fallback_key: str) -> Any:
    if isinstance(mapping_key, str) and mapping_key.strip():
        return claims.get(mapping_key.strip())
    return claims.get(fallback_key)


def _mapped_group_values(
    groups: list[str],
    mapping: Any,
) -> list[Any]:
    if not isinstance(mapping, dict):
        return []
    values: list[Any] = []
    for group in groups:
        mapped = mapping.get(group)
        if mapped is None:
            continue
        if isinstance(mapped, (list, tuple, set)):
            values.extend(mapped)
        else:
            values.append(mapped)
    return values


def _coerce_int_list(values: list[Any]) -> list[int]:
    result: list[int] = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def preview_claim_mapping(
    claim_mapping: dict[str, Any] | None,
    claims: dict[str, Any] | None,
) -> dict[str, Any]:
    mapping = claim_mapping if isinstance(claim_mapping, dict) else {}
    claim_values = claims if isinstance(claims, dict) else {}

    subject = _claim_value(claim_values, mapping.get("subject"), "sub")
    email = _claim_value(claim_values, mapping.get("email"), "email")
    username = _claim_value(
        claim_values,
        mapping.get("username"),
        "preferred_username",
    )
    groups = _normalize_string_list(
        _claim_value(claim_values, mapping.get("groups"), "groups")
    )

    derived_roles = _normalize_string_list(mapping.get("default_roles"))
    derived_roles.extend(_normalize_string_list(_mapped_group_values(groups, mapping.get("role_mappings"))))

    derived_org_ids = _coerce_int_list(_mapped_group_values(groups, mapping.get("org_mappings")))
    derived_org_ids.extend(_coerce_int_list(mapping.get("default_org_ids") or []))

    derived_team_ids = _coerce_int_list(_mapped_group_values(groups, mapping.get("team_mappings")))
    derived_team_ids.extend(_coerce_int_list(mapping.get("default_team_ids") or []))

    warnings: list[str] = []
    if subject is None:
        warnings.append("No subject claim resolved from the payload")
    if email is None:
        warnings.append("No email claim resolved from the payload")

    return {
        "subject": str(subject).strip() if subject is not None else None,
        "email": str(email).strip() if email is not None else None,
        "username": str(username).strip() if username is not None else None,
        "groups": sorted(dict.fromkeys(groups)),
        "derived_roles": sorted(dict.fromkeys(_normalize_string_list(derived_roles))),
        "derived_org_ids": sorted(dict.fromkeys(derived_org_ids)),
        "derived_team_ids": sorted(dict.fromkeys(derived_team_ids)),
        "warnings": warnings,
    }
