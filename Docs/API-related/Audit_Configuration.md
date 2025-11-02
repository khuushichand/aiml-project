Audit Configuration and Tuning
==============================

Overview
--------
The Unified Audit Service supports runtime tuning via settings to control
PII detection, risk scoring, and high-risk operation sensitivity. This
document summarizes the knobs and provides practical examples.

Settings Reference
------------------

- AUDIT_PII_PATTERNS
  - Type: dict[str, str | list[str]]
  - Purpose: Add or override regex patterns for PII detection.
  - Example:
    - Python: `settings["AUDIT_PII_PATTERNS"] = {"custom": r"HELLO\\d{3}"}`
    - .env (JSON): `AUDIT_PII_PATTERNS={"custom":"HELLO\\d{3}"}`

- AUDIT_PII_SCAN_FIELDS
  - Type: list[str] or comma-separated str
  - Purpose: Extra string fields to scan/redact outside of metadata.
    Accepts event field names (e.g., `error_message`) or `context_` prefixed
    context fields (e.g., `context_endpoint`, `context_user_agent`).
  - Example:
    - Python: `settings["AUDIT_PII_SCAN_FIELDS"] = ["error_message", "context_endpoint"]`
    - .env: `AUDIT_PII_SCAN_FIELDS=error_message,context_endpoint`

- AUDIT_ACTION_RISK_BONUS
  - Type: dict[str, int]
  - Purpose: Increase risk score for specific action labels.
  - Defaults: `{ "sla_breached": 10, "quarantined": 10, "unauthorized_access": 10 }`
  - Example:
    - Python: `settings["AUDIT_ACTION_RISK_BONUS"] = {"bulk_delete": 15}`
    - .env (JSON): `AUDIT_ACTION_RISK_BONUS={"bulk_delete":15}`

- AUDIT_HIGH_RISK_OPERATIONS
  - Type: list[str] or comma-separated str
  - Purpose: Words/verbs that, when present in `event.action` (case-insensitive
    substring), add +30 to the risk score.
  - Default set includes: delete, drop, truncate, export, download,
    change_password, reset_password, grant, revoke, modify_permissions,
    create_admin, delete_user
  - Example:
    - Python: `settings["AUDIT_HIGH_RISK_OPERATIONS"] = ["purge", "wipe"]`
    - .env: `AUDIT_HIGH_RISK_OPERATIONS=purge,wipe`

- AUDIT_SUSPICIOUS_THRESHOLDS
  - Type: dict[str, int | bool]
  - Purpose: Thresholds and toggles for suspicious activity contributions.
  - Defaults:
    - `failed_auth` (int): 3  → +20 if `metadata.consecutive_failures` > 3
    - `data_export` (int): 1000 → +15 if `result_count` > 1000
    - `after_hours` (bool): true → +10 when hour < 6 or hour > 22
    - `rapid_requests` (int): 100 (reserved for future use)
    - `unusual_location` (bool): true (reserved for future use)
  - Example:
    - Python: `settings["AUDIT_SUSPICIOUS_THRESHOLDS"] = {"data_export": 50, "failed_auth": 2, "after_hours": false}`
    - .env (JSON): `AUDIT_SUSPICIOUS_THRESHOLDS={"data_export":50,"failed_auth":2,"after_hours":false}`

- AUDIT_HIGH_RISK_SCORE
  - Type: int
  - Purpose: Threshold used to classify an event as “high risk” for stats and early flushes.
  - Default: 70
  - Example: `.env: AUDIT_HIGH_RISK_SCORE=80`

Notes
-----
- Settings are read via the project’s `settings` mapping (LazySettings). They can be set in `.env` or programmatically in tests.
- For PII, redaction places `[{TYPE}_REDACTED]` placeholders in strings while preserving metadata structure (dict/list) where possible.
- Risk scoring is additive and capped at 100. Time-of-day and weekend bonuses are separate.
- High-risk operations match `event.action` by case-insensitive substring (e.g., `"PurGe_old"` matches `"purge"`).

Quick Examples
--------------
Python (at startup or in tests):

```python
from tldw_Server_API.app.core.config import settings

settings["AUDIT_PII_PATTERNS"] = {"api_secret": r"sec_[A-Za-z0-9]{24}"}
settings["AUDIT_PII_SCAN_FIELDS"] = ["error_message", "context_endpoint"]
settings["AUDIT_ACTION_RISK_BONUS"] = {"bulk_delete": 20}
settings["AUDIT_HIGH_RISK_OPERATIONS"] = ["purge", "wipe"]
settings["AUDIT_SUSPICIOUS_THRESHOLDS"] = {"data_export": 50, "failed_auth": 2, "after_hours": False}
```

.env (JSON values quoted):

```
AUDIT_PII_PATTERNS={"api_secret":"sec_[A-Za-z0-9]{24}"}
AUDIT_PII_SCAN_FIELDS=error_message,context_endpoint
AUDIT_ACTION_RISK_BONUS={"bulk_delete":20}
AUDIT_HIGH_RISK_OPERATIONS=purge,wipe
AUDIT_SUSPICIOUS_THRESHOLDS={"data_export":50,"failed_auth":2,"after_hours":false}
AUDIT_HIGH_RISK_SCORE=80
```
