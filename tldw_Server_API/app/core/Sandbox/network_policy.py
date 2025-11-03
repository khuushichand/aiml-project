from __future__ import annotations

import ipaddress
import os
import socket
import subprocess
from typing import Callable, Iterable, List, Optional, Sequence
from loguru import logger


def _truthy(v: Optional[str]) -> bool:
    return bool(v) and str(v).strip().lower() in {"1", "true", "yes", "on", "y"}


def default_resolver(host: str) -> List[str]:
    """Resolve hostname to IPv4 addresses using getaddrinfo; return unique list.

    Avoids raising on DNS errors, returns empty list if resolution fails.
    """
    out: List[str] = []
    try:
        infos = socket.getaddrinfo(host, None, family=socket.AF_INET)
        for _fam, _sock, _proto, _canon, sa in infos:
            ip = sa[0]
            if ip not in out:
                out.append(ip)
    except Exception:
        return []
    return out


def expand_allowlist_to_targets(
    raw_allowlist: Sequence[str] | str | None,
    *,
    resolver: Callable[[str], List[str]] = default_resolver,
    wildcard_subdomains: Sequence[str] | None = ("", "www", "api"),
) -> List[str]:
    """Expand allowlist inputs (CIDR, IP, hostname, wildcard *.domain) into CIDR/IP targets.

    - CIDR tokens: validated and returned as-is
    - IP tokens: promoted to /32
    - Hostname tokens: resolved to A records and promoted to /32
    - Wildcard tokens (e.g., "*.example.com"): resolve a small set of commonly used subdomains
      ("", "www", "api") plus the apex. This is a pragmatic compromise until a dedicated
      DNS pinning/proxy mechanism is available.
    Returns a de-duplicated list of strings like "1.2.3.4/32" or "1.2.3.0/24" sorted for stability.
    """
    if raw_allowlist is None:
        return []
    if isinstance(raw_allowlist, str):
        tokens = [t.strip() for t in raw_allowlist.split(',') if t.strip()]
    else:
        tokens = [str(t).strip() for t in raw_allowlist if str(t).strip()]
    results: set[str] = set()
    for tok in tokens:
        # CIDR
        try:
            if "/" in tok:
                _ = ipaddress.ip_network(tok, strict=False)
                results.add(str(tok))
                continue
        except Exception:
            pass
        # Literal IP
        try:
            ipaddress.ip_address(tok)
            results.add(f"{tok}/32")
            continue
        except Exception:
            pass
        # Hostname (supports wildcard prefix "*.")
        host = tok
        is_wild = False
        if host.startswith("*."):
            is_wild = True
            host = host[2:]
        if not host:
            continue
        # Resolve apex and a small set of common subdomains for wildcard tokens
        to_resolve: List[str] = []
        if is_wild:
            subs = list(wildcard_subdomains or ("",))
            for sub in subs:
                fqdn = f"{sub}.{host}" if sub else host
                to_resolve.append(fqdn)
        else:
            to_resolve.append(host)
        for h in to_resolve:
            for ip in resolver(h):
                try:
                    ipaddress.ip_address(ip)
                    results.add(f"{ip}/32")
                except Exception:
                    continue
    return sorted(results)


def _build_restore_blob(container_ip: str, targets: Iterable[str], label: str) -> str:
    """Build an iptables-restore filter table blob that appends ACCEPT rules for targets
    and a final DROP for the container IP, labeled for later cleanup.
    """
    lines: List[str] = ["*filter"]
    for tgt in targets:
        dspec = tgt if "/" in tgt else f"{tgt}/32"
        lines.append(
            f"-A DOCKER-USER -s {container_ip} -d {dspec} -j ACCEPT -m comment --comment {label}"
        )
    lines.append(
        f"-A DOCKER-USER -s {container_ip} -j DROP -m comment --comment {label}"
    )
    lines.append("COMMIT\n")
    return "\n".join(lines)


def apply_egress_rules_atomic(container_ip: str, targets: Sequence[str], label: str) -> List[str]:
    """Apply iptables rules via iptables-restore --noflush for atomicity.

    Returns a list of rule specs (as in `iptables -S` without the initial action) for deletion fallback.
    On failure, attempts iterative application with `iptables` commands.
    """
    rule_specs: List[str] = []
    try:
        blob = _build_restore_blob(container_ip, targets, label)
        proc = subprocess.run(["iptables-restore", "--noflush"], input=blob.encode("utf-8"), check=False)
        if proc.returncode == 0:
            for tgt in targets:
                dspec = tgt if "/" in tgt else f"{tgt}/32"
                rule_specs.append(f"DOCKER-USER -s {container_ip} -d {dspec} -j ACCEPT -m comment --comment {label}")
            rule_specs.append(f"DOCKER-USER -s {container_ip} -j DROP -m comment --comment {label}")
            return rule_specs
        else:
            logger.debug("iptables-restore failed; falling back to iterative iptables invocations")
    except Exception as e:
        logger.debug(f"iptables-restore invocation failed: {e}")
    # Fallback path: iterative `iptables` calls
    for tgt in targets:
        dspec = tgt if "/" in tgt else f"{tgt}/32"
        try:
            subprocess.run([
                "iptables", "-I", "DOCKER-USER", "1",
                "-s", container_ip, "-d", dspec, "-j", "ACCEPT",
                "-m", "comment", "--comment", label,
            ], check=False)
            rule_specs.append(f"DOCKER-USER -s {container_ip} -d {dspec} -j ACCEPT -m comment --comment {label}")
        except Exception:
            pass
    try:
        subprocess.run([
            "iptables", "-A", "DOCKER-USER",
            "-s", container_ip, "-j", "DROP",
            "-m", "comment", "--comment", label,
        ], check=False)
        rule_specs.append(f"DOCKER-USER -s {container_ip} -j DROP -m comment --comment {label}")
    except Exception:
        pass
    return rule_specs


def delete_rules_by_label(label: str) -> None:
    """Delete all rules in DOCKER-USER containing the label comment.

    Attempts precise deletion using rule numbers; falls back to translating `iptables -S` specs.
    """
    # Try deletion by line numbers (descending)
    try:
        out = subprocess.check_output(["iptables", "-L", "DOCKER-USER", "--line-numbers", "-n", "-v"], text=True)
        lines = out.splitlines()
        # Skip header lines, find those with the comment
        numbered: List[int] = []
        for ln in lines:
            if label in ln:
                try:
                    num = int(ln.split()[0])
                    numbered.append(num)
                except Exception:
                    continue
        for num in sorted(numbered, reverse=True):
            try:
                subprocess.run(["iptables", "-D", "DOCKER-USER", str(num)], check=False)
            except Exception:
                pass
        return
    except Exception:
        pass
    # Fallback: translate `iptables -S` specs into deletions
    try:
        out2 = subprocess.check_output(["iptables", "-S", "DOCKER-USER"], text=True)
        for line in out2.splitlines():
            if label in line:
                parts = line.strip().split()
                if parts and parts[0] in {"-A", "-I"}:
                    parts[0] = "-D"
                    try:
                        subprocess.run(["iptables"] + parts, check=False)
                    except Exception:
                        pass
    except Exception:
        pass

