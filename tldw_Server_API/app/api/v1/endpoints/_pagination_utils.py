from __future__ import annotations

"""
Reusable helpers for building RFC5988 Link headers for paginated endpoints.

This module is intentionally lightweight and dependency-free, so it can be
used across endpoints (e.g., runs, events, future artifacts listings).
"""

from typing import List, Optional, Tuple

import urllib.parse as _u


def build_link_header(
    base_path: str,
    common_params: List[Tuple[str, str]] | None = None,
    *,
    next_cursor: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    has_more: Optional[bool] = None,
    cursor_param: str = "cursor",
    include_first_last: bool = True,
) -> Optional[str]:
    """Build an RFC5988 Link header string for pagination.

    - Cursor mode: when `next_cursor` is provided, returns a `rel="next"` link using
      the given `cursor_param`. If `limit` is provided it is included as a query param.
    - Offset mode: when `limit` and `offset` are provided, returns `rel="next"`,
      `rel="prev"`, and when `include_first_last=True`, `rel="first"` (offset=0)
      and a best-effort `rel="last"` when `has_more is False`.

    The helper is tolerant and will only include links it can build from provided inputs.
    Returns a comma-separated Link header value or None if no links are applicable.

    Example (cursor-based):
        >>> build_link_header(
        ...     base_path="/api/v1/workflows/runs",
        ...     common_params=[("status", "running"), ("order_by", "created_at")],
        ...     next_cursor="abc123",
        ...     limit=25,
        ... )
        '</api/v1/workflows/runs?status=running&order_by=created_at&limit=25&cursor=abc123>; rel="next"'

    Example (offset-based):
        >>> build_link_header(
        ...     base_path="/api/v1/workflows/runs",
        ...     common_params=[("status", "running")],
        ...     limit=25,
        ...     offset=50,
        ...     has_more=True,
        ... )
        '</api/v1/workflows/runs?status=running&limit=25&offset=75>; rel="next", '
        '</api/v1/workflows/runs?status=running&limit=25&offset=25>; rel="prev", '
        '</api/v1/workflows/runs?status=running&limit=25&offset=0>; rel="first"'
    """
    params_common: List[Tuple[str, str]] = list(common_params or [])
    links: List[str] = []

    # Cursor-based next link
    if next_cursor:
        q = params_common + [("limit", str(limit))] if limit is not None else list(params_common)
        q.append((cursor_param, next_cursor))
        href = base_path + "?" + _u.urlencode(q, doseq=True)
        links.append(f"<{href}>; rel=\"next\"")

    # Offset-based links
    if limit is not None and offset is not None:
        # Next
        if has_more:
            qn = params_common + [("limit", str(limit)), ("offset", str(int(offset) + int(limit)))]
            hrefn = base_path + "?" + _u.urlencode(qn, doseq=True)
            links.append(f"<{hrefn}>; rel=\"next\"")
        # Prev
        if int(offset) > 0:
            prev_off = max(0, int(offset) - int(limit))
            qp = params_common + [("limit", str(limit)), ("offset", str(prev_off))]
            hrefp = base_path + "?" + _u.urlencode(qp, doseq=True)
            links.append(f"<{hrefp}>; rel=\"prev\"")
        # First/Last (best-effort)
        if include_first_last:
            qf = params_common + [("limit", str(limit)), ("offset", "0")]
            hreff = base_path + "?" + _u.urlencode(qf, doseq=True)
            links.append(f"<{hreff}>; rel=\"first\"")
            # We don't know total; treat current page as last when not has_more
            if has_more is False:
                ql = params_common + [("limit", str(limit)), ("offset", str(offset))]
                hrefl = base_path + "?" + _u.urlencode(ql, doseq=True)
                links.append(f"<{hrefl}>; rel=\"last\"")

    return ", ".join(links) if links else None


__all__ = ["build_link_header"]
