from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def _normalize_predicate_values(value: Any) -> list[str]:
    """Normalize predicate values into a lowercased list of strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [str(value).strip().lower()] if str(value).strip() else []


def _extract_domain(url: str | None) -> str:
    """Extract a lowercase domain from a URL or host-like string."""
    if not url:
        return ""
    raw = str(url).strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw if "://" in raw else f"//{raw}", scheme="http")
        netloc = parsed.netloc or ""
        if not netloc and parsed.path:
            netloc = parsed.path.split("/")[0]
        if not netloc:
            return ""
        return netloc.split(":")[0].strip().lower()
    except Exception:
        return ""


def _get_media_review_context(
    db: MediaDatabase, media_id: int, extractor: str | None
) -> dict[str, Any] | None:
    """Return media metadata used for claim review rule evaluation."""
    row = db.execute_query(
        "SELECT id, url, title, type, visibility, org_id, team_id, owner_user_id, client_id "
        "FROM Media WHERE id = ?",
        (int(media_id),),
    ).fetchone()
    if not row:
        return None
    ctx = dict(row)
    ctx["source_domain"] = _extract_domain(ctx.get("url"))
    ctx["extractor"] = str(extractor or "").strip().lower()
    return ctx


def _claim_review_rule_matches(predicate: dict[str, Any], context: dict[str, Any]) -> bool:
    """Return True if a rule predicate matches the claim/media context."""
    if not predicate:
        return True
    supported_keys = {
        "source_domain",
        "source",
        "url_contains",
        "title_contains",
        "media_type",
        "visibility",
        "org_id",
        "team_id",
        "owner_user_id",
        "client_id",
        "media_id",
        "extractor",
    }
    for key in predicate:
        if key not in supported_keys:
            return False

    def _contains_any(haystack: str, needles: list[str]) -> bool:
        if not needles:
            return True
        return any(needle in haystack for needle in needles if needle)

    ctx_url = str(context.get("url") or "").lower()
    ctx_title = str(context.get("title") or "").lower()
    ctx_type = str(context.get("type") or "").lower()
    ctx_visibility = str(context.get("visibility") or "").lower()
    ctx_domain = str(context.get("source_domain") or "").lower()
    ctx_extractor = str(context.get("extractor") or "").lower()

    def _match_exact(ctx_val: Any, predicate_val: Any) -> bool:
        values = _normalize_predicate_values(predicate_val)
        if not values:
            return True
        return str(ctx_val).strip().lower() in values

    if "source_domain" in predicate and not _match_exact(ctx_domain, predicate.get("source_domain")):
        return False
    if "source" in predicate and not _match_exact(ctx_domain, predicate.get("source")):
        return False
    if "url_contains" in predicate and not _contains_any(ctx_url, _normalize_predicate_values(predicate.get("url_contains"))):
        return False
    if "title_contains" in predicate and not _contains_any(ctx_title, _normalize_predicate_values(predicate.get("title_contains"))):
        return False
    if "media_type" in predicate and not _match_exact(ctx_type, predicate.get("media_type")):
        return False
    if "visibility" in predicate and not _match_exact(ctx_visibility, predicate.get("visibility")):
        return False
    if "org_id" in predicate and not _match_exact(context.get("org_id"), predicate.get("org_id")):
        return False
    if "team_id" in predicate and not _match_exact(context.get("team_id"), predicate.get("team_id")):
        return False
    if "owner_user_id" in predicate and not _match_exact(context.get("owner_user_id"), predicate.get("owner_user_id")):
        return False
    if "client_id" in predicate and not _match_exact(context.get("client_id"), predicate.get("client_id")):
        return False
    if "media_id" in predicate and not _match_exact(context.get("id"), predicate.get("media_id")):
        return False
    return not ("extractor" in predicate and not _match_exact(ctx_extractor, predicate.get("extractor")))


def resolve_claim_review_assignment(
    *,
    db: MediaDatabase,
    media_id: int,
    extractor: str | None,
) -> tuple[int | None, str | None]:
    """Return reviewer_id/review_group for a claim based on review rules."""
    context = _get_media_review_context(db, media_id, extractor)
    if not context:
        return None, None
    owner_user_id = context.get("owner_user_id")
    client_id = context.get("client_id")
    user_id = owner_user_id if owner_user_id is not None else client_id
    if user_id is None or str(user_id).strip() == "":
        return None, None
    rules = db.list_claim_review_rules(str(user_id), active_only=True)
    for rule in rules:
        raw_predicate = rule.get("predicate_json")
        try:
            predicate = json.loads(raw_predicate) if raw_predicate else {}
        except Exception:
            predicate = {}
        if not isinstance(predicate, dict):
            predicate = {}
        if not _claim_review_rule_matches(predicate, context):
            continue
        reviewer_id = rule.get("reviewer_id")
        review_group = rule.get("review_group")
        try:
            reviewer_id_val = int(reviewer_id) if reviewer_id is not None else None
        except Exception:
            reviewer_id_val = None
        review_group_val = str(review_group).strip() if review_group else None
        if reviewer_id_val is not None or review_group_val:
            return reviewer_id_val, review_group_val
    return None, None


def apply_review_rules(
    *,
    db: MediaDatabase,
    claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply review rules to a list of claims in-place."""
    if not claims:
        return claims
    assignment_cache: dict[tuple[int, str], tuple[int | None, str | None]] = {}
    for claim in claims:
        try:
            media_id = int(claim.get("media_id"))
        except Exception:
            continue
        extractor = str(claim.get("extractor") or "heuristic")
        cache_key = (media_id, extractor)
        if cache_key not in assignment_cache:
            assignment_cache[cache_key] = resolve_claim_review_assignment(
                db=db,
                media_id=media_id,
                extractor=extractor,
            )
        assigned_reviewer_id, assigned_review_group = assignment_cache[cache_key]
        if claim.get("reviewer_id") is None and assigned_reviewer_id is not None:
            claim["reviewer_id"] = assigned_reviewer_id
        if not claim.get("review_group") and assigned_review_group:
            claim["review_group"] = assigned_review_group
    return claims
