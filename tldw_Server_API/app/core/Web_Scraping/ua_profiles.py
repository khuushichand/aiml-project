"""
UA and browser-like header profiles for scraping and websearch.

This module centralizes construction of realistic browser headers
including sec-ch-ua*, Sec-Fetch-*, Accept, Accept-Language, and
Accept-Encoding. It also maps UA profiles to curl_cffi impersonation
strings for consistent TLS/HTTP2 fingerprinting.

Usage:
    from tldw_Server_API.app.core.Web_Scraping.ua_profiles import (
        build_browser_headers, pick_ua_profile, profile_to_impersonate
    )

    profile = pick_ua_profile("fixed", domain="example.com")
    headers = build_browser_headers(profile, accept_lang="en-US,en;q=0.9")

Notes:
- Accept-Encoding includes gzip, deflate, br, zstd. Ensure optional
  decompressors are installed when not using curl's built-in decoding
  (e.g., python 'brotli' and 'zstandard').
- Sec-Fetch-* defaults are appropriate for top-level navigations.
  Adjust per-request when issuing subresource fetches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List
import random


@dataclass(frozen=True)
class UAProfile:
    name: str
    user_agent: str
    sec_ch_ua: str
    sec_ch_ua_mobile: str
    sec_ch_ua_platform: str
    impersonate: Optional[str]  # curl_cffi impersonate token


# Curated UA profiles (static but periodically updatable)
_UA_PROFILES: Dict[str, UAProfile] = {
    # Chrome 120 on Windows 10/11
    "chrome_120_win": UAProfile(
        name="chrome_120_win",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        sec_ch_ua='"Not.A/Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"Windows"',
        impersonate="chrome120",
    ),
    # Firefox 120 on Windows
    "firefox_120_win": UAProfile(
        name="firefox_120_win",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
            "Gecko/20100101 Firefox/120.0"
        ),
        sec_ch_ua='"Not.A/Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',  # Some servers accept Chromium-style hints
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"Windows"',
        impersonate="firefox120",
    ),
    # Safari 17 on macOS
    "safari_17_mac": UAProfile(
        name="safari_17_mac",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
        sec_ch_ua='"Not.A/Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        sec_ch_ua_mobile="?0",
        sec_ch_ua_platform='"macOS"',
        impersonate="safari17",
    ),
}


_DEFAULT_PROFILE_ORDER: List[str] = [
    "chrome_120_win",
    "firefox_120_win",
    "safari_17_mac",
]


def pick_ua_profile(mode: str = "fixed", domain: Optional[str] = None) -> str:
    """Pick a UA profile name.

    - mode: 'fixed' or 'rotate'
    - domain: reserved for future per-domain policies
    """
    if mode == "rotate":
        return random.choice(_DEFAULT_PROFILE_ORDER)
    return _DEFAULT_PROFILE_ORDER[0]


def profile_to_impersonate(profile: str) -> Optional[str]:
    p = _UA_PROFILES.get(profile)
    return p.impersonate if p else None


def build_browser_headers(
    profile: str,
    *,
    accept_lang: str = "en-US,en;q=0.9",
    sec_fetch_site: str = "none",
    sec_fetch_mode: str = "navigate",
    sec_fetch_dest: str = "document",
    upgrade_insecure_requests: bool = True,
    accept_encoding: str = "gzip, deflate, br, zstd",
) -> Dict[str, str]:
    """Construct realistic browser headers for top-level navigation.

    Includes:
    - User-Agent
    - sec-ch-ua, sec-ch-ua-mobile, sec-ch-ua-platform
    - Accept, Accept-Language, Accept-Encoding
    - Sec-Fetch-*
    - Upgrade-Insecure-Requests (optional)
    """
    p = _UA_PROFILES.get(profile)
    if not p:
        p = _UA_PROFILES[_DEFAULT_PROFILE_ORDER[0]]

    headers: Dict[str, str] = {
        "User-Agent": p.user_agent,
        "sec-ch-ua": p.sec_ch_ua,
        "sec-ch-ua-mobile": p.sec_ch_ua_mobile,
        "sec-ch-ua-platform": p.sec_ch_ua_platform,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": accept_lang,
        "Accept-Encoding": accept_encoding,
        "Sec-Fetch-Site": sec_fetch_site,
        "Sec-Fetch-Mode": sec_fetch_mode,
        "Sec-Fetch-Dest": sec_fetch_dest,
    }
    if upgrade_insecure_requests:
        headers["Upgrade-Insecure-Requests"] = "1"
    return headers


__all__ = [
    "UAProfile",
    "build_browser_headers",
    "pick_ua_profile",
    "profile_to_impersonate",
]
