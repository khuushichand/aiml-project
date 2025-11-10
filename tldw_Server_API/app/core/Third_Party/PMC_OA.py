"""
PMC_OA.py

PMC OA Web Service adapter (https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi)

Supports identification and result set queries with resumptionToken. Also
exposes a simple PDF download helper for PMC articles.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import os
from xml.etree import ElementTree as ET
from tldw_Server_API.app.core.http_client import fetch


BASE_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"


def _get_xml(params: Dict[str, Any]) -> ET.Element:
    r = fetch(method="GET", url=BASE_URL, params=params, headers={"Accept": "application/xml"}, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        return ET.fromstring(r.text)
    finally:
        try:
            r.close()
        except Exception:
            pass


def pmc_oa_identify() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        root = _get_xml({})
        info: Dict[str, Any] = {}
        # Extract simple counts and formats when present
        resp_date = root.find("responseDate")
        repo = root.find("repositoryName")
        formats = [f.text for f in root.findall("formats/format") if f is not None and f.text]
        latest = root.find("records/latest")
        info.update({
            "responseDate": resp_date.text if resp_date is not None else None,
            "repositoryName": repo.text if repo is not None else None,
            "formats": formats or None,
            "latest": latest.text if latest is not None else None,
        })
        return info, None
    except Exception as e:
        return None, f"PMC OA Identify error: {str(e)}"


def _parse_resumption(root: ET.Element) -> Optional[str]:
    res = root.find("resumption")
    if res is None:
        return None
    link = res.find("link")
    if link is not None:
        token = link.attrib.get("token")
        return token
    return None


def pmc_oa_query(
    from_date: Optional[str] = None,
    until_date: Optional[str] = None,
    fmt: Optional[str] = None,  # 'pdf' or 'tgz'
    resumption_token: Optional[str] = None,
    id_param: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str], Optional[str]]:
    """Query OA Web Service for record links.

    Returns (items, resumption_token, error_message)
    """
    try:
        params: Dict[str, Any] = {}
        if id_param:
            params["id"] = id_param
        elif resumption_token:
            params["resumptionToken"] = resumption_token
        else:
            if from_date:
                params["from"] = from_date
            if until_date:
                params["until"] = until_date
            if fmt:
                params["format"] = fmt
        root = _get_xml(params)
        records: List[Dict[str, Any]] = []
        for rec in root.findall("records/record"):
            rid = rec.attrib.get("id")
            citation = rec.attrib.get("citation")
            license_attr = rec.attrib.get("license")
            retracted = rec.attrib.get("retracted")
            links = []
            for link in rec.findall("link"):
                links.append({
                    "format": link.attrib.get("format"),
                    "updated": link.attrib.get("updated"),
                    "href": link.attrib.get("href"),
                })
            records.append({
                "id": rid,
                "citation": citation,
                "license": license_attr,
                "retracted": (retracted == "yes") if retracted is not None else None,
                "links": links,
            })
        return records, _parse_resumption(root), None
    except Exception as e:
        return None, None, f"PMC OA query error: {str(e)}"


def download_pmc_pdf(pmcid: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Download a PMC PDF by PMCID numeric portion.

    Returns (content_bytes, filename, error_message)
    """
    try:
        pmcid_num = str(pmcid).strip().lstrip("PMC")
        if not pmcid_num:
            return None, None, "PMCID cannot be empty"
        url = f"https://pmc.ncbi.nlm.nih.gov/PMC{pmcid_num}/pdf"
        r = fetch(method="GET", url=url, timeout=30)
        if r.status_code >= 400:
            return None, None, f"PMC PDF HTTP error: {r.status_code}"
        # Best-effort filename from headers; default to PMC{pmcid}.pdf
        filename = f"PMC{pmcid_num}.pdf"
        cd = r.headers.get("Content-Disposition")
        if cd and "filename=" in cd:
            filename = cd.split("filename=")[-1].strip('"')
        return r.content, filename, None
    except Exception as e:
        return None, None, f"PMC PDF download error: {str(e)}"
