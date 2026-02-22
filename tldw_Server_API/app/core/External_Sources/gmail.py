from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

from tldw_Server_API.app.core.http_client import afetch

from .connector_base import BaseConnector


class GmailConnector(BaseConnector):
    name = "gmail"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_base: str | None = None,
    ):
        super().__init__(
            client_id=client_id or os.getenv("CONNECTOR_GMAIL_CLIENT_ID"),
            client_secret=client_secret or os.getenv("CONNECTOR_GMAIL_CLIENT_SECRET"),
            redirect_base=redirect_base or os.getenv("CONNECTOR_REDIRECT_BASE_URL"),
        )

    def authorize_url(
        self,
        state: str | None = None,
        scopes: list[str] | None = None,
        redirect_path: str = "/api/v1/connectors/providers/gmail/callback",
    ) -> str:
        redirect_uri = f"{self.redirect_base}{redirect_path}"
        if not self.client_id:
            return f"{redirect_uri}?scaffold=1&state={state or ''}"
        scope = " ".join(
            scopes
            or [
                "https://www.googleapis.com/auth/gmail.readonly",
                "openid",
                "email",
                "profile",
            ]
        )
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        resp = await afetch(method="POST", url=token_url, data=data, timeout=30)
        try:
            resp.raise_for_status()
            tok = resp.json()
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token"),
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "scope": tok.get("scope"),
            "provider": self.name,
            "display_name": "Gmail Account",
            "email": None,
        }

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any] | None:
        if not (self.client_id and self.client_secret and refresh_token):
            return None
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        resp = await afetch(method="POST", url=token_url, data=data, timeout=30)
        try:
            resp.raise_for_status()
            tok = resp.json()
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        return {
            "access_token": tok.get("access_token"),
            "refresh_token": tok.get("refresh_token") or refresh_token,
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "scope": tok.get("scope"),
        }

    async def list_sources(
        self,
        account: dict[str, Any],
        parent_remote_id: str | None = None,
        *,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        # Gmail labels endpoint does not support cursor/page_size for this call.
        _ = page_size
        _ = cursor
        token = (account.get("tokens") or {}).get("access_token") or account.get(
            "access_token"
        )
        if not token:
            return [], None
        headers = {"Authorization": f"Bearer {token}"}
        resp = await afetch(
            method="GET",
            url="https://gmail.googleapis.com/gmail/v1/users/me/labels",
            headers=headers,
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        labels = data.get("labels") or []
        items: list[dict[str, Any]] = []
        for label in labels:
            label_id = str(label.get("id") or "").strip()
            label_name = str(label.get("name") or "").strip()
            if not label_id:
                continue
            if parent_remote_id and label_id != str(parent_remote_id).strip():
                continue
            items.append(
                {
                    "id": label_id,
                    "name": label_name or label_id,
                    "type": "folder",
                    "label_type": str(label.get("type") or "").lower() or None,
                    "messages_total": int(label.get("messagesTotal") or 0),
                    "messages_unread": int(label.get("messagesUnread") or 0),
                }
            )
        items.sort(key=lambda item: str(item.get("name") or "").lower())
        return items, None

    async def list_messages(
        self,
        account: dict[str, Any],
        *,
        label_id: str | None = None,
        page_size: int = 100,
        cursor: str | None = None,
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        token = (account.get("tokens") or {}).get("access_token") or account.get(
            "access_token"
        )
        if not token:
            return [], None
        headers = {"Authorization": f"Bearer {token}"}
        params: dict[str, Any] = {
            "maxResults": max(1, min(int(page_size), 500)),
        }
        if label_id:
            params["labelIds"] = str(label_id)
        if cursor:
            params["pageToken"] = str(cursor)
        if query:
            params["q"] = str(query)
        resp = await afetch(
            method="GET",
            url="https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers=headers,
            params=params,
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        messages = data.get("messages") or []
        items = []
        for row in messages:
            if not isinstance(row, dict):
                continue
            msg_id = str(row.get("id") or "").strip()
            if not msg_id:
                continue
            items.append(
                {
                    "id": msg_id,
                    "threadId": row.get("threadId"),
                }
            )
        return items, data.get("nextPageToken")

    async def list_history(
        self,
        account: dict[str, Any],
        *,
        start_history_id: str,
        label_id: str | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        token = (account.get("tokens") or {}).get("access_token") or account.get(
            "access_token"
        )
        if not token:
            return [], None, None

        start_history = str(start_history_id or "").strip()
        if not start_history:
            return [], None, None

        headers = {"Authorization": f"Bearer {token}"}
        params: dict[str, Any] = {
            "startHistoryId": start_history,
            "maxResults": max(1, min(int(page_size), 500)),
            "historyTypes": [
                "messageAdded",
                "messageDeleted",
                "labelAdded",
                "labelRemoved",
            ],
        }
        if label_id:
            params["labelId"] = str(label_id)
        if cursor:
            params["pageToken"] = str(cursor)

        resp = await afetch(
            method="GET",
            url="https://gmail.googleapis.com/gmail/v1/users/me/history",
            headers=headers,
            params=params,
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()

        history_rows = data.get("history") or []
        items_by_id: dict[str, dict[str, Any]] = {}
        ordered_ids: list[str] = []
        max_history_id: str | None = None

        def _merge_history_id(current: str | None, candidate: Any) -> str | None:
            text = str(candidate or "").strip()
            if not text:
                return current
            if not current:
                return text
            try:
                return text if int(text) >= int(current) else current
            except (TypeError, ValueError):
                return text if text >= current else current

        def _ensure_item(message_id: str, thread_id: Any) -> dict[str, Any]:
            existing = items_by_id.get(message_id)
            if existing is not None:
                if existing.get("threadId") is None and thread_id is not None:
                    existing["threadId"] = thread_id
                return existing

            created = {
                "id": message_id,
                "threadId": thread_id,
                "historyId": None,
                "message_added": False,
                "message_deleted": False,
                "labels_added": set(),
                "labels_removed": set(),
            }
            items_by_id[message_id] = created
            ordered_ids.append(message_id)
            return created

        def _coerce_label_ids(raw_value: Any) -> list[str]:
            if not isinstance(raw_value, list):
                return []
            out: list[str] = []
            for label in raw_value:
                text = str(label or "").strip()
                if text:
                    out.append(text)
            return out

        for row in history_rows:
            if not isinstance(row, dict):
                continue
            row_history_id = str(row.get("id") or row.get("historyId") or "").strip() or None
            max_history_id = _merge_history_id(max_history_id, row_history_id)

            for change in row.get("messagesAdded") or []:
                if not isinstance(change, dict):
                    continue
                message = change.get("message")
                if not isinstance(message, dict):
                    continue
                message_id = str(message.get("id") or "").strip()
                if not message_id:
                    continue
                item = _ensure_item(message_id, message.get("threadId"))
                item["message_added"] = True
                item["historyId"] = _merge_history_id(item.get("historyId"), row_history_id)

            for change in row.get("messagesDeleted") or []:
                if not isinstance(change, dict):
                    continue
                message = change.get("message")
                if not isinstance(message, dict):
                    continue
                message_id = str(message.get("id") or "").strip()
                if not message_id:
                    continue
                item = _ensure_item(message_id, message.get("threadId"))
                item["message_deleted"] = True
                item["historyId"] = _merge_history_id(item.get("historyId"), row_history_id)

            for change in row.get("labelsAdded") or []:
                if not isinstance(change, dict):
                    continue
                message = change.get("message")
                if not isinstance(message, dict):
                    continue
                message_id = str(message.get("id") or "").strip()
                if not message_id:
                    continue
                item = _ensure_item(message_id, message.get("threadId"))
                item["historyId"] = _merge_history_id(item.get("historyId"), row_history_id)
                for label_id in _coerce_label_ids(change.get("labelIds")):
                    item["labels_added"].add(label_id)

            for change in row.get("labelsRemoved") or []:
                if not isinstance(change, dict):
                    continue
                message = change.get("message")
                if not isinstance(message, dict):
                    continue
                message_id = str(message.get("id") or "").strip()
                if not message_id:
                    continue
                item = _ensure_item(message_id, message.get("threadId"))
                item["historyId"] = _merge_history_id(item.get("historyId"), row_history_id)
                for label_id in _coerce_label_ids(change.get("labelIds")):
                    item["labels_removed"].add(label_id)

            # Fallback: some payloads contain only `messages`.
            row_messages = row.get("messages")
            if isinstance(row_messages, list):
                for message in row_messages:
                    if not isinstance(message, dict):
                        continue
                    message_id = str(message.get("id") or "").strip()
                    if not message_id:
                        continue
                    item = _ensure_item(message_id, message.get("threadId"))
                    item["historyId"] = _merge_history_id(item.get("historyId"), row_history_id)
                    # Unknown change type; force message fetch for reconciliation.
                    item["message_added"] = True

        items: list[dict[str, Any]] = []
        for message_id in ordered_ids:
            item = items_by_id[message_id]
            labels_added = {
                str(label).strip()
                for label in (item.get("labels_added") or set())
                if str(label).strip()
            }
            labels_removed = {
                str(label).strip()
                for label in (item.get("labels_removed") or set())
                if str(label).strip()
            }
            # Net out contradictory operations in the same history window.
            net_added = sorted(label for label in labels_added if label not in labels_removed)
            net_removed = sorted(label for label in labels_removed if label not in labels_added)
            items.append(
                {
                    "id": item["id"],
                    "threadId": item.get("threadId"),
                    "historyId": item.get("historyId"),
                    "message_added": bool(item.get("message_added")),
                    "message_deleted": bool(item.get("message_deleted")),
                    "labels_added": net_added,
                    "labels_removed": net_removed,
                }
            )

        latest_history_id = _merge_history_id(max_history_id, data.get("historyId"))
        return items, data.get("nextPageToken"), latest_history_id

    async def get_message(
        self,
        account: dict[str, Any],
        *,
        message_id: str,
        format: str = "full",
    ) -> dict[str, Any]:
        token = (account.get("tokens") or {}).get("access_token") or account.get(
            "access_token"
        )
        if not token:
            return {}
        headers = {"Authorization": f"Bearer {token}"}
        resp = await afetch(
            method="GET",
            url=f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            headers=headers,
            params={"format": format},
            timeout=30,
        )
        try:
            resp.raise_for_status()
            data = resp.json() or {}
        finally:
            close = getattr(resp, "aclose", None)
            if callable(close):
                await close()
        return data if isinstance(data, dict) else {}
