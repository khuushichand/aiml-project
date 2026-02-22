#!/usr/bin/env python3
"""
Stage 9A helper: snapshot Prometheus text metrics and compute RG parity deltas.

This is intended for dev/staging "soak windows" where you want to confirm:
  - Shadow mismatch counters stay at (near) zero.
  - Each expected policy_id saw at least one decision.

Examples:
  # Capture before/after snapshots (default metrics endpoint is /metrics)
  python Helper_Scripts/rg_stage9a_parity_window.py snapshot --out stage9a_before.prom
  python Helper_Scripts/rg_stage9a_parity_window.py snapshot --out stage9a_after.prom

  # Report deltas for key RG metrics
  python Helper_Scripts/rg_stage9a_parity_window.py report --before stage9a_before.prom --after stage9a_after.prom

  # Evaluate a full release-window gate from multiple snapshots
  python Helper_Scripts/rg_stage9a_parity_window.py release-window-report \
    --snapshots-glob "stage9a_window/*.prom" \
    --out-md stage9a_release_window.md

  # Include a bearer token or API key if your metrics endpoint is protected
  python Helper_Scripts/rg_stage9a_parity_window.py snapshot --api-key "$SINGLE_USER_API_KEY" --out before.prom
  python Helper_Scripts/rg_stage9a_parity_window.py snapshot --bearer-token "$JWT" --out before.prom
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin


LabelTuple = Tuple[Tuple[str, str], ...]
SampleKey = Tuple[str, LabelTuple]


DEFAULT_EXPECTED_POLICY_IDS: Tuple[str, ...] = (
    "chat.default",           # /api/v1/chat/*
    "character_chat.default", # /api/v1/chats/*
    "embeddings.default",     # /api/v1/embeddings*
    "audio.default",          # /api/v1/audio/*
    "authnz.default",         # /api/v1/auth/*
    "evals.default",          # /api/v1/evaluations/*
    "media.default",          # /api/v1/media/*
    "workflows.default",      # /api/v1/workflows/*
    "rag.default",            # /api/v1/rag/*
)
# NOTE: mcp.ingestion and web_scraping.default are module-level internal policies,
# not ingress-routed, so they won't appear in parity tests unless exercised internally.


@dataclass(frozen=True)
class SnapshotMeta:
    captured_at_unix: int
    metrics_url: str
    health_url: Optional[str]
    health_status_code: Optional[int]
    rg_policy_version: Optional[int]
    rg_policy_store: Optional[str]
    rg_policy_count: Optional[int]


def _join(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    p = (path or "").lstrip("/")
    return urljoin(base, p)


def _headers(api_key: Optional[str], bearer_token: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if api_key:
        headers["X-API-KEY"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return headers


def _fetch_text(url: str, *, headers: Dict[str, str], timeout_sec: float) -> str:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # nosec B310
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def _fetch_json(url: str, *, headers: Dict[str, str], timeout_sec: float) -> Tuple[Optional[int], Optional[dict]]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # nosec B310
            raw = resp.read()
            code = getattr(resp, "status", None)
        try:
            return int(code) if code is not None else None, json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return int(code) if code is not None else None, None
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except Exception:
            raw = b""
        try:
            data = json.loads(raw.decode("utf-8", errors="replace")) if raw else None
        except Exception:
            data = None
        return int(getattr(e, "code", 0) or 0), data


def _parse_labels(s: str) -> Dict[str, str]:
    """
    Parse Prometheus label sets like: key="value",foo="bar".

    This is intentionally small and supports the common escape sequences used
    in Prometheus text exposition.
    """
    out: Dict[str, str] = {}
    i = 0
    n = len(s)

    def _read_key(start: int) -> Tuple[str, int]:
        j = start
        while j < n and s[j] not in ("=", " ", "\t", "\n", "\r"):
            j += 1
        return s[start:j].strip(), j

    def _read_quoted_value(start: int) -> Tuple[str, int]:
        if start >= n or s[start] != '"':
            raise ValueError("expected opening quote")
        j = start + 1
        buf: List[str] = []
        while j < n:
            ch = s[j]
            if ch == '"':
                return "".join(buf), j + 1
            if ch == "\\" and (j + 1) < n:
                nxt = s[j + 1]
                if nxt in ('\\', '"'):
                    buf.append(nxt)
                elif nxt == "n":
                    buf.append("\n")
                elif nxt == "t":
                    buf.append("\t")
                elif nxt == "r":
                    buf.append("\r")
                else:
                    # Unknown escape: preserve the escaped char
                    buf.append(nxt)
                j += 2
                continue
            buf.append(ch)
            j += 1
        raise ValueError("unterminated quoted value")

    while i < n:
        while i < n and s[i] in (" ", "\t", ","):
            i += 1
        if i >= n:
            break
        key, i = _read_key(i)
        if not key:
            break
        if i >= n or s[i] != "=":
            raise ValueError(f"invalid label key/value near: {s[i:]!r}")
        i += 1
        val, i = _read_quoted_value(i)
        out[key] = val
        while i < n and s[i] in (" ", "\t"):
            i += 1
        if i < n and s[i] == ",":
            i += 1
    return out


def parse_prometheus_text(text: str) -> Dict[SampleKey, float]:
    """
    Parse Prometheus exposition text into a map of (metric_name, labels) -> value.

    Only samples are returned; HELP/TYPE/comments are ignored.
    """
    samples: Dict[SampleKey, float] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Split off the numeric value (and optional timestamp)
        parts = line.split()
        if len(parts) < 2:
            continue
        left = parts[0]
        val_s = parts[1]
        try:
            value = float(val_s)
        except Exception:
            continue

        if "{" in left and left.endswith("}"):
            name, rest = left.split("{", 1)
            labels_s = rest[:-1]
            try:
                labels = _parse_labels(labels_s)
            except Exception:
                continue
        else:
            name = left
            labels = {}

        key: SampleKey = (name, tuple(sorted((str(k), str(v)) for k, v in labels.items())))
        samples[key] = value
    return samples


def _effective_increase(before: float, after: float) -> Tuple[float, bool]:
    """
    Return (increase, reset_detected).

    Counters should be monotonic. If after < before, assume a reset occurred.
    """
    if after >= before:
        return after - before, False
    return after, True


def _sum_increases_by(
    *,
    before: Dict[SampleKey, float],
    after: Dict[SampleKey, float],
    metric_name: str,
    group_labels: Sequence[str],
) -> Tuple[Dict[Tuple[str, ...], float], bool]:
    out: Dict[Tuple[str, ...], float] = {}
    reset = False
    keys = {k for k in before.keys() if k[0] == metric_name} | {k for k in after.keys() if k[0] == metric_name}
    for key in keys:
        labels = dict(key[1])
        b = float(before.get(key, 0.0))
        a = float(after.get(key, 0.0))
        inc, did_reset = _effective_increase(b, a)
        reset = reset or did_reset
        grp = tuple(labels.get(lbl, "") for lbl in group_labels)
        out[grp] = out.get(grp, 0.0) + float(inc)
    return out, reset


def _top_increases(
    *,
    before: Dict[SampleKey, float],
    after: Dict[SampleKey, float],
    metric_name: str,
    top_n: int,
) -> Tuple[List[Tuple[float, Dict[str, str]]], bool]:
    items: List[Tuple[float, Dict[str, str]]] = []
    reset = False
    keys = {k for k in before.keys() if k[0] == metric_name} | {k for k in after.keys() if k[0] == metric_name}
    for key in keys:
        labels = dict(key[1])
        b = float(before.get(key, 0.0))
        a = float(after.get(key, 0.0))
        inc, did_reset = _effective_increase(b, a)
        reset = reset or did_reset
        if inc > 0:
            items.append((float(inc), labels))
    items.sort(key=lambda x: x[0], reverse=True)
    return items[: max(0, int(top_n))], reset


def _format_kv(labels: Dict[str, str], keys: Sequence[str]) -> str:
    return ", ".join(f"{k}={labels.get(k, '')}" for k in keys)


def _load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _maybe_read_meta(prom_path: Path) -> Optional[SnapshotMeta]:
    meta_path = prom_path.with_suffix(prom_path.suffix + ".meta.json")
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return SnapshotMeta(
            captured_at_unix=int(data.get("captured_at_unix") or 0),
            metrics_url=str(data.get("metrics_url") or ""),
            health_url=data.get("health_url"),
            health_status_code=data.get("health_status_code"),
            rg_policy_version=data.get("rg_policy_version"),
            rg_policy_store=data.get("rg_policy_store"),
            rg_policy_count=data.get("rg_policy_count"),
        )
    except Exception:
        return None


def _write_meta(prom_path: Path, meta: SnapshotMeta) -> None:
    meta_path = prom_path.with_suffix(prom_path.suffix + ".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "captured_at_unix": meta.captured_at_unix,
                "metrics_url": meta.metrics_url,
                "health_url": meta.health_url,
                "health_status_code": meta.health_status_code,
                "rg_policy_version": meta.rg_policy_version,
                "rg_policy_store": meta.rg_policy_store,
                "rg_policy_count": meta.rg_policy_count,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def cmd_snapshot(args: argparse.Namespace) -> int:
    out_path = Path(args.out)
    if out_path.suffix == "":
        out_path = out_path.with_suffix(".prom")

    metrics_url = _join(args.base_url, args.metrics_path)
    health_url = _join(args.base_url, args.health_path) if args.health_path else None
    headers = _headers(args.api_key, args.bearer_token)

    try:
        text = _fetch_text(metrics_url, headers=headers, timeout_sec=float(args.timeout))
    except Exception as e:
        print(f"Failed to fetch metrics from {metrics_url}: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    rg_policy_version = None
    rg_policy_store = None
    rg_policy_count = None
    health_status_code = None
    if health_url:
        code, data = _fetch_json(health_url, headers=headers, timeout_sec=float(args.timeout))
        health_status_code = code
        if isinstance(data, dict):
            rgv = data.get("rg_policy_version")
            if rgv is not None:
                try:
                    rg_policy_version = int(rgv)
                except Exception:
                    rg_policy_version = None
            rg_policy_store = data.get("rg_policy_store")
            rpc = data.get("rg_policy_count")
            if rpc is not None:
                try:
                    rg_policy_count = int(rpc)
                except Exception:
                    rg_policy_count = None

    meta = SnapshotMeta(
        captured_at_unix=int(time.time()),
        metrics_url=metrics_url,
        health_url=health_url,
        health_status_code=health_status_code,
        rg_policy_version=rg_policy_version,
        rg_policy_store=str(rg_policy_store) if rg_policy_store is not None else None,
        rg_policy_count=rg_policy_count,
    )
    _write_meta(out_path, meta)

    print(f"Wrote {out_path}")
    print(f"Wrote {out_path.with_suffix(out_path.suffix + '.meta.json')}")
    if meta.rg_policy_version is not None:
        print(f"rg_policy_version={meta.rg_policy_version} store={meta.rg_policy_store} policies={meta.rg_policy_count}")
    return 0


def _write_markdown_report(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _snapshot_epoch(path: Path, meta: Optional[SnapshotMeta]) -> int:
    if meta and meta.captured_at_unix:
        try:
            return int(meta.captured_at_unix)
        except (TypeError, ValueError):
            meta = None
    try:
        return int(path.stat().st_mtime)
    except Exception:
        return 0


def _aggregate_metric_over_series(
    *,
    series: Sequence[Dict[SampleKey, float]],
    metric_name: str,
    group_labels: Sequence[str],
) -> Tuple[Dict[Tuple[str, ...], float], bool]:
    totals: Dict[Tuple[str, ...], float] = {}
    reset_detected = False
    if len(series) < 2:
        return totals, reset_detected

    for before, after in zip(series[:-1], series[1:]):
        incs, did_reset = _sum_increases_by(
            before=before,
            after=after,
            metric_name=metric_name,
            group_labels=group_labels,
        )
        reset_detected = reset_detected or did_reset
        for grp, val in incs.items():
            totals[grp] = totals.get(grp, 0.0) + float(val)
    return totals, reset_detected


def _analyze_release_window(
    *,
    snapshots: Sequence[Tuple[Path, Optional[SnapshotMeta], Dict[SampleKey, float]]],
    expected_policy_ids: Sequence[str],
    min_window_hours: float,
    mismatch_threshold: float,
    mismatch_rate_threshold: float,
    allow_resets: bool,
    allow_missing_coverage: bool,
    top_mismatches: int,
    top_policies: int,
    top_denials: int,
) -> Dict[str, Any]:
    if len(snapshots) < 2:
        raise ValueError("At least two snapshots are required.")

    ordered = sorted(snapshots, key=lambda x: _snapshot_epoch(x[0], x[1]))
    paths = [p for p, _, _ in ordered]
    metas = [m for _, m, _ in ordered]
    series = [s for _, _, s in ordered]

    first_epoch = _snapshot_epoch(paths[0], metas[0])
    last_epoch = _snapshot_epoch(paths[-1], metas[-1])
    window_seconds = max(0, int(last_epoch - first_epoch))
    window_hours = float(window_seconds) / 3600.0

    mismatch_total_map, mismatch_total_reset = _aggregate_metric_over_series(
        series=series,
        metric_name="rg_shadow_decision_mismatch_total",
        group_labels=(),
    )
    mismatch_total = float(mismatch_total_map.get((), 0.0))

    mismatch_by_series, mismatch_series_reset = _aggregate_metric_over_series(
        series=series,
        metric_name="rg_shadow_decision_mismatch_total",
        group_labels=("module", "route", "policy_id", "legacy", "rg"),
    )
    mismatch_items: List[Tuple[float, Dict[str, str]]] = []
    for grp, inc in sorted(mismatch_by_series.items(), key=lambda kv: kv[1], reverse=True):
        if inc <= 0:
            continue
        labels = {
            "module": grp[0] if len(grp) > 0 else "",
            "route": grp[1] if len(grp) > 1 else "",
            "policy_id": grp[2] if len(grp) > 2 else "",
            "legacy": grp[3] if len(grp) > 3 else "",
            "rg": grp[4] if len(grp) > 4 else "",
        }
        mismatch_items.append((float(inc), labels))
    mismatch_items = mismatch_items[: max(0, int(top_mismatches))]

    decisions_by_policy, decisions_reset = _aggregate_metric_over_series(
        series=series,
        metric_name="rg_decisions_total",
        group_labels=("policy_id",),
    )
    denials_by_policy_reason, denials_reset = _aggregate_metric_over_series(
        series=series,
        metric_name="rg_denials_total",
        group_labels=("policy_id", "reason"),
    )

    total_decisions = sum(float(v) for v in decisions_by_policy.values() if v > 0)
    if total_decisions > 0:
        mismatch_rate = mismatch_total / total_decisions
    elif mismatch_total <= 0:
        mismatch_rate = 0.0
    else:
        mismatch_rate = float("inf")

    seen_policy_ids = {k[0] for k, v in decisions_by_policy.items() if v > 0 and k and k[0]}
    missing_policy_ids = [p for p in expected_policy_ids if p not in seen_policy_ids]

    top_policy_items = sorted(decisions_by_policy.items(), key=lambda kv: kv[1], reverse=True)[: int(top_policies)]
    top_denial_items = sorted(denials_by_policy_reason.items(), key=lambda kv: kv[1], reverse=True)[: int(top_denials)]

    resets_detected = mismatch_total_reset or mismatch_series_reset or decisions_reset or denials_reset

    fail_reasons: List[str] = []
    if window_hours < float(min_window_hours):
        fail_reasons.append(f"window_hours={window_hours:.2f} < required={float(min_window_hours):.2f}")
    if mismatch_total > float(mismatch_threshold):
        fail_reasons.append(
            f"mismatches_increase={mismatch_total:.0f} > threshold={float(mismatch_threshold):.0f}"
        )
    if mismatch_rate > float(mismatch_rate_threshold):
        fail_reasons.append(
            f"mismatch_rate={mismatch_rate:.6f} > threshold={float(mismatch_rate_threshold):.6f}"
        )
    if missing_policy_ids and not allow_missing_coverage:
        fail_reasons.append(f"missing_policy_ids={len(missing_policy_ids)}")
    if resets_detected and not allow_resets:
        fail_reasons.append("counter_resets_detected")

    return {
        "ok": not fail_reasons,
        "paths": paths,
        "metas": metas,
        "window_seconds": window_seconds,
        "window_hours": window_hours,
        "mismatch_total": mismatch_total,
        "mismatch_rate": mismatch_rate,
        "mismatch_items": mismatch_items,
        "decisions_by_policy": decisions_by_policy,
        "top_policy_items": top_policy_items,
        "denials_by_policy_reason": denials_by_policy_reason,
        "top_denial_items": top_denial_items,
        "seen_policy_ids": seen_policy_ids,
        "missing_policy_ids": missing_policy_ids,
        "resets_detected": resets_detected,
        "fail_reasons": fail_reasons,
    }


def cmd_exercise(args: argparse.Namespace) -> int:
    """Exercise all expected RG-governed endpoints to generate decisions."""
    import subprocess

    base = args.base_url.rstrip("/")
    key = args.api_key or ""
    headers = _headers(key, args.bearer_token)

    # Endpoints that trigger each expected policy_id
    # Format: (method, path, content_type, body, policy_id)
    endpoints = [
        ("POST", "/api/v1/auth/login", "application/x-www-form-urlencoded",
         "username=test&password=test", "authnz.default"),
        ("POST", "/api/v1/chats/", "application/json",
         '{"character_id":1,"title":"rg-test"}', "character_chat.default"),
        ("POST", "/api/v1/chat/completions", "application/json",
         '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"hi"}],"max_tokens":1}',
         "chat.default"),
        ("POST", "/api/v1/embeddings", "application/json",
         '{"input":"test","model":"text-embedding-ada-002"}', "embeddings.default"),
        ("GET", "/api/v1/audio/voices/catalog", None, None, "audio.default"),
        ("GET", "/api/v1/evaluations/templates", None, None, "evals.default"),
        ("GET", "/api/v1/media/items", None, None, "media.default"),
        ("GET", "/api/v1/workflows/templates", None, None, "workflows.default"),
        ("GET", "/api/v1/rag/health", None, None, "rag.default"),
    ]

    print(f"Exercising {len(endpoints)} endpoints to trigger RG decisions...")
    print(f"Base URL: {base}")
    print()

    for method, path, content_type, body, policy in endpoints:
        url = f"{base}{path}"
        cmd = ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-X", method]
        if key:
            cmd.extend(["-H", f"X-API-KEY: {key}"])
        if args.bearer_token:
            cmd.extend(["-H", f"Authorization: Bearer {args.bearer_token}"])
        if content_type:
            cmd.extend(["-H", f"Content-Type: {content_type}"])
        if body:
            cmd.extend(["-d", body])
        cmd.append(url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=float(args.timeout))
            status = result.stdout.strip()
        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
        except Exception as e:
            status = f"ERROR: {e}"

        print(f"[{policy:25s}] {method:4s} {path:40s} → HTTP {status}")

    print()
    print("Done. Take a snapshot now to capture the RG decisions.")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    before_path = Path(args.before)
    after_path = Path(args.after)
    if not before_path.exists():
        print(f"--before not found: {before_path}", file=sys.stderr)
        return 2
    if not after_path.exists():
        print(f"--after not found: {after_path}", file=sys.stderr)
        return 2

    before_text = _load_text_file(before_path)
    after_text = _load_text_file(after_path)
    before = parse_prometheus_text(before_text)
    after = parse_prometheus_text(after_text)

    expected = list(DEFAULT_EXPECTED_POLICY_IDS)
    if args.expected_policy_id:
        expected = list(args.expected_policy_id)

    mismatch_total_map, mismatch_total_reset = _sum_increases_by(
        before=before,
        after=after,
        metric_name="rg_shadow_decision_mismatch_total",
        group_labels=(),
    )
    mismatch_items, mismatch_reset = _top_increases(
        before=before,
        after=after,
        metric_name="rg_shadow_decision_mismatch_total",
        top_n=int(args.top_mismatches),
    )
    mismatch_total = float(mismatch_total_map.get((), 0.0))
    mismatch_reset = mismatch_reset or mismatch_total_reset

    decisions_by_policy, decisions_reset = _sum_increases_by(
        before=before,
        after=after,
        metric_name="rg_decisions_total",
        group_labels=("policy_id",),
    )
    denials_by_policy_reason, denials_reset = _sum_increases_by(
        before=before,
        after=after,
        metric_name="rg_denials_total",
        group_labels=("policy_id", "reason"),
    )

    seen_policy_ids = {k[0] for k, v in decisions_by_policy.items() if v > 0 and k and k[0]}
    missing_policy_ids = [p for p in expected if p not in seen_policy_ids]

    mismatch_threshold = float(args.mismatch_threshold)
    allow_resets = bool(args.allow_resets)
    allow_missing_coverage = bool(args.allow_missing_coverage)

    resets_detected = mismatch_reset or decisions_reset or denials_reset

    fail_reasons: List[str] = []
    if mismatch_total > mismatch_threshold:
        fail_reasons.append(f"mismatches_increase={mismatch_total:.0f} > threshold={mismatch_threshold:.0f}")
    if missing_policy_ids and not allow_missing_coverage:
        fail_reasons.append(f"missing_policy_ids={len(missing_policy_ids)}")
    if resets_detected and not allow_resets:
        fail_reasons.append("counter_resets_detected")

    ok = not fail_reasons

    before_meta = _maybe_read_meta(before_path)
    after_meta = _maybe_read_meta(after_path)

    def _fmt_ts(meta: Optional[SnapshotMeta]) -> str:
        if not meta or not meta.captured_at_unix:
            return "unknown"
        return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(meta.captured_at_unix))

    # Console report
    print("Stage 9A parity report (RG metrics)")
    print(f"- before: {before_path} ({_fmt_ts(before_meta)})")
    print(f"- after:  {after_path} ({_fmt_ts(after_meta)})")
    if after_meta and after_meta.rg_policy_version is not None:
        print(
            f"- rg_policy_version={after_meta.rg_policy_version} store={after_meta.rg_policy_store} "
            f"policies={after_meta.rg_policy_count}"
        )
    if resets_detected:
        print("- WARNING: counter resets detected between snapshots; deltas may be unreliable")

    print(f"\nrg_shadow_decision_mismatch_total increase: {mismatch_total:.0f}")
    if mismatch_items:
        for inc, labels in mismatch_items:
            print(f"  +{inc:.0f}  {_format_kv(labels, ('module', 'route', 'policy_id', 'legacy', 'rg'))}")

    # Decisions by policy_id (top N)
    top_pols = sorted(decisions_by_policy.items(), key=lambda kv: kv[1], reverse=True)[: int(args.top_policies)]
    print("\nrg_decisions_total increase by policy_id:")
    for (policy_id,), inc in top_pols:
        print(f"  {policy_id or '<missing>'}: {inc:.0f}")
    if missing_policy_ids:
        print("\nMissing expected policy_ids (no decisions observed):")
        for p in missing_policy_ids:
            print(f"  - {p}")

    # Denials summary (top N)
    top_den = sorted(denials_by_policy_reason.items(), key=lambda kv: kv[1], reverse=True)[: int(args.top_denials)]
    if top_den:
        print("\nrg_denials_total increase (top):")
        for (policy_id, reason), inc in top_den:
            print(f"  {policy_id or '<missing>'} reason={reason or '<missing>'}: {inc:.0f}")

    if ok:
        print("\nRESULT: PASS")
    else:
        print("\nRESULT: FAIL (" + "; ".join(fail_reasons) + ")")

    # Optional markdown report
    if args.out_md:
        md_lines: List[str] = []
        md_lines.append("# Stage 9A RG Parity Report (Staging/Dev)")
        md_lines.append("")
        md_lines.append(f"- Before: `{before_path}` ({_fmt_ts(before_meta)})")
        md_lines.append(f"- After: `{after_path}` ({_fmt_ts(after_meta)})")
        if after_meta and after_meta.rg_policy_version is not None:
            md_lines.append(
                f"- RG policy: version={after_meta.rg_policy_version} store={after_meta.rg_policy_store} "
                f"policies={after_meta.rg_policy_count}"
            )
        if resets_detected:
            md_lines.append("- WARNING: counter resets detected between snapshots; deltas may be unreliable")
        md_lines.append("")

        md_lines.append("## Shadow mismatches")
        md_lines.append(f"- `rg_shadow_decision_mismatch_total` increase: **{mismatch_total:.0f}**")
        if mismatch_items:
            md_lines.append("")
            md_lines.append("Top mismatches:")
            for inc, labels in mismatch_items:
                md_lines.append(f"- +{inc:.0f} `{_format_kv(labels, ('module', 'route', 'policy_id', 'legacy', 'rg'))}`")
        md_lines.append("")

        md_lines.append("## Coverage (policy_id)")
        md_lines.append("Observed policy_ids (decisions increase > 0):")
        for p in sorted(seen_policy_ids):
            md_lines.append(f"- `{p}`")
        if missing_policy_ids:
            md_lines.append("")
            md_lines.append("Missing expected policy_ids:")
            for p in missing_policy_ids:
                md_lines.append(f"- `{p}`")
        md_lines.append("")

        md_lines.append("## Decisions")
        for (policy_id,), inc in top_pols:
            md_lines.append(f"- `{policy_id or '<missing>'}`: {inc:.0f}")
        md_lines.append("")

        if top_den:
            md_lines.append("## Denials (top)")
            for (policy_id, reason), inc in top_den:
                md_lines.append(f"- `{policy_id or '<missing>'}` reason=`{reason or '<missing>'}`: {inc:.0f}")
            md_lines.append("")

        md_lines.append("## Result")
        md_lines.append(f"- {'PASS' if ok else 'FAIL'}")
        if fail_reasons:
            md_lines.append("- Reasons: " + "; ".join(f"`{r}`" for r in fail_reasons))

        _write_markdown_report(Path(args.out_md), md_lines)
        print(f"\nWrote markdown report: {args.out_md}")

    return 0 if ok else 3


def cmd_release_window_report(args: argparse.Namespace) -> int:
    pattern = str(args.snapshots_glob or "").strip()
    if not pattern:
        print("--snapshots-glob is required", file=sys.stderr)
        return 2

    paths = [Path(p) for p in glob.glob(pattern)]
    paths = [p for p in paths if p.suffix == ".prom" and p.exists()]
    if len(paths) < 2:
        print(
            f"Need at least two .prom snapshots for release-window report, found {len(paths)} for pattern: {pattern}",
            file=sys.stderr,
        )
        return 2

    snapshots: List[Tuple[Path, Optional[SnapshotMeta], Dict[SampleKey, float]]] = []
    for path in paths:
        text = _load_text_file(path)
        snapshots.append((path, _maybe_read_meta(path), parse_prometheus_text(text)))

    expected = list(DEFAULT_EXPECTED_POLICY_IDS)
    if args.expected_policy_id:
        expected = list(args.expected_policy_id)

    result = _analyze_release_window(
        snapshots=snapshots,
        expected_policy_ids=expected,
        min_window_hours=float(args.min_window_hours),
        mismatch_threshold=float(args.mismatch_threshold),
        mismatch_rate_threshold=float(args.mismatch_rate_threshold),
        allow_resets=bool(args.allow_resets),
        allow_missing_coverage=bool(args.allow_missing_coverage),
        top_mismatches=int(args.top_mismatches),
        top_policies=int(args.top_policies),
        top_denials=int(args.top_denials),
    )

    def _fmt_ts(meta: Optional[SnapshotMeta], path: Path) -> str:
        epoch = _snapshot_epoch(path, meta)
        if not epoch:
            return "unknown"
        return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(epoch))

    ordered_paths: List[Path] = list(result["paths"])
    ordered_metas: List[Optional[SnapshotMeta]] = list(result["metas"])
    first_path = ordered_paths[0]
    first_meta = ordered_metas[0]
    last_path = ordered_paths[-1]
    last_meta = ordered_metas[-1]

    print("Stage 5 release-window gate report (RG metrics)")
    print(f"- snapshots: {len(ordered_paths)}")
    print(f"- first: {first_path} ({_fmt_ts(first_meta, first_path)})")
    print(f"- last:  {last_path} ({_fmt_ts(last_meta, last_path)})")
    print(f"- window_hours: {float(result['window_hours']):.2f}")
    if last_meta and last_meta.rg_policy_version is not None:
        print(
            f"- rg_policy_version={last_meta.rg_policy_version} store={last_meta.rg_policy_store} "
            f"policies={last_meta.rg_policy_count}"
        )
    if result["resets_detected"]:
        print("- WARNING: counter resets detected across snapshots")

    print("")
    print(
        "Shadow mismatch: total_increase={:.0f}, mismatch_rate={:.6f}".format(
            float(result["mismatch_total"]),
            float(result["mismatch_rate"]),
        )
    )
    mismatch_items: List[Tuple[float, Dict[str, str]]] = list(result["mismatch_items"])
    for inc, labels in mismatch_items:
        print(f"  +{inc:.0f}  {_format_kv(labels, ('module', 'route', 'policy_id', 'legacy', 'rg'))}")

    print("\nCoverage (rg_decisions_total by policy_id):")
    for (policy_id,), inc in list(result["top_policy_items"]):
        print(f"  {policy_id or '<missing>'}: {inc:.0f}")
    missing_policy_ids: List[str] = list(result["missing_policy_ids"])
    if missing_policy_ids:
        print("\nMissing expected policy_ids:")
        for policy_id in missing_policy_ids:
            print(f"  - {policy_id}")

    top_denials: List[Tuple[Tuple[str, str], float]] = list(result["top_denial_items"])
    if top_denials:
        print("\nDenials (rg_denials_total top):")
        for (policy_id, reason), inc in top_denials:
            print(f"  {policy_id or '<missing>'} reason={reason or '<missing>'}: {inc:.0f}")

    if result["ok"]:
        print("\nRESULT: PASS")
    else:
        print("\nRESULT: FAIL (" + "; ".join(result["fail_reasons"]) + ")")

    if args.out_md:
        md_lines: List[str] = []
        md_lines.append("# Stage 5 Release-Window RG Gate Report")
        md_lines.append("")
        md_lines.append(f"- Snapshots analyzed: **{len(ordered_paths)}**")
        md_lines.append(f"- First snapshot: `{first_path}` ({_fmt_ts(first_meta, first_path)})")
        md_lines.append(f"- Last snapshot: `{last_path}` ({_fmt_ts(last_meta, last_path)})")
        md_lines.append(f"- Window hours: **{float(result['window_hours']):.2f}**")
        if last_meta and last_meta.rg_policy_version is not None:
            md_lines.append(
                f"- RG policy: version={last_meta.rg_policy_version} store={last_meta.rg_policy_store} "
                f"policies={last_meta.rg_policy_count}"
            )
        if result["resets_detected"]:
            md_lines.append("- WARNING: counter resets detected across snapshots")
        md_lines.append("")
        md_lines.append("## Shadow mismatch")
        md_lines.append(f"- `rg_shadow_decision_mismatch_total` increase: **{float(result['mismatch_total']):.0f}**")
        md_lines.append(f"- Mismatch rate: **{float(result['mismatch_rate']):.6f}**")
        if mismatch_items:
            md_lines.append("")
            md_lines.append("Top mismatch series:")
            for inc, labels in mismatch_items:
                md_lines.append(f"- +{inc:.0f} `{_format_kv(labels, ('module', 'route', 'policy_id', 'legacy', 'rg'))}`")
        md_lines.append("")
        md_lines.append("## Coverage")
        for (policy_id,), inc in list(result["top_policy_items"]):
            md_lines.append(f"- `{policy_id or '<missing>'}`: {inc:.0f}")
        if missing_policy_ids:
            md_lines.append("")
            md_lines.append("Missing expected policy_ids:")
            for policy_id in missing_policy_ids:
                md_lines.append(f"- `{policy_id}`")
        md_lines.append("")
        if top_denials:
            md_lines.append("## Denials")
            for (policy_id, reason), inc in top_denials:
                md_lines.append(f"- `{policy_id or '<missing>'}` reason=`{reason or '<missing>'}`: {inc:.0f}")
            md_lines.append("")
        md_lines.append("## Result")
        md_lines.append(f"- {'PASS' if result['ok'] else 'FAIL'}")
        if result["fail_reasons"]:
            md_lines.append("- Reasons: " + "; ".join(f"`{r}`" for r in result["fail_reasons"]))
        _write_markdown_report(Path(args.out_md), md_lines)
        print(f"\nWrote markdown report: {args.out_md}")

    return 0 if result["ok"] else 3


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Stage 9A helper: snapshot metrics and report RG parity deltas")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="Fetch metrics endpoint and write a .prom snapshot (+ .meta.json)")
    s.add_argument("--base-url", default="http://127.0.0.1:8000", help="Server base URL")
    s.add_argument("--metrics-path", default="/metrics", help="Prometheus text endpoint path")
    s.add_argument("--health-path", default="/api/v1/health", help="Health endpoint path (set empty to disable)")
    s.add_argument("--api-key", default=None, help="X-API-KEY for single-user mode (if required)")
    s.add_argument("--bearer-token", default=None, help="Authorization: Bearer <token> (if required)")
    s.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    s.add_argument("--out", required=True, help="Output .prom file path (suffix added if missing)")
    s.set_defaults(func=cmd_snapshot)

    e = sub.add_parser("exercise", help="Exercise all expected RG-governed endpoints to generate decisions")
    e.add_argument("--base-url", default="http://127.0.0.1:8000", help="Server base URL")
    e.add_argument("--api-key", default=None, help="X-API-KEY for single-user mode (if required)")
    e.add_argument("--bearer-token", default=None, help="Authorization: Bearer <token> (if required)")
    e.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds per request")
    e.set_defaults(func=cmd_exercise)

    r = sub.add_parser("report", help="Diff two snapshots and report RG parity deltas")
    r.add_argument("--before", required=True, help="Before snapshot .prom")
    r.add_argument("--after", required=True, help="After snapshot .prom")
    r.add_argument(
        "--expected-policy-id",
        action="append",
        default=None,
        help="Expected policy_id (repeatable). Defaults to a core staging checklist set.",
    )
    r.add_argument("--mismatch-threshold", type=float, default=0.0, help="Allowed mismatch increase (default 0)")
    r.add_argument("--allow-missing-coverage", action="store_true", help="Do not fail on missing expected coverage")
    r.add_argument("--allow-resets", action="store_true", help="Do not fail if counter resets are detected")
    r.add_argument("--top-mismatches", type=int, default=20, help="Max mismatch series to display")
    r.add_argument("--top-policies", type=int, default=20, help="Max policy_ids to display for decisions")
    r.add_argument("--top-denials", type=int, default=20, help="Max denial series to display")
    r.add_argument("--out-md", default=None, help="Write a markdown report to this path")
    r.set_defaults(func=cmd_report)

    w = sub.add_parser(
        "release-window-report",
        help="Evaluate Stage 5 release-window gate using a series of snapshots",
    )
    w.add_argument(
        "--snapshots-glob",
        required=True,
        help="Glob pattern for snapshot .prom files (example: 'stage9a_window/*.prom')",
    )
    w.add_argument(
        "--expected-policy-id",
        action="append",
        default=None,
        help="Expected policy_id (repeatable). Defaults to a core staging checklist set.",
    )
    w.add_argument(
        "--min-window-hours",
        type=float,
        default=168.0,
        help="Minimum required observation window in hours (default 168 = 7 days)",
    )
    w.add_argument(
        "--mismatch-threshold",
        type=float,
        default=0.0,
        help="Allowed absolute mismatch increase across the window (default 0)",
    )
    w.add_argument(
        "--mismatch-rate-threshold",
        type=float,
        default=0.01,
        help="Allowed mismatch rate across window (default 0.01 = 1%%)",
    )
    w.add_argument("--allow-missing-coverage", action="store_true", help="Do not fail on missing expected coverage")
    w.add_argument("--allow-resets", action="store_true", help="Do not fail if counter resets are detected")
    w.add_argument("--top-mismatches", type=int, default=20, help="Max mismatch series to display")
    w.add_argument("--top-policies", type=int, default=20, help="Max policy_ids to display for decisions")
    w.add_argument("--top-denials", type=int, default=20, help="Max denial series to display")
    w.add_argument("--out-md", default=None, help="Write a markdown report to this path")
    w.set_defaults(func=cmd_release_window_report)

    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
