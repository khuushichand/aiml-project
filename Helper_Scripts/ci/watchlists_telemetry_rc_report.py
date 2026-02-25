"""Generate Watchlists RC telemetry report (reporting-only threshold policy)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASELINE_JSON = Path("Docs") / "Plans" / "watchlists_ux_stage1_telemetry_export_summary_2026_02_23.json"
DEFAULT_SUMMARY_OUTPUT = Path("tmp") / "watchlists_telemetry_rc_report_summary.md"
DEFAULT_JSON_OUTPUT = Path("tmp") / "watchlists_telemetry_rc_report.json"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 20.0

FALLBACK_BASELINE = {
    "uc1_f1_first_source_setup_percent": 92.96,
    "uc1_f2_time_to_first_review_seconds": 567.49,
    "uc2_f2_text_output_success_percent": 0.06,
    "uc2_f3_audio_output_success_percent": 0.03,
}


def _build_run_url_from_env() -> str:
    explicit_url = os.environ.get("GITHUB_RUN_URL")
    if explicit_url:
        return explicit_url
    server_url = os.environ.get("GITHUB_SERVER_URL", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if server_url and repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return "n/a"


def collect_metadata() -> dict[str, str]:
    return {
        "ref": os.environ.get("GITHUB_REF", "local"),
        "sha": os.environ.get("GITHUB_SHA", "local"),
        "run_url": _build_run_url_from_env(),
        "generated_at_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
    }


def load_baseline_metrics(baseline_json_path: Path) -> dict[str, float]:
    if not baseline_json_path.exists():
        return dict(FALLBACK_BASELINE)
    payload = json.loads(baseline_json_path.read_text(encoding="utf-8"))
    funnel_metrics = payload.get("funnel_metrics", {}) if isinstance(payload, dict) else {}
    try:
        return {
            "uc1_f1_first_source_setup_percent": float(
                funnel_metrics.get("UC1_F1_first_source_setup", {}).get("percent", FALLBACK_BASELINE["uc1_f1_first_source_setup_percent"])
            ),
            "uc1_f2_time_to_first_review_seconds": float(
                funnel_metrics.get("UC1_F2_time_to_first_review", {}).get("median_seconds", FALLBACK_BASELINE["uc1_f2_time_to_first_review_seconds"])
            ),
            "uc2_f2_text_output_success_percent": float(
                funnel_metrics.get("UC2_F2_text_output_success", {}).get("percent", FALLBACK_BASELINE["uc2_f2_text_output_success_percent"])
            ),
            "uc2_f3_audio_output_success_percent": float(
                funnel_metrics.get("UC2_F3_audio_output_success", {}).get("percent", FALLBACK_BASELINE["uc2_f3_audio_output_success_percent"])
            ),
        }
    except (TypeError, ValueError):
        return dict(FALLBACK_BASELINE)


def fetch_rc_summary(*, api_base_url: str, api_key: str | None, timeout_seconds: float) -> dict[str, Any]:
    base = api_base_url.rstrip("/")
    url = f"{base}/api/v1/watchlists/telemetry/rc-summary"
    params = {}
    since = os.environ.get("WATCHLISTS_RC_SINCE")
    until = os.environ.get("WATCHLISTS_RC_UNTIL")
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    if params:
        url = f"{url}?{urlencode(params)}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    req = Request(url=url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as response:  # nosec B310
            body = response.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        raise RuntimeError(f"http_error:{exc.code}:{body}") from exc
    except URLError as exc:
        raise RuntimeError(f"url_error:{exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_json:{exc}") from exc


def _to_percent(rate_value: Any) -> float:
    try:
        return float(rate_value) * 100.0
    except (TypeError, ValueError):
        return 0.0


def evaluate_thresholds(*, rc_payload: dict[str, Any], baseline: dict[str, float]) -> list[dict[str, Any]]:
    onboarding = rc_payload.get("onboarding", {}) if isinstance(rc_payload, dict) else {}
    onboarding_rates = onboarding.get("rates", {}) if isinstance(onboarding, dict) else {}
    onboarding_timings = onboarding.get("timings", {}) if isinstance(onboarding, dict) else {}
    uc2_backend = rc_payload.get("uc2_backend", {}) if isinstance(rc_payload, dict) else {}

    setup_percent = _to_percent(onboarding_rates.get("setup_completion_rate"))
    setup_baseline = float(baseline.get("uc1_f1_first_source_setup_percent", FALLBACK_BASELINE["uc1_f1_first_source_setup_percent"]))
    setup_delta = setup_percent - setup_baseline
    setup_status = "potential_breach" if setup_delta <= -10.0 else "ok"

    first_output_percent = _to_percent(uc2_backend.get("first_output_success_rate"))
    first_output_baseline = float(baseline.get("uc2_f2_text_output_success_percent", FALLBACK_BASELINE["uc2_f2_text_output_success_percent"]))
    first_output_delta = first_output_percent - first_output_baseline
    # Preserve the 10pp reporting threshold while still surfacing catastrophic
    # regressions where RC has zero first-output success against a non-zero baseline.
    first_output_status = (
        "potential_breach"
        if first_output_delta <= -10.0 or (first_output_baseline > 0.0 and first_output_percent <= 0.0)
        else "ok"
    )

    median_first_output_seconds = float(onboarding_timings.get("median_seconds_to_first_output_success") or 0.0)
    median_baseline_seconds = float(
        baseline.get("uc1_f2_time_to_first_review_seconds", FALLBACK_BASELINE["uc1_f2_time_to_first_review_seconds"])
    )
    median_status = (
        "potential_breach"
        if median_baseline_seconds > 0
        and median_first_output_seconds > 0
        and median_first_output_seconds >= (median_baseline_seconds * 1.25)
        else "ok"
    )
    median_delta = median_first_output_seconds - median_baseline_seconds

    return [
        {
            "id": "setup_completion_drop_10pp",
            "label": "Setup completion drop >= 10pp vs baseline",
            "status": setup_status,
            "metric_value": setup_percent,
            "baseline_value": setup_baseline,
            "delta": setup_delta,
            "reporting_only": True,
        },
        {
            "id": "first_output_success_drop_10pp",
            "label": "First output success drop >= 10pp vs baseline",
            "status": first_output_status,
            "metric_value": first_output_percent,
            "baseline_value": first_output_baseline,
            "delta": first_output_delta,
            "reporting_only": True,
        },
        {
            "id": "median_first_output_regression_25pct",
            "label": "Median first-output timing regression >=25% vs baseline",
            "status": median_status,
            "metric_value": median_first_output_seconds,
            "baseline_value": median_baseline_seconds,
            "delta": median_delta,
            "reporting_only": True,
        },
    ]


def determine_decision(*, thresholds: list[dict[str, Any]], operational_error: str | None) -> str:
    if operational_error:
        return "OPERATIONAL_FAILURE"
    if any(str(item.get("status")) == "potential_breach" for item in thresholds):
        return "REPORT_ONLY_POTENTIAL_BREACH"
    return "REPORT_ONLY_OK"


def decision_exit_code(decision: str) -> int:
    return 1 if decision == "OPERATIONAL_FAILURE" else 0


def build_summary_markdown(
    *,
    metadata: dict[str, str],
    decision: str,
    thresholds: list[dict[str, Any]],
    operational_error: str | None,
) -> str:
    lines: list[str] = []
    lines.append("## Watchlists Telemetry RC Report")
    lines.append("")
    lines.append(f"- Ref: `{metadata.get('ref', 'n/a')}`")
    lines.append(f"- SHA: `{metadata.get('sha', 'n/a')}`")
    lines.append(f"- Run URL: {metadata.get('run_url', 'n/a')}")
    lines.append(f"- Generated (UTC): `{metadata.get('generated_at_utc', 'n/a')}`")
    lines.append("- Policy: reporting-only thresholds (breaches do not fail RC workflow)")
    lines.append("")
    lines.append("| Threshold | Status | Metric | Baseline | Delta |")
    lines.append("|---|---|---:|---:|---:|")
    for threshold in thresholds:
        metric = float(threshold.get("metric_value") or 0.0)
        baseline = float(threshold.get("baseline_value") or 0.0)
        delta = float(threshold.get("delta") or 0.0)
        lines.append(
            f"| {threshold.get('id', 'unknown')} | {threshold.get('status', 'unknown')} | {metric:.2f} | {baseline:.2f} | {delta:.2f} |"
        )
    lines.append("")
    lines.append(f"### Decision: {decision}")
    if operational_error:
        lines.append("")
        lines.append(f"Operational error: `{operational_error}`")
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Watchlists RC telemetry markdown report.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--api-key", default=os.environ.get("SINGLE_USER_API_KEY", ""))
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--baseline-json", default=str(DEFAULT_BASELINE_JSON))
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_OUTPUT))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    metadata = collect_metadata()
    baseline_path = Path(args.baseline_json)
    summary_output = Path(args.summary_output)
    json_output = Path(args.json_output)

    baseline = load_baseline_metrics(baseline_path)
    rc_payload: dict[str, Any] | None = None
    thresholds: list[dict[str, Any]] = []
    operational_error: str | None = None

    try:
        rc_payload = fetch_rc_summary(
            api_base_url=args.api_base_url,
            api_key=args.api_key or None,
            timeout_seconds=float(args.timeout_seconds),
        )
        thresholds = evaluate_thresholds(rc_payload=rc_payload, baseline=baseline)
    except Exception as exc:  # noqa: BLE001
        operational_error = str(exc)

    decision = determine_decision(thresholds=thresholds, operational_error=operational_error)
    markdown = build_summary_markdown(
        metadata=metadata,
        decision=decision,
        thresholds=thresholds,
        operational_error=operational_error,
    )

    summary_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(markdown, encoding="utf-8")
    json_output.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "decision": decision,
                "operational_error": operational_error,
                "baseline": baseline,
                "thresholds": thresholds,
                "rc_payload": rc_payload,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return decision_exit_code(decision)


if __name__ == "__main__":
    raise SystemExit(main())
