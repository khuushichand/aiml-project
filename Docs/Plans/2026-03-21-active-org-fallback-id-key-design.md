# Active Org Fallback `id` Key Design

## Goal

Fix `get_active_org_id()` so it can resolve the first organization when `get_user_orgs()` returns rows keyed by `id` instead of `org_id`.

## Problem

The current OSS fallback logic only reads `user_orgs[0]["org_id"]`. Some org-list call sites and serialized rows can use `id` instead. In that case, `get_active_org_id()` incorrectly returns `None` even though the user has organizations.

## Options

1. Keep `org_id` only and normalize all callers upstream.
   This is brittle and pushes the bug outward.

2. Accept both `org_id` and `id` in the fallback path.
   This is the smallest and safest fix. It matches the private hosted fix and keeps the helper tolerant of the current row shapes.

Recommendation: option 2.

## Design

Change only the fallback branch in `tldw_Server_API/app/api/v1/API_Deps/org_deps.py`:

- read `user_orgs[0].get("org_id") or user_orgs[0].get("id")`
- if either exists, return it as `int`
- otherwise keep returning `None`

## Testing

Add a regression test in `tldw_Server_API/tests/AuthNZ_Unit/test_org_deps.py` that:

- stubs `get_user_orgs()` to return `[{\"id\": 321}]`
- calls `get_active_org_id()` without explicit org inputs
- proves the current code fails before the fix
- proves it returns `321` after the fix
