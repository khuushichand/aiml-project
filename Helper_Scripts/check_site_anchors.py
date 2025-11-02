#!/usr/bin/env python3
"""
Check internal anchor links in a built MkDocs site.

Scans HTML files under the given site directory (default: ./site),
collects anchor IDs from each page, and verifies that links with
fragment identifiers (e.g., page.html#anchor or #anchor) point to
existing anchors in the target page.

Usage:
  python Helper_Scripts/check_site_anchors.py [SITE_DIR]

Exit codes:
  0: no problems found
  1: missing anchors or missing target files detected

Notes:
  - Only checks internal links (http(s):, mailto:, tel:, javascript: are skipped).
  - Resolves absolute paths (/...) relative to the site root.
  - Decodes percent-encoded fragments when comparing anchor IDs.
"""

from __future__ import annotations

import os
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse, unquote


class AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: Set[str] = set()
        self.hrefs: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]):
        # collect id attributes on common elements (headings, anchors, generic)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "a", "div", "span", "section"):
            for k, v in attrs:
                if k == "id" and v:
                    self.ids.add(v)
                    break
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)
                    break


SKIP_SCHEMES = ("http:", "https:", "mailto:", "tel:", "javascript:")


def is_internal_link(href: str) -> bool:
    href = href.strip()
    if not href:
        return False
    lower = href.lower()
    return not lower.startswith(SKIP_SCHEMES)


def collect_page_anchors(html_path: Path) -> Tuple[Set[str], List[str]]:
    parser = AnchorCollector()
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set(), []
    parser.feed(text)
    return parser.ids, parser.hrefs


def resolve_target(current: Path, href: str, site_root: Path) -> Tuple[Path, str]:
    """Resolve a link target to a file path and fragment id.

    Returns (target_file, fragment_id). If no fragment, fragment_id is ''.
    """
    p = urlparse(href)
    fragment = unquote(p.fragment) if p.fragment else ""
    # anchor-only link
    if not p.scheme and not p.netloc and (p.path == "" or p.path is None):
        return current, fragment
    # absolute path (site-root relative)
    if p.path and p.path.startswith("/"):
        target = (site_root / p.path.lstrip("/")).resolve()
        return target, fragment
    # relative path
    if p.path:
        target = (current.parent / p.path).resolve()
        return target, fragment
    # fallback to current file
    return current, fragment


def main(argv: List[str]) -> int:
    site_dir = Path(argv[1]) if len(argv) > 1 else Path("site")
    if not site_dir.exists():
        print(f"[ERROR] Site directory not found: {site_dir}", file=sys.stderr)
        return 1

    # Collect anchors for all pages
    anchors_by_file: Dict[Path, Set[str]] = {}
    hrefs_by_file: Dict[Path, List[str]] = {}

    for path in site_dir.rglob("*.html"):
        ids, hrefs = collect_page_anchors(path)
        anchors_by_file[path.resolve()] = ids
        hrefs_by_file[path.resolve()] = hrefs

    missing: List[Tuple[Path, str, str]] = []  # (source_file, href, reason)
    checked_links = 0

    for src, hrefs in hrefs_by_file.items():
        for href in hrefs:
            if not is_internal_link(href):
                continue
            # Only check links that include a fragment (either #frag or file#frag)
            has_fragment = "#" in href
            if not has_fragment and not href.startswith("#"):
                continue
            checked_links += 1
            tgt_file, frag = resolve_target(src, href, site_dir)
            # Only verify anchors when a fragment is present
            if not frag:
                continue
            if not tgt_file.exists():
                # If target path lacks extension, try adding .html (mkdocs often generates index.html in dirs)
                alt = tgt_file
                if tgt_file.is_dir():
                    alt = tgt_file / "index.html"
                elif tgt_file.suffix == "":
                    alt = tgt_file.with_suffix(".html")
                if not alt.exists():
                    missing.append((src, href, "target file not found"))
                    continue
                tgt_file = alt
            ids = anchors_by_file.get(tgt_file.resolve())
            if ids is None:
                # If the target wasn't scanned (e.g., non-html), skip silently
                continue
            if frag not in ids:
                missing.append((src, href, "anchor id not found"))

    if missing:
        print("Broken internal anchors detected:")
        for src, href, reason in missing:
            rel_src = os.path.relpath(src, site_dir)
            print(f" - {rel_src}: {href}  ({reason})")
        print(f"\nScanned HTML files: {len(anchors_by_file)}; Checked links with fragments: {checked_links}; Missing anchors: {len(missing)}")
        return 1

    print(f"OK: {len(anchors_by_file)} HTML files; {checked_links} fragment links checked; no missing anchors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
