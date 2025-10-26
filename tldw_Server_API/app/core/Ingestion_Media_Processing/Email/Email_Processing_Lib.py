"""
Email_Processing_Lib.py
Minimal EML parsing and processing for ingestion pipeline.

Stage 1 scope:
- Parse .eml bytes to extract plain text/HTML, headers, and addresses.
- Produce a normalized result dict compatible with media processing pipeline.
- Chunking (optional) and optional analysis hooks.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple

import os
import re
import io
import zipfile
import tempfile
import mailbox
from email import policy
from email.message import Message, EmailMessage
from email.parser import BytesParser
from email.header import decode_header, make_header
from email.utils import getaddresses

from tldw_Server_API.app.core.Utils.Utils import logging
from tldw_Server_API.app.core.Chunking import improved_chunking_process
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import DEFAULT_MEDIA_TYPE_CONFIG

try:
    import html2text as _html2text
except Exception:
    _html2text = None  # Optional dependency; fallback stripping will apply

# Compatibility shim for Python 3.13 EmailMessage/contentmanager API changes
# Some helpers call: outer.add_attachment(inner, maintype="message", subtype="rfc822").
# In Python 3.13 this ultimately calls email.contentmanager.set_message_content(),
# whose signature no longer accepts 'maintype'. We provide two defensive shims:
# 1) Patch contentmanager.set_message_content to drop 'maintype'.
# 2) Patch the active Policy's ContentManager set_handlers[Message] mapping to a wrapper
#    that drops 'maintype' before delegating to the original handler. This ensures the
#    fix applies even if handlers were bound at import-time to the original function.
try:  # pragma: no cover - defensive guard
    import email.contentmanager as _ecm  # type: ignore
    if hasattr(_ecm, 'set_message_content'):
        _orig_cm_set_message_content = _ecm.set_message_content  # type: ignore[attr-defined]

        def _compat_cm_set_message_content(msg, obj, *args, **kwargs):  # type: ignore[no-redef]
            if 'maintype' in kwargs:
                kwargs.pop('maintype', None)
            return _orig_cm_set_message_content(msg, obj, *args, **kwargs)  # type: ignore[misc]

        _ecm.set_message_content = _compat_cm_set_message_content  # type: ignore[assignment]

    # Additionally patch the active policy content manager mapping so any
    # pre-bound handler for Message objects also ignores 'maintype'.
    try:
        from email.message import Message as _EMessage  # local alias
        from email import policy as _epolicy
        _cm_inst = getattr(_epolicy.default, 'content_manager', None)
        if _cm_inst and hasattr(_cm_inst, 'set_handlers'):
            _orig_handler = _cm_inst.set_handlers.get(_EMessage)
            if callable(_orig_handler):
                def _compat_handler(msg, obj, *args, **kwargs):  # type: ignore[no-redef]
                    if 'maintype' in kwargs:
                        kwargs.pop('maintype', None)
                    return _orig_handler(msg, obj, *args, **kwargs)

                _cm_inst.set_handlers[_EMessage] = _compat_handler  # type: ignore[index]
    except Exception:
        # best-effort; if anything fails, fall back to add_attachment shim below
        pass
except Exception:
    pass

# Also guard add_attachment path for message/rfc822 to drop 'maintype' kwarg
try:  # pragma: no cover
    _OrigEmailMessage = EmailMessage
    if hasattr(_OrigEmailMessage, 'add_attachment'):
        _orig_add_attachment = _OrigEmailMessage.add_attachment  # type: ignore[attr-defined]

        def _compat_add_attachment(self, content, *args, **kwargs):  # type: ignore[no-redef]
            if isinstance(content, EmailMessage) and 'maintype' in kwargs:
                kwargs.pop('maintype', None)
            return _orig_add_attachment(self, content, *args, **kwargs)

        _OrigEmailMessage.add_attachment = _compat_add_attachment  # type: ignore[assignment]
except Exception:
    pass


def _decode_mime_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _addresses_from_header(msg: Message, header_name: str) -> str:
    try:
        raw_values = msg.get_all(header_name, [])
        pairs = getaddresses(raw_values)
        # Keep only email part for storage/search; join with comma+space
        emails: List[str] = []
        for name, email_addr in pairs:
            if email_addr and "@" in email_addr:
                emails.append(email_addr)
        return ", ".join(emails)
    except Exception as e:
        logging.debug(f"Failed to parse addresses from {header_name}: {e}")
        try:
            get_metrics_registry().increment(
                "app_warning_events_total",
                labels={"component": "email_ingest", "event": "addresses_parse_failed"},
            )
        except Exception:
            pass
        return ""


def _part_payload_to_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = (part.get_content_charset() or "utf-8").lower()
    for enc in [charset, "utf-8", "latin-1"]:
        try:
            return payload.decode(enc, errors="ignore")
        except Exception:
            continue
    # Fallback
    try:
        return payload.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        if _html2text:
            conv = _html2text.HTML2Text()
            conv.ignore_links = False
            conv.ignore_images = True
            conv.body_width = 0
            return conv.handle(html)
        # Very light fallback: strip tags
        return re.sub(r"<[^>]+>", " ", html)
    except Exception:
        return html


def parse_eml_bytes(
    file_bytes: bytes,
    filename: str = "email.eml",
    *,
    return_children: bool = False,
) -> Tuple[str, Dict[str, Any], List[Tuple[bytes, str]]]:
    """
    Parse EML bytes and return (content_text, metadata_dict).
    metadata_dict contains email-specific fields in metadata['email'].
    """
    msg: Message = BytesParser(policy=policy.default).parsebytes(file_bytes)

    # Headers and fields
    subject = _decode_mime_header(msg.get("Subject"))
    from_addr = _addresses_from_header(msg, "From")
    to_addr = _addresses_from_header(msg, "To")
    cc_addr = _addresses_from_header(msg, "Cc")
    bcc_addr = _addresses_from_header(msg, "Bcc")
    date_hdr = _decode_mime_header(msg.get("Date"))
    message_id = _decode_mime_header(msg.get("Message-ID"))
    fmt = (msg.get_content_type() or "message/rfc822").strip()

    # Flatten headers map with unfolded values
    headers_map: Dict[str, Any] = {}
    try:
        for k, v in msg.items():
            headers_map[k] = _decode_mime_header(v)
    except Exception:
        pass

    # Bodies and attachments
    text_parts: List[str] = []
    html_first: Optional[str] = None
    attachments_meta: List[Dict[str, Any]] = []
    child_emls: List[Tuple[bytes, str]] = []  # (bytes, filename)

    if msg.is_multipart():
        for part in msg.walk():
            cdisp = (part.get_content_disposition() or "").lower()
            ctype = (part.get_content_type() or "").lower()
            filename_part = part.get_filename()

            if cdisp == "attachment" or filename_part:
                try:
                    raw = part.get_payload(decode=True) or b""
                except Exception:
                    raw = b""
                attachments_meta.append({
                    "name": _decode_mime_header(filename_part) if filename_part else (part.get("Content-ID") or "unknown_file_name"),
                    "content_type": ctype,
                    "size": len(raw) if isinstance(raw, (bytes, bytearray)) else None,
                    "content_id": part.get("Content-ID"),
                    "disposition": cdisp or None,
                })
                # Capture nested EMLs if requested
                if return_children and (
                    ctype == "message/rfc822" or (filename_part and str(filename_part).lower().endswith('.eml'))
                ):
                    try:
                        payload_obj = part.get_payload()
                        if isinstance(payload_obj, list) and payload_obj and isinstance(payload_obj[0], Message):
                            child_msg = payload_obj[0]
                            child_bytes = child_msg.as_bytes(policy=policy.default)
                        else:
                            # Fallback: try decoded
                            child_bytes = part.get_payload(decode=True) or b""
                        if child_bytes:
                            child_name = _decode_mime_header(filename_part) if filename_part else "attached.eml"
                            child_emls.append((child_bytes, child_name))
                    except Exception as ce:
                        logging.debug(f"Failed to capture nested EML bytes: {ce}")
                        try:
                            get_metrics_registry().increment(
                                "app_warning_events_total",
                                labels={"component": "email_ingest", "event": "nested_eml_capture_failed"},
                            )
                        except Exception:
                            pass
                continue

            if ctype == "text/plain":
                text_parts.append(_part_payload_to_text(part))
            elif ctype == "text/html" and html_first is None:
                html_first = _part_payload_to_text(part)
    else:
        # Single-part message
        ctype = (msg.get_content_type() or "").lower()
        if ctype == "text/plain":
            text_parts.append(_part_payload_to_text(msg))
        elif ctype == "text/html":
            html_first = _part_payload_to_text(msg)

    text_content = "\n".join([t for t in text_parts if t and t.strip()])
    if not text_content and html_first:
        text_content = _html_to_text(html_first)

    metadata: Dict[str, Any] = {
        "title": subject or (filename.rsplit(".", 1)[0] if filename else "Untitled Email"),
        "author": from_addr or "Unknown",
        "parser_used": "builtin-email",
        "filename": filename,
        "email": {
            "from": from_addr,
            "to": to_addr,
            "cc": cc_addr,
            "bcc": bcc_addr,
            "subject": subject,
            "date": date_hdr,
            "message_id": message_id,
            "format": fmt,
            "attachments": attachments_meta,
            "headers_map": headers_map,
        },
    }

    return text_content.strip(), metadata, child_emls


def process_email_task(
    *,
    file_bytes: bytes,
    filename: str,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    perform_chunking: bool = True,
    chunk_options: Optional[Dict[str, Any]] = None,
    perform_analysis: bool = False,
    api_name: Optional[str] = None,
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    summarize_recursively: bool = False,
    ingest_attachments: bool = False,
    max_depth: int = 1,
) -> Dict[str, Any]:
    """
    Process EML bytes and produce a normalized dict (no DB interaction).
    """
    result: Dict[str, Any] = {
        "status": "Pending",
        "input_ref": filename,
        "media_type": "email",
        "parser_used": "builtin-email",
        "processing_source": "bytes",
        "content": None,
        "metadata": {},
        "chunks": None,
        "analysis": None,
        "keywords": keywords or [],
        "warnings": [],
        "analysis_details": {
            "analysis_model": api_name if perform_analysis else None,
            "custom_prompt_used": custom_prompt if perform_analysis else None,
            "system_prompt_used": system_prompt if perform_analysis else None,
            "summarized_recursively": summarize_recursively if perform_analysis else False,
        },
        "error": None,
    }

    try:
        content_text, metadata, child_emls = parse_eml_bytes(file_bytes, filename, return_children=True)
        if title_override:
            metadata["title"] = title_override
        if author_override:
            metadata["author"] = author_override

        result["content"] = content_text
        result["metadata"] = metadata

        # Chunking
        if content_text and perform_chunking:
            if chunk_options is None:
                chunk_options = {"method": "sentences", "max_size": 1000, "overlap": 200}
            try:
                chunks = improved_chunking_process(content_text, chunk_options)
                if not chunks:
                    chunks = [{"text": content_text, "metadata": {"chunk_num": 0}}]
                    result["warnings"].append("Chunking yielded no results; using full text.")
                result["chunks"] = chunks
            except Exception as e:
                logging.error(f"Email chunking failed for {filename}: {e}")
                try:
                    get_metrics_registry().increment(
                        "app_exception_events_total",
                        labels={"component": "email_ingest", "event": "chunking_failed"},
                    )
                except Exception:
                    pass
                result["warnings"].append(f"Chunking failed: {e}")
                result["chunks"] = [{"text": content_text, "metadata": {"chunk_num": 0, "error": str(e)}}]
        elif content_text:
            result["chunks"] = [{"text": content_text, "metadata": {"chunk_num": 0}}]

        # Analysis (optional; requires api_name/api_key)
        if perform_analysis and api_name and api_key and result.get("chunks"):
            try:
                from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze
                # Summarize entire content or first N chars
                analysis_text = analyze(
                    api_name=api_name,
                    input_data=content_text,
                    custom_prompt_arg=custom_prompt,
                    api_key=api_key,
                    recursive_summarization=summarize_recursively,
                    system_message=system_prompt,
                )
                if analysis_text and isinstance(analysis_text, str):
                    result["analysis"] = analysis_text
            except Exception as e:
                logging.warning(f"Email analysis failed for {filename}: {e}")
                try:
                    get_metrics_registry().increment(
                        "app_warning_events_total",
                        labels={"component": "email_ingest", "event": "analysis_failed"},
                    )
                except Exception:
                    pass
                result["warnings"].append(f"Analysis failed: {e}")

        # Optionally parse nested email attachments recursively (children are returned in 'children' key)
        if ingest_attachments and max_depth > 1 and child_emls:
            children_results: List[Dict[str, Any]] = []
            for child_bytes, child_name in child_emls:
                try:
                    child_res = process_email_task(
                        file_bytes=child_bytes,
                        filename=child_name or "attached.eml",
                        title_override=None,
                        author_override=None,
                        keywords=keywords,
                        perform_chunking=perform_chunking,
                        chunk_options=chunk_options,
                        perform_analysis=False,  # Do not analyze children by default
                        api_name=api_name,
                        api_key=api_key,
                        custom_prompt=custom_prompt,
                        system_prompt=system_prompt,
                        summarize_recursively=False,
                        ingest_attachments=ingest_attachments,
                        max_depth=max_depth - 1,
                    )
                    children_results.append(child_res)
                except Exception as ce:
                    logging.debug(f"Failed to process child EML '{child_name}': {ce}")
                    try:
                        get_metrics_registry().increment(
                            "app_warning_events_total",
                            labels={"component": "email_ingest", "event": "child_process_failed"},
                        )
                    except Exception:
                        pass
            if children_results:
                result["children"] = children_results

        result["status"] = "Success"
        return result
    except Exception as e:
        logging.error(f"Failed processing email '{filename}': {e}", exc_info=True)
        result["status"] = "Error"
        result["error"] = str(e)
        return result


def process_eml_archive_bytes(
    *,
    file_bytes: bytes,
    archive_name: str,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    perform_chunking: bool = True,
    chunk_options: Optional[Dict[str, Any]] = None,
    perform_analysis: bool = False,
    api_name: Optional[str] = None,
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    summarize_recursively: bool = False,
    ingest_attachments: bool = False,
    max_depth: int = 1,
) -> List[Dict[str, Any]]:
    """
    Process a ZIP archive of EML files and return a list of per-email result dicts.
    Applies basic guardrails on member count and uncompressed size using archive config limits.
    """
    results: List[Dict[str, Any]] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(file_bytes), 'r')
    except Exception as e:
        logging.error(f"Invalid or unreadable archive '{archive_name}': {e}")
        return [{
            "status": "Error",
            "input_ref": archive_name,
            "media_type": "email",
            "processing_source": f"archive:{archive_name}",
            "error": f"Invalid ZIP archive: {e}",
        }]

    cfg = DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {}) if isinstance(DEFAULT_MEDIA_TYPE_CONFIG, dict) else {}
    max_internal_files = int(cfg.get('max_internal_files', 100))
    max_uncompressed_size = int(cfg.get('max_internal_uncompressed_size_mb', 200)) * 1024 * 1024

    members = zf.infolist()
    if len(members) > max_internal_files:
        return [{
            "status": "Error",
            "input_ref": archive_name,
            "media_type": "email",
            "processing_source": f"archive:{archive_name}",
            "error": f"Archive contains too many files ({len(members)} > {max_internal_files})",
        }]

    total_size = sum(m.file_size for m in members)
    if total_size > max_uncompressed_size:
        return [{
            "status": "Error",
            "input_ref": archive_name,
            "media_type": "email",
            "processing_source": f"archive:{archive_name}",
            "error": f"Archive declared uncompressed size exceeds limit ({total_size} > {max_uncompressed_size} bytes)",
        }]

    group_tag = f"email_archive:{archive_name.rsplit('.', 1)[0]}" if archive_name else None
    base_keywords = list(keywords or [])
    if group_tag:
        try:
            if group_tag not in base_keywords:
                base_keywords.append(group_tag)
        except Exception:
            pass

    for member in members:
        if member.is_dir():
            continue
        # Skip non-EML members
        name_lower = (member.filename or '').lower()
        if not name_lower.endswith('.eml'):
            continue
        try:
            eml_bytes = zf.read(member)
        except Exception as e:
            results.append({
                "status": "Error",
                "input_ref": f"{archive_name}::{member.filename}",
                "media_type": "email",
                "processing_source": f"archive:{archive_name}::{member.filename}",
                "error": f"Failed to read member: {e}",
            })
            continue

        # Process the individual EML
        one = process_email_task(
            file_bytes=eml_bytes,
            filename=member.filename,
            title_override=title_override,
            author_override=author_override,
            keywords=base_keywords,
            perform_chunking=perform_chunking,
            chunk_options=chunk_options,
            perform_analysis=perform_analysis,
            api_name=api_name,
            api_key=api_key,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            summarize_recursively=summarize_recursively,
            ingest_attachments=ingest_attachments,
            max_depth=max_depth,
        )
        # Normalize fields for clarity
        one.setdefault("media_type", "email")
        one.setdefault("status", "Success")
        one["input_ref"] = f"{archive_name}::{member.filename}"
        one["processing_source"] = f"archive:{archive_name}::{member.filename}"
        # Ensure keywords include the archive grouping tag
        try:
            kws = set(one.get("keywords") or [])
            if group_tag:
                kws.add(group_tag)
            one["keywords"] = sorted(list(kws))
        except Exception:
            pass
        results.append(one)

    return results


def process_mbox_bytes(
    *,
    file_bytes: bytes,
    mbox_name: str,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    perform_chunking: bool = True,
    chunk_options: Optional[Dict[str, Any]] = None,
    perform_analysis: bool = False,
    api_name: Optional[str] = None,
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    summarize_recursively: bool = False,
    ingest_attachments: bool = False,
    max_depth: int = 1,
) -> List[Dict[str, Any]]:
    """
    Process an MBOX file (bytes) and return a list of per-email result dicts.
    Uses Python's mailbox.mbox by writing bytes to a temporary file. Applies guardrails
    using the same DEFAULT_MEDIA_TYPE_CONFIG['archive'] limits used for ZIP archives.
    """
    results: List[Dict[str, Any]] = []

    # Guardrails based on archive limits
    cfg = DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {}) if isinstance(DEFAULT_MEDIA_TYPE_CONFIG, dict) else {}
    max_internal_files = int(cfg.get('max_internal_files', 100))
    max_uncompressed_size = int(cfg.get('max_internal_uncompressed_size_mb', 200)) * 1024 * 1024

    # Quick size check against cap
    try:
        if file_bytes is not None and len(file_bytes) > max_uncompressed_size:
            return [{
                "status": "Error",
                "input_ref": mbox_name,
                "media_type": "email",
                "processing_source": f"mbox:{mbox_name}",
                "error": f"MBOX declared size exceeds limit ({len(file_bytes)} > {max_uncompressed_size} bytes)",
            }]
    except Exception:
        pass

    group_tag = f"email_mbox:{mbox_name.rsplit('.', 1)[0]}" if mbox_name else None
    base_keywords = list(keywords or [])
    if group_tag:
        try:
            if group_tag not in base_keywords:
                base_keywords.append(group_tag)
        except Exception:
            pass

    tmp_path = None
    mbox = None
    try:
        # Write to a temp file for mailbox.mbox
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_bytes or b"")
            tmp_path = tmp.name

        mbox = mailbox.mbox(tmp_path)
        # Iterate messages with cap; stage successes, and if cap exceeded, emit a single guardrail error only
        count = 0
        limit_exceeded = False
        staged: List[Dict[str, Any]] = []
        for msg in mbox:
            count += 1
            if count > max_internal_files:
                limit_exceeded = True
                break

            try:
                try:
                    child_bytes = msg.as_bytes(policy=policy.default)  # type: ignore[attr-defined]
                except Exception:
                    # Fallback: use legacy as_bytes without policy
                    child_bytes = msg.as_bytes()  # type: ignore[attr-defined]
            except Exception as e:
                staged.append({
                    "status": "Error",
                    "input_ref": f"{mbox_name}::message_{count}",
                    "media_type": "email",
                    "processing_source": f"mbox:{mbox_name}::message_{count}",
                    "error": f"Failed to extract message bytes: {e}",
                })
                continue

            one = process_email_task(
                file_bytes=child_bytes,
                filename=f"message_{count}.eml",
                title_override=title_override,
                author_override=author_override,
                keywords=base_keywords,
                perform_chunking=perform_chunking,
                chunk_options=chunk_options,
                perform_analysis=perform_analysis,
                api_name=api_name,
                api_key=api_key,
                custom_prompt=custom_prompt,
                system_prompt=system_prompt,
                summarize_recursively=summarize_recursively,
                ingest_attachments=ingest_attachments,
                max_depth=max_depth,
            )
            # Normalize fields
            one.setdefault("media_type", "email")
            one.setdefault("status", "Success")
            one["input_ref"] = f"{mbox_name}::message_{count}"
            one["processing_source"] = f"mbox:{mbox_name}::message_{count}"
            try:
                kws = set(one.get("keywords") or [])
                if group_tag:
                    kws.add(group_tag)
                one["keywords"] = sorted(list(kws))
            except Exception:
                pass
            staged.append(one)

        if limit_exceeded:
            # Emit a single guardrail error entry and ignore any previously staged successes
            return [{
                "status": "Error",
                "input_ref": mbox_name,
                "media_type": "email",
                "processing_source": f"mbox:{mbox_name}",
                "error": f"MBOX contains too many messages (>{max_internal_files})",
            }]
        # Otherwise, return the staged results
        results.extend(staged)
    except Exception as e:
        logging.error(f"Invalid or unreadable MBOX '{mbox_name}': {e}")
        try:
            get_metrics_registry().increment(
                "app_exception_events_total",
                labels={"component": "email_ingest", "event": "mbox_read_failed"},
            )
        except Exception:
            pass
        return [{
            "status": "Error",
            "input_ref": mbox_name,
            "media_type": "email",
            "processing_source": f"mbox:{mbox_name}",
            "error": f"Invalid MBOX file: {e}",
        }]
    finally:
        # Ensure mbox handle is closed before removing the temporary file
        try:
            if mbox is not None:
                mbox.close()
        except Exception:
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "email_ingest", "event": "mbox_close_failed"},
                )
            except Exception:
                pass
        # Cleanup temp file
        try:
            if tmp_path:
                import os
                os.unlink(tmp_path)
        except Exception:
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "email_ingest", "event": "mbox_tmp_cleanup_failed"},
                )
            except Exception:
                pass

    return results


def process_pst_bytes(
    *,
    file_bytes: bytes,
    pst_name: str,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    perform_chunking: bool = True,
    chunk_options: Optional[Dict[str, Any]] = None,
    perform_analysis: bool = False,
    api_name: Optional[str] = None,
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    summarize_recursively: bool = False,
    ingest_attachments: bool = False,
    max_depth: int = 1,
) -> List[Dict[str, Any]]:
    """
    PST/OST container handler with optional pypff integration.
    - If pypff is unavailable, returns a clear informative error (feature-flag behavior).
    - When available, expands messages into RFC822 bytes and processes each via process_email_task.
    - Guardrails: total bytes size check and max message count (reuse archive caps).
    """
    # Grouping keyword for PST/OST containers
    group_tag = f"email_pst:{(pst_name or '').rsplit('.', 1)[0]}" if pst_name else None
    base_keywords = list(keywords or [])
    if group_tag:
        try:
            if group_tag not in base_keywords:
                base_keywords.append(group_tag)
        except Exception:
            pass

    # Guardrails from archive config
    cfg = DEFAULT_MEDIA_TYPE_CONFIG.get('archive', {}) if isinstance(DEFAULT_MEDIA_TYPE_CONFIG, dict) else {}
    max_internal_files = int(cfg.get('max_internal_files', 100))
    max_uncompressed_size = int(cfg.get('max_internal_uncompressed_size_mb', 200)) * 1024 * 1024

    # Quick size check against cap
    try:
        if file_bytes is not None and len(file_bytes) > max_uncompressed_size:
            return [{
                "status": "Error",
                "input_ref": pst_name,
                "media_type": "email",
                "processing_source": f"pst:{pst_name}",
                "keywords": base_keywords,
                "error": f"PST/OST file exceeds size limit ({len(file_bytes)} > {max_uncompressed_size} bytes)",
            }]
    except Exception:
        pass

    # Try to import pypff
    try:
        import pypff  # type: ignore
    except Exception:
        return [{
            "status": "Error",
            "input_ref": pst_name,
            "media_type": "email",
            "processing_source": f"pst:{pst_name}",
            "keywords": base_keywords,
            "error": "PST/OST support not enabled. Install and configure 'pypff' (libpff) or integrate 'readpst' for parsing.",
        }]

    results: List[Dict[str, Any]] = []

    # Write bytes to a temp file for pypff
    tmp_path = None
    pst = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_bytes or b"")
            tmp_path = tmp.name

        pst = pypff.file()
        pst.open(tmp_path)

        # Access root folder
        try:
            root = pst.get_root_folder()
        except Exception:
            root = getattr(pst, 'root_folder', None)

        # Traverse folders and messages up to max_internal_files
        stack: List[Any] = []
        if root is not None:
            stack.append(root)

        count = 0
        while stack:
            folder = stack.pop()
            # Enqueue subfolders
            try:
                num_folders = None
                # Support multiple attribute names across pypff versions
                for attr in ("number_of_sub_folders", "get_number_of_sub_folders"):
                    val = getattr(folder, attr, None)
                    if callable(val):
                        num_folders = int(val())
                        break
                    if isinstance(val, int):
                        num_folders = int(val)
                        break
                if num_folders and num_folders > 0:
                    for i in range(num_folders):
                        sub = None
                        for m in ("get_sub_folder", "get_subfolder", "sub_folders"):
                            getter = getattr(folder, m, None)
                            if callable(getter):
                                try:
                                    sub = getter(i)
                                except Exception:
                                    sub = None
                                break
                        if sub is not None:
                            stack.append(sub)
            except Exception:
                pass

            # Iterate messages
            try:
                num_msgs = None
                for attr in ("number_of_sub_messages", "get_number_of_sub_messages"):
                    val = getattr(folder, attr, None)
                    if callable(val):
                        num_msgs = int(val())
                        break
                    if isinstance(val, int):
                        num_msgs = int(val)
                        break
                if not num_msgs:
                    continue

                for i in range(num_msgs):
                    if count >= max_internal_files:
                        results.append({
                            "status": "Error",
                            "input_ref": pst_name,
                            "media_type": "email",
                            "processing_source": f"pst:{pst_name}",
                            "keywords": base_keywords,
                            "error": f"PST contains too many messages (>{max_internal_files})",
                        })
                        stack.clear()
                        break

                    try:
                        msg = None
                        for m in ("get_sub_message", "get_message", "sub_messages"):
                            getter = getattr(folder, m, None)
                            if callable(getter):
                                msg = getter(i)
                                break
                        if msg is None:
                            continue

                        # Extract basic fields with broad compatibility
                        def _get(obj, names: List[str]) -> Optional[str]:
                            for n in names:
                                v = getattr(obj, n, None)
                                if callable(v):
                                    try:
                                        v = v()
                                    except Exception:
                                        v = None
                                if isinstance(v, (str, bytes)):
                                    return v.decode("utf-8", errors="ignore") if isinstance(v, (bytes, bytearray)) else v
                            return None

                        subject = _get(msg, ["get_subject", "subject"]) or ""
                        sender_name = _get(msg, ["get_sender_name", "sender_name"]) or ""
                        sender_email = _get(msg, ["get_sender_email_address", "sender_email_address"]) or ""
                        plain_body = _get(msg, ["get_plain_text_body", "plain_text_body", "body"])
                        html_body = _get(msg, ["get_html_body", "html_body"]) if not plain_body else None
                        # Recipients
                        recipients_to: List[str] = []
                        recipients_cc: List[str] = []
                        recipients_bcc: List[str] = []
                        try:
                            # Common pypff APIs
                            num_rcpts = 0
                            for attr in ("get_number_of_recipients", "number_of_recipients"):
                                val = getattr(msg, attr, None)
                                if callable(val):
                                    num_rcpts = int(val())
                                    break
                                if isinstance(val, int):
                                    num_rcpts = int(val)
                                    break
                            for ri in range(int(num_rcpts or 0)):
                                rcpt = None
                                for mname in ("get_recipient", "recipient"):
                                    getter = getattr(msg, mname, None)
                                    if callable(getter):
                                        try:
                                            rcpt = getter(ri)
                                        except Exception:
                                            rcpt = None
                                        break
                                if rcpt is None:
                                    continue
                                # Extract email address
                                rcpt_email = _get(rcpt, ["get_email_address", "email_address"]) or ""
                                # Determine type (1=orig, 2=to, 3=cc, 4=bcc in some builds)
                                rcpt_type = None
                                for tname in ("get_type", "type"):
                                    tv = getattr(rcpt, tname, None)
                                    if callable(tv):
                                        try:
                                            rcpt_type = int(tv())
                                        except Exception:
                                            rcpt_type = None
                                    elif isinstance(tv, int):
                                        rcpt_type = int(tv)
                                if rcpt_type in (2, None) and rcpt_email:  # default to To
                                    recipients_to.append(rcpt_email)
                                elif rcpt_type == 3 and rcpt_email:
                                    recipients_cc.append(rcpt_email)
                                elif rcpt_type == 4 and rcpt_email:
                                    recipients_bcc.append(rcpt_email)
                        except Exception:
                            pass
                        # Date
                        msg_date = _get(msg, ["get_delivery_time", "delivery_time", "get_client_submit_time", "client_submit_time"]) or None

                        from_str = (f"{sender_name} <{sender_email}>".strip() if sender_email else sender_name) or "Unknown"

                        # Reconstruct a minimal RFC822 email
                        em = EmailMessage()
                        em["From"] = from_str
                        if subject:
                            em["Subject"] = subject
                        # Normalize and set recipients once
                        def _norm_list(vals: List[str]) -> List[str]:
                            uniq = []
                            seen = set()
                            for v in vals or []:
                                s = (v or "").strip().lower()
                                if s and s not in seen:
                                    seen.add(s); uniq.append(s)
                            return uniq
                        recipients_to = _norm_list(recipients_to)
                        recipients_cc = _norm_list(recipients_cc)
                        recipients_bcc = _norm_list(recipients_bcc)
                        if recipients_to:
                            em["To"] = ", ".join(recipients_to)
                        else:
                            em["To"] = "undisclosed-recipients:;"
                        if recipients_cc:
                            em["Cc"] = ", ".join(recipients_cc)
                        if recipients_bcc:
                            em["Bcc"] = ", ".join(recipients_bcc)
                        date_header_value = None
                        if msg_date:
                            try:
                                # Normalize to RFC2822
                                from datetime import timezone
                                from email.utils import parsedate_to_datetime, format_datetime
                                dt = None
                                if hasattr(msg_date, 'isoformat'):
                                    dt = msg_date  # datetime-like
                                elif isinstance(msg_date, (bytes, bytearray)):
                                    s = msg_date.decode('utf-8', errors='ignore')
                                    dt = parsedate_to_datetime(s)
                                elif isinstance(msg_date, str):
                                    dt = parsedate_to_datetime(msg_date)
                                if dt is not None and getattr(dt, 'tzinfo', None) is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                if dt is not None:
                                    date_header_value = format_datetime(dt)
                                    em["Date"] = date_header_value
                                else:
                                    date_header_value = str(msg_date)
                                    em["Date"] = date_header_value
                            except Exception:
                                try:
                                    date_header_value = str(msg_date)
                                    em["Date"] = date_header_value
                                except Exception:
                                    pass
                        if plain_body:
                            em.set_content(plain_body)
                        elif html_body:
                            try:
                                em.add_alternative(html_body, subtype="html")
                            except Exception:
                                em.set_content(html_body)
                        else:
                            em.set_content("")
                        # Collect attachment metadata (no bytes loaded)
                        attachments_meta: List[Dict[str, Any]] = []
                        try:
                            num_att = 0
                            for an in ("get_number_of_attachments", "number_of_attachments"):
                                av = getattr(msg, an, None)
                                if callable(av):
                                    num_att = int(av())
                                    break
                                if isinstance(av, int):
                                    num_att = int(av)
                                    break
                            for ai in range(int(num_att or 0)):
                                att = None
                                for g in ("get_attachment", "attachment"):
                                    gv = getattr(msg, g, None)
                                    if callable(gv):
                                        try:
                                            att = gv(ai)
                                        except Exception:
                                            att = None
                                        break
                                if att is None:
                                    continue
                                name = _get(att, ["get_name", "name"]) or None
                                size = None
                                for szn in ("get_size", "size"):
                                    sv = getattr(att, szn, None)
                                    if callable(sv):
                                        try:
                                            size = int(sv())
                                        except Exception:
                                            size = None
                                        break
                                    if isinstance(sv, int):
                                        size = int(sv)
                                        break
                                content_type = _get(att, ["get_mime_type", "mime_type"]) or None
                                attachments_meta.append({
                                    "name": name,
                                    "content_type": content_type,
                                    "size": size,
                                })
                        except Exception:
                            attachments_meta = []
                        try:
                            child_bytes = em.as_bytes(policy=policy.default)
                        except Exception:
                            child_bytes = em.as_bytes()

                        count += 1
                        one = process_email_task(
                            file_bytes=child_bytes,
                            filename=f"message_{count}.eml",
                            title_override=title_override,
                            author_override=author_override,
                            keywords=base_keywords,
                            perform_chunking=perform_chunking,
                            chunk_options=chunk_options,
                            perform_analysis=perform_analysis,
                            api_name=api_name,
                            api_key=api_key,
                            custom_prompt=custom_prompt,
                            system_prompt=system_prompt,
                            summarize_recursively=summarize_recursively,
                            ingest_attachments=ingest_attachments,
                            max_depth=max_depth,
                        )
                        one.setdefault("media_type", "email")
                        one.setdefault("status", "Success")
                        one["input_ref"] = f"{pst_name}::message_{count}"
                        one["processing_source"] = f"pst:{pst_name}::message_{count}"
                        try:
                            kws = set(one.get("keywords") or [])
                            if group_tag:
                                kws.add(group_tag)
                            one["keywords"] = sorted(list(kws))
                        except Exception:
                            pass
                        # Augment metadata with PST-derived recipients/date/attachments for robustness
                        try:
                            if attachments_meta:
                                md = one.get("metadata") or {}
                                emd = md.get("email") or {}
                                exist = emd.get("attachments") or []
                                if isinstance(exist, list):
                                    exist.extend(attachments_meta)
                                else:
                                    exist = attachments_meta
                                emd["attachments"] = exist
                                # Recipients fields (string lists expected by codebase)
                                if recipients_to:
                                    emd.setdefault("to", ", ".join(recipients_to))
                                if recipients_cc:
                                    emd.setdefault("cc", ", ".join(recipients_cc))
                                if recipients_bcc:
                                    emd.setdefault("bcc", ", ".join(recipients_bcc))
                                if date_header_value and not emd.get("date"):
                                    emd["date"] = date_header_value
                                md["email"] = emd
                                one["metadata"] = md
                        except Exception:
                            pass
                        results.append(one)
                    except Exception as e:
                        results.append({
                            "status": "Error",
                            "input_ref": f"{pst_name}::message_{count+1}",
                            "media_type": "email",
                            "processing_source": f"pst:{pst_name}::message_{count+1}",
                            "keywords": base_keywords,
                            "error": f"Failed to extract PST message: {e}",
                        })
            except Exception:
                continue

        return results or [{
            "status": "Error",
            "input_ref": pst_name,
            "media_type": "email",
            "processing_source": f"pst:{pst_name}",
            "keywords": base_keywords,
            "error": "No messages found in PST/OST.",
        }]
    except Exception as e:
        logging.error(f"Invalid or unreadable PST/OST '{pst_name}': {e}")
        try:
            get_metrics_registry().increment(
                "app_exception_events_total",
                labels={"component": "email_ingest", "event": "pst_read_failed"},
            )
        except Exception:
            pass
        return [{
            "status": "Error",
            "input_ref": pst_name,
            "media_type": "email",
            "processing_source": f"pst:{pst_name}",
            "keywords": base_keywords,
            "error": f"Invalid PST/OST file: {e}",
        }]
    finally:
        if pst is not None:
            try:
                pst.close()
            except Exception as close_err:
                logging.warning(f"Failed to close PST/OST reader for '{pst_name}': {close_err}")
                try:
                    get_metrics_registry().increment(
                        "app_warning_events_total",
                        labels={"component": "email_ingest", "event": "pst_close_failed"},
                    )
                except Exception:
                    pass
        try:
            if tmp_path:
                os.unlink(tmp_path)
        except Exception as cleanup_err:
            logging.warning(f"Failed to remove temporary PST/OST file '{tmp_path}': {cleanup_err}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "email_ingest", "event": "pst_tmp_cleanup_failed"},
                )
            except Exception:
                pass
