import re
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - runtime fallback when PyYAML is unavailable
    yaml = None  # type: ignore


def collect_endpoint_ids_from_code(base_dir: Path) -> set[str]:
    """Scan endpoint code for endpoint_id string literals.

    Catches both dependency usage (endpoint_id="...") and manual assignment
    patterns used in WebSocket handlers (endpoint_id = "...").
    """
    ids: set[str] = set()
    pattern = re.compile(r"endpoint_id\s*=\s*\"([^\"]+)\"")
    for path in base_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in pattern.finditer(text):
            ids.add(m.group(1))
    return ids


def load_catalog_scope_ids(catalog_path: Path) -> set[str]:
    text = catalog_path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        scopes = data.get("scopes", []) or []
        return {s.get("id") for s in scopes if isinstance(s, dict) and s.get("id")}
    # Fallback minimal parser: extract ids between 'scopes:' and 'feature_flags:'
    ids: set[str] = set()
    lines = text.splitlines()
    in_scopes = False
    for line in lines:
        if line.strip().startswith("feature_flags:"):
            if in_scopes:
                break
        if line.strip().startswith("scopes:"):
            in_scopes = True
            continue
        if not in_scopes:
            continue
        m = re.match(r"\s*-\s+id:\s+(.+)$", line)
        if m:
            ids.add(m.group(1).strip())
    return ids


def test_endpoint_ids_have_catalog_entries():
    repo_root = Path(__file__).resolve().parents[3]
    endpoints_dir = repo_root / "tldw_Server_API" / "app" / "api" / "v1" / "endpoints"
    catalog_path = repo_root / "tldw_Server_API" / "Config_Files" / "privilege_catalog.yaml"

    endpoint_ids = collect_endpoint_ids_from_code(endpoints_dir)
    catalog_ids = load_catalog_scope_ids(catalog_path)

    missing = sorted([eid for eid in endpoint_ids if eid not in catalog_ids])
    assert not missing, (
        "Found endpoint_id values without privilege catalog entries: " + ", ".join(missing)
    )
