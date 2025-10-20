import pytest

from tldw_Server_API.app.core.Notifications.service import NotificationsService


class _FakeEmailService:
    def __init__(self):
        self.calls = []

    async def send_email(self, *, to_email, subject, html_body, text_body, attachments=None):
        self.calls.append(
            {
                "to_email": to_email,
                "subject": subject,
                "html_body": html_body,
                "text_body": text_body,
                "attachments": attachments,
            }
        )
        return True


class _FakeDocService:
    def __init__(self):
        self.calls = []

    def create_manual_document(
        self,
        *,
        title,
        content,
        document_type,
        metadata,
        provider,
        model,
        conversation_id=None,
    ):
        self.calls.append(
            {
                "title": title,
                "content": content,
                "document_type": document_type,
                "metadata": metadata,
                "provider": provider,
                "model": model,
                "conversation_id": conversation_id,
            }
        )
        return 42


@pytest.mark.asyncio
async def test_notifications_email_delivery(monkeypatch):
    fake_email = _FakeEmailService()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Notifications.service.get_email_service",
        lambda: fake_email,
    )

    svc = NotificationsService(user_id=1, user_email="user@example.com")
    result = await svc.deliver_email(
        subject="Hello",
        html_body="<p>Hello</p>",
        text_body="Hello",
        recipients=None,
        attachments=[{"filename": "demo.txt", "content": "ZXhhbXBsZQ=="}],
    )

    assert result.channel == "email"
    assert result.status == "sent"
    assert fake_email.calls
    call = fake_email.calls[0]
    assert call["to_email"] == "user@example.com"
    assert call["subject"] == "Hello"


@pytest.mark.asyncio
async def test_notifications_email_skips_without_recipient(monkeypatch):
    fake_email = _FakeEmailService()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Notifications.service.get_email_service",
        lambda: fake_email,
    )

    svc = NotificationsService(user_id=1, user_email=None)
    result = await svc.deliver_email(
        subject="Nope",
        html_body="<p>ignored</p>",
        text_body=None,
        recipients=[],
        fallback_to_user_email=False,
    )

    assert result.status == "skipped"
    assert result.details["reason"] == "no_recipients"
    assert not fake_email.calls


def test_notifications_chatbook_delivery(monkeypatch):
    fake_doc = _FakeDocService()
    svc = NotificationsService(user_id=2, user_email=None)

    monkeypatch.setattr(
        NotificationsService,
        "_ensure_doc_service",
        lambda self: fake_doc,
    )

    result = svc.deliver_chatbook(
        title="Watchlist Brief",
        content="Summary content",
        description="Daily brief",
        metadata={"source": "watchlist"},
    )

    assert result.channel == "chatbook"
    assert result.status == "stored"
    assert fake_doc.calls
    call = fake_doc.calls[0]
    assert call["metadata"]["source"] == "watchlist"
    assert call["metadata"]["description"] == "Daily brief"
