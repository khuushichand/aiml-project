from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Set

import yaml
from loguru import logger

from tldw_Server_API.app.core.Resource_Governance.policy_admin import AuthNZPolicyAdmin


def _resolve_policy_path(path: Path) -> Path:
    try:
        resolved = path.expanduser()
    except Exception as exc:
        logger.opt(exception=exc).debug("Failed to expand RG policy path: {}", path)
        return path
    if resolved.exists():
        return resolved
    base = Path(__file__).resolve().parents[4]
    candidates: list[Path] = []
    if not resolved.is_absolute():
        try:
            candidates.append((base / resolved).resolve())
        except Exception as exc:
            logger.opt(exception=exc).debug("Failed to resolve RG policy candidate from {}", resolved)
    name = resolved.name or "resource_governor_policies.yaml"
    candidates.append(base / "Config_Files" / name)
    candidates.append(base / "tldw_Server_API" / "Config_Files" / name)
    for candidate in candidates:
        try:
            if candidate.exists():
                logger.info("RG policy file not found at {}; using {}", resolved, candidate)
                return candidate
        except Exception as exc:
            logger.opt(exception=exc).debug("Failed to stat RG policy candidate {}", candidate)
    return resolved


def _default_policy_path() -> Path:
    base = Path(__file__).resolve().parents[4]
    raw = os.getenv(
        "RG_POLICY_PATH",
        str(base / "Config_Files" / "resource_governor_policies.yaml"),
    )
    return _resolve_policy_path(Path(raw))


_DEFAULT_POLICY_PATH = _default_policy_path()


def _iter_route_map_policy_ids(route_map: Dict[str, Any]) -> Iterable[str]:
    by_path = route_map.get("by_path") or {}
    if isinstance(by_path, dict):
        for v in by_path.values():
            if isinstance(v, str) and v.strip():
                yield v.strip()

    by_tag = route_map.get("by_tag") or {}
    if isinstance(by_tag, dict):
        for v in by_tag.values():
            if isinstance(v, str) and v.strip():
                yield v.strip()


def _load_policy_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"RG policy file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("RG policy file must parse to a YAML mapping")
    return data


async def seed_db_policies_from_yaml(
    *,
    yaml_path: Path,
    seed_all: bool,
) -> int:
    """
    Seed missing AuthNZ DB RG policies from a YAML policy file.

    In `RG_POLICY_STORE=db` deployments, YAML `policies:` are not used at runtime.
    This helper bootstraps the DB store by inserting policy rows that are present
    in YAML but missing in `rg_policies`.

    Returns a process exit code (0 on success; 1 on fatal error).
    """
    data = _load_policy_file(yaml_path)
    policies = data.get("policies") or {}
    if not isinstance(policies, dict):
        raise ValueError("RG policy file 'policies' must be a mapping")
    route_map = data.get("route_map") or {}
    if not isinstance(route_map, dict):
        route_map = {}

    referenced: Set[str] = set(_iter_route_map_policy_ids(route_map))
    if seed_all:
        to_seed = set(str(k) for k in policies.keys() if str(k).strip())
    else:
        to_seed = referenced

    admin = AuthNZPolicyAdmin()
    await admin.initialize()

    created = 0
    skipped_existing = 0
    missing_in_yaml: list[str] = []
    known_in_db: Set[str] = set()

    for policy_id in sorted(to_seed):
        rec = await admin.get_policy_record(policy_id)
        if rec:
            known_in_db.add(policy_id)
            skipped_existing += 1
            continue
        payload = policies.get(policy_id)
        if payload is None:
            missing_in_yaml.append(policy_id)
            continue
        if not isinstance(payload, dict):
            raise ValueError(f"Policy payload for {policy_id!r} must be a mapping")
        await admin.upsert_policy(policy_id, payload, version=1)
        created += 1
        known_in_db.add(policy_id)

    print(f"RG DB seed complete: created={created} skipped_existing={skipped_existing} yaml={yaml_path}")
    if missing_in_yaml:
        missing_sorted = ", ".join(sorted(missing_in_yaml))
        print(
            "WARNING: referenced policy_ids missing from YAML (not seeded): "
            f"{missing_sorted}"
        )
    if not seed_all and referenced:
        missing_in_db = [pid for pid in sorted(referenced) if pid not in known_in_db]
        if missing_in_db:
            missing_sorted = ", ".join(missing_in_db)
            print(
                "WARNING: route_map references policy_ids still missing from DB. "
                "Ingress will fail closed for those routes in RG_POLICY_STORE=db: "
                f"{missing_sorted}"
            )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seed_db_from_yaml",
        description=(
            "Seed AuthNZ rg_policies rows from a YAML policy file. "
            "Useful when running with RG_POLICY_STORE=db."
        ),
    )
    p.add_argument(
        "--yaml",
        dest="yaml_path",
        type=Path,
        default=_DEFAULT_POLICY_PATH,
        help="Path to resource_governor_policies.yaml (defaults to RG_POLICY_PATH or repo default).",
    )
    p.add_argument(
        "--all",
        dest="seed_all",
        action="store_true",
        help="Seed all YAML policies, not just policy_ids referenced by route_map.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        yaml_path = args.yaml_path
        if yaml_path != _DEFAULT_POLICY_PATH:
            yaml_path = _resolve_policy_path(yaml_path)
        return asyncio.run(
            seed_db_policies_from_yaml(
                yaml_path=yaml_path,
                seed_all=bool(args.seed_all),
            )
        )
    except Exception as exc:
        print(f"ERROR: failed to seed RG DB policies: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
