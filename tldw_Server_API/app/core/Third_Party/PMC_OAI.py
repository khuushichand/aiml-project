"""
PMC_OAI.py

PMC OAI-PMH provider adapter for Identify, ListSets, ListIdentifiers, ListRecords, GetRecord.

Uses the production base URL: https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/

Parses oai_dc metadata to extract title, creators, identifiers and license URLs when present.
Returns normalized dictionaries and resumption tokens where applicable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import requests
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tldw_Server_API.app.core.http_client import create_client
from xml.etree import ElementTree as ET


BASE_URL = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"


def _mk_session():
    try:
        c = create_client(timeout=20)
        c.headers.update({"Accept-Encoding": "gzip, deflate"})
        return c
    except Exception:
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        s = requests.Session()
        s.headers.update({"Accept-Encoding": "gzip, deflate"})
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s


def _get(session: requests.Session, params: Dict[str, Any]) -> ET.Element:
    r = session.get(BASE_URL, params=params, timeout=20)
    r.raise_for_status()
    return ET.fromstring(r.text)


def pmc_oai_identify() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        s = _mk_session()
        root = _get(s, {"verb": "Identify"})
        info: Dict[str, Any] = {}
        ident = root.find(".//{http://www.openarchives.org/OAI/2.0/}Identify")
        if ident is None:
            return {"raw_xml": r_text(root)}, None
        # Extract some common fields
        def text(tag: str) -> Optional[str]:
            el = ident.find(f"{{http://www.openarchives.org/OAI/2.0/}}{tag}")
            return el.text if el is not None else None

        info.update({
            "repositoryName": text("repositoryName"),
            "baseURL": text("baseURL"),
            "protocolVersion": text("protocolVersion"),
            "earliestDatestamp": text("earliestDatestamp"),
            "deletedRecord": text("deletedRecord"),
            "granularity": text("granularity"),
        })
        return info, None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to PMC OAI-PMH timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"PMC OAI-PMH HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to PMC OAI-PMH timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"PMC OAI-PMH HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"PMC OAI-PMH Request Error: {str(e)}"
        return None, f"Unexpected PMC OAI-PMH Identify error: {str(e)}"


def r_text(el: ET.Element) -> str:
    return ET.tostring(el, encoding="unicode")


def _parse_resumption(root: ET.Element) -> Optional[str]:
    ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}
    r = root.find(".//oai:resumptionToken", ns)
    return r.text.strip() if r is not None and r.text else None


def pmc_oai_list_sets(resumption_token: Optional[str] = None) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str], Optional[str]]:
    try:
        s = _mk_session()
        params: Dict[str, Any] = {"verb": "ListSets"}
        if resumption_token:
            params = {"verb": "ListSets", "resumptionToken": resumption_token}
        root = _get(s, params)
        sets: List[Dict[str, Any]] = []
        ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}
        for se in root.findall(".//oai:set", ns):
            spec = se.find("oai:setSpec", ns)
            name = se.find("oai:setName", ns)
            sets.append({
                "setSpec": spec.text if spec is not None else None,
                "setName": name.text if name is not None else None,
            })
        return sets, _parse_resumption(root), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to PMC OAI-PMH timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"PMC OAI-PMH HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to PMC OAI-PMH timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"PMC OAI-PMH HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"PMC OAI-PMH Request Error: {str(e)}"
        return None, None, f"Unexpected PMC OAI-PMH ListSets error: {str(e)}"


def _parse_dc_metadata(md: ET.Element) -> Dict[str, Any]:
    # oai_dc namespace
    ns = {
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    out: Dict[str, Any] = {
        "title": None,
        "creators": [],
        "identifiers": [],
        "rights": [],
        "license_urls": [],
        "date": None,
        "pmcid": None,
        "pmid": None,
        "doi": None,
    }
    t = md.find(".//dc:title", ns)
    out["title"] = t.text if t is not None else None
    for c in md.findall(".//dc:creator", ns):
        if c.text:
            out["creators"].append(c.text)
    for i in md.findall(".//dc:identifier", ns):
        if i.text:
            val = i.text.strip()
            out["identifiers"].append(val)
            # Extract pmcid/pmid/doi from canonical URLs when present
            if "pmc.ncbi.nlm.nih.gov" in val and "/PMC" in val:
                try:
                    # canonical PMC URL looks like https://pmc.ncbi.nlm.nih.gov/PMC1234567
                    pmcid = val.split("/PMC")[-1]
                    out["pmcid"] = pmcid
                except Exception:
                    pass
            if "pubmed.ncbi.nlm.nih.gov" in val:
                try:
                    out["pmid"] = val.rstrip('/').split('/')[-1]
                except Exception:
                    pass
            if "doi.org/" in val:
                try:
                    out["doi"] = val.split("doi.org/")[-1]
                except Exception:
                    pass
    for r in md.findall(".//dc:rights", ns):
        if r.text:
            txt = r.text.strip()
            out["rights"].append(txt)
            if txt.startswith("http://") or txt.startswith("https://"):
                out["license_urls"].append(txt)
    d = md.find(".//dc:date", ns)
    out["date"] = d.text if d is not None else None
    return out


def _parse_records(root: ET.Element) -> List[Dict[str, Any]]:
    ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}
    items: List[Dict[str, Any]] = []
    for rec in root.findall(".//oai:record", ns):
        header = rec.find("oai:header", ns)
        meta = rec.find("oai:metadata", ns)
        item: Dict[str, Any] = {}
        if header is not None:
            id_el = header.find("oai:identifier", ns)
            ds = header.find("oai:datestamp", ns)
            ss = [se.text for se in header.findall("oai:setSpec", ns) if se is not None and se.text]
            item["header"] = {
                "identifier": id_el.text if id_el is not None else None,
                "datestamp": ds.text if ds is not None else None,
                "setSpecs": ss if ss else None,
            }
        if meta is not None and len(meta):
            # expect child to be oai_dc:dc or pmc/pmc_fm
            md_child = list(meta)[0]
            if md_child.tag.endswith("dc"):
                item["metadata"] = _parse_dc_metadata(md_child)
            else:
                item["raw_xml"] = r_text(md_child)
        items.append(item)
    return items


def pmc_oai_list_records(
    metadata_prefix: str = "oai_dc",
    from_date: Optional[str] = None,
    until_date: Optional[str] = None,
    set_name: Optional[str] = None,
    resumption_token: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str], Optional[str]]:
    try:
        s = _mk_session()
        params: Dict[str, Any] = {"verb": "ListRecords"}
        if resumption_token:
            params["resumptionToken"] = resumption_token
        else:
            params["metadataPrefix"] = metadata_prefix
            if from_date:
                params["from"] = from_date
            if until_date:
                params["until"] = until_date
            if set_name:
                params["set"] = set_name
        root = _get(s, params)
        items = _parse_records(root)
        return items, _parse_resumption(root), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to PMC OAI-PMH timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"PMC OAI-PMH HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to PMC OAI-PMH timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"PMC OAI-PMH HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"PMC OAI-PMH Request Error: {str(e)}"
        return None, None, f"Unexpected PMC OAI-PMH ListRecords error: {str(e)}"


def pmc_oai_list_identifiers(
    metadata_prefix: str = "oai_dc",
    from_date: Optional[str] = None,
    until_date: Optional[str] = None,
    set_name: Optional[str] = None,
    resumption_token: Optional[str] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str], Optional[str]]:
    try:
        s = _mk_session()
        params: Dict[str, Any] = {"verb": "ListIdentifiers"}
        if resumption_token:
            params["resumptionToken"] = resumption_token
        else:
            params["metadataPrefix"] = metadata_prefix
            if from_date:
                params["from"] = from_date
            if until_date:
                params["until"] = until_date
            if set_name:
                params["set"] = set_name
        root = _get(s, params)
        ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}
        items: List[Dict[str, Any]] = []
        for he in root.findall(".//oai:header", ns):
            id_el = he.find("oai:identifier", ns)
            ds = he.find("oai:datestamp", ns)
            ss = [se.text for se in he.findall("oai:setSpec", ns) if se is not None and se.text]
            items.append({
                "identifier": id_el.text if id_el is not None else None,
                "datestamp": ds.text if ds is not None else None,
                "setSpecs": ss if ss else None,
            })
        return items, _parse_resumption(root), None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, None, "Request to PMC OAI-PMH timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, None, f"PMC OAI-PMH HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, None, "Request to PMC OAI-PMH timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, None, f"PMC OAI-PMH HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, None, f"PMC OAI-PMH Request Error: {str(e)}"
        return None, None, f"Unexpected PMC OAI-PMH ListIdentifiers error: {str(e)}"


def pmc_oai_get_record(
    identifier: str,
    metadata_prefix: str = "oai_dc",
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if not identifier or not identifier.strip():
            return None, "Identifier cannot be empty"
        s = _mk_session()
        params = {"verb": "GetRecord", "identifier": identifier.strip(), "metadataPrefix": metadata_prefix}
        root = _get(s, params)
        items = _parse_records(root)
        if not items:
            return None, None
        return items[0], None
    except Exception as e:
        if httpx is not None and isinstance(e, httpx.TimeoutException):
            return None, "Request to PMC OAI-PMH timed out."
        if httpx is not None and isinstance(e, httpx.HTTPStatusError):
            return None, f"PMC OAI-PMH HTTP Error: {getattr(e.response, 'status_code', '?')}"
        if isinstance(e, requests.exceptions.Timeout):
            return None, "Request to PMC OAI-PMH timed out."
        if isinstance(e, requests.exceptions.HTTPError):
            return None, f"PMC OAI-PMH HTTP Error: {getattr(getattr(e, 'response', None), 'status_code', '?')}"
        if isinstance(e, requests.exceptions.RequestException):
            return None, f"PMC OAI-PMH Request Error: {str(e)}"
        return None, f"Unexpected PMC OAI-PMH GetRecord error: {str(e)}"
