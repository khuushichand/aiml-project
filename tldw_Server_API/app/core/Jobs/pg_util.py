from __future__ import annotations

from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

# Cache negotiation results per host:port signature to avoid repeated probes
_NEGOTIATED_OPTIONS_CACHE: dict[str, str] = {}


def normalize_pg_dsn(
    dsn: str,
    *,
    connect_timeout_s: int = 3,
    statement_timeout_ms: int = 5000,
    lock_timeout_ms: int = 2000,
    idle_in_xact_timeout_ms: int = 5000,
) -> str:
    """Ensure a Postgres DSN includes fast-fail connection and query timeouts.

    - Adds connect_timeout if absent
    - Adds options with statement/lock/idle_in_xact timeouts if absent
    """
    if not dsn or not dsn.strip().lower().startswith("postgres"):
        return dsn
    p = urlparse(dsn)
    q = dict(parse_qsl(p.query, keep_blank_values=True))

    if "connect_timeout" not in q:
        q["connect_timeout"] = str(int(max(1, connect_timeout_s)))

    if "options" not in q:
        # Compose options string (newest first). Use RFC3986 encoding (spaces as %20).
        opts = (
            f"-c statement_timeout={int(max(1, statement_timeout_ms))} "
            f"-c lock_timeout={int(max(1, lock_timeout_ms))} "
            f"-c idle_in_transaction_session_timeout={int(max(1, idle_in_xact_timeout_ms))}"
        )
        q["options"] = opts

    # Use RFC3986 percent-encoding (spaces as %20, not '+') for libpq compatibility
    new_query = urlencode(q, doseq=True, quote_via=quote)
    new_p = p._replace(query=new_query)
    return urlunparse(new_p)


def _replace_options(dsn: str, options: str | None) -> str:
    """Return DSN with provided libpq options string (or remove it if None)."""
    p = urlparse(dsn)
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    if options is None:
        q.pop("options", None)
    else:
        q["options"] = options
    new_query = urlencode(q, doseq=True, quote_via=quote)
    return urlunparse(p._replace(query=new_query))


def _dsn_signature(dsn: str) -> str:
    try:
        p = urlparse(dsn)
        host = p.hostname or ""
        port = p.port or 5432
        return f"{host}:{port}"
    except Exception:
        return dsn


def negotiate_pg_dsn(
    dsn: str,
    *,
    connect_timeout_s: int = 3,
    statement_timeout_ms: int = 5000,
    lock_timeout_ms: int = 2000,
    idle_in_xact_timeout_ms: int = 5000,
) -> str:
    """Normalize a Postgres DSN and, if necessary, downgrade libpq options.

    Strategy:
    - Start with normalize_pg_dsn() including statement/lock/idle_in_xact timeouts.
    - Attempt a short connection. If server rejects unknown GUCs (older versions),
      try progressively simpler options sets:
        1) statement + lock + idle_in_transaction_session_timeout
        2) statement + lock
        3) statement only
        4) no options
    - Cache the negotiated `options` per host:port to avoid repeated probes.
    - If psycopg is unavailable, return the normalized DSN.
    """
    if not dsn or not dsn.strip().lower().startswith("postgres"):
        return dsn

    base = normalize_pg_dsn(
        dsn,
        connect_timeout_s=connect_timeout_s,
        statement_timeout_ms=statement_timeout_ms,
        lock_timeout_ms=lock_timeout_ms,
        idle_in_xact_timeout_ms=idle_in_xact_timeout_ms,
    )

    sig = _dsn_signature(base)
    cached = _NEGOTIATED_OPTIONS_CACHE.get(sig)
    if cached is not None:
        return _replace_options(base, cached or None)

    try:
        import psycopg  # type: ignore
    except Exception:
        return base

    def _try_connect(test_dsn: str) -> tuple[bool, str]:
        try:
            with psycopg.connect(test_dsn) as _c:  # type: ignore
                return True, ""
        except Exception as e:  # pragma: no cover - specific to env
            return False, str(e)

    ok, err = _try_connect(base)
    if ok:
        q = dict(parse_qsl(urlparse(base).query))
        _NEGOTIATED_OPTIONS_CACHE[sig] = q.get("options", "")
        return base

    # Only attempt downgrades for GUC-related errors or server complaints
    err_lc = (err or "").lower()
    if "unrecognized configuration parameter" not in err_lc and "invalid value for parameter" not in err_lc:
        # Connectivity/auth/other error; return normalized DSN
        return base

    # Progressive fallback candidates
    opts_full = (
        f"-c statement_timeout={int(max(1, statement_timeout_ms))} "
        f"-c lock_timeout={int(max(1, lock_timeout_ms))} "
        f"-c idle_in_transaction_session_timeout={int(max(1, idle_in_xact_timeout_ms))}"
    )
    opts_stmt_lock = (
        f"-c statement_timeout={int(max(1, statement_timeout_ms))} "
        f"-c lock_timeout={int(max(1, lock_timeout_ms))}"
    )
    opts_stmt_only = f"-c statement_timeout={int(max(1, statement_timeout_ms))}"
    candidates: list[str | None] = [opts_stmt_lock, opts_stmt_only, None]

    for opt in candidates:
        trial = _replace_options(base, opt)
        ok2, err2 = _try_connect(trial)
        if ok2:
            _NEGOTIATED_OPTIONS_CACHE[sig] = opt or ""
            return trial
        err_lc2 = (err2 or "").lower()
        # If error no longer about config parameter, break early
        if "unrecognized configuration parameter" not in err_lc2 and "invalid value for parameter" not in err_lc2:
            break

    # Could not negotiate; return the base DSN (fast-fail still applied)
    _NEGOTIATED_OPTIONS_CACHE[sig] = dict(parse_qsl(urlparse(base).query)).get("options", "")
    return base
