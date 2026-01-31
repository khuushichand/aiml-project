"""Pydantic config models for integration adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class WebhookConfig(BaseAdapterConfig):
    """Config for webhook adapter."""

    url: str = Field(..., description="Webhook URL (required)")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        "POST", description="HTTP method"
    )
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    body: Optional[Any] = Field(None, description="Request body (templated)")
    content_type: str = Field("application/json", description="Content-Type header")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Request timeout")
    retry_count: int = Field(0, ge=0, le=5, description="Number of retries")
    retry_delay_ms: int = Field(1000, ge=100, description="Delay between retries in ms")
    auth: Optional[Dict[str, str]] = Field(None, description="Authentication config")


class NotifyConfig(BaseAdapterConfig):
    """Config for notification adapter."""

    channel: Literal["slack", "discord", "email", "webhook", "teams"] = Field(
        "webhook", description="Notification channel"
    )
    message: str = Field(..., description="Notification message (templated)")
    title: Optional[str] = Field(None, description="Notification title")
    url: Optional[str] = Field(None, description="Webhook/endpoint URL")
    recipients: Optional[List[str]] = Field(None, description="Recipients (for email)")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="Attachments")


class MCPToolConfig(BaseAdapterConfig):
    """Config for MCP tool execution adapter."""

    tool_name: str = Field(..., description="Name of the MCP tool to execute")
    server: Optional[str] = Field(None, description="MCP server to use")
    arguments: Optional[Dict[str, Any]] = Field(None, description="Tool arguments")
    timeout_seconds: int = Field(60, ge=1, le=600, description="Execution timeout")


class S3UploadConfig(BaseAdapterConfig):
    """Config for S3 upload adapter."""

    file_uri: str = Field(..., description="file:// path to upload (required)")
    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key (templated)")
    region: Optional[str] = Field(None, description="AWS region")
    acl: Optional[str] = Field(None, description="S3 ACL (private, public-read, etc.)")
    content_type: Optional[str] = Field(None, description="Content-Type override")
    metadata: Optional[Dict[str, str]] = Field(None, description="S3 object metadata")
    storage_class: Optional[str] = Field(None, description="S3 storage class")


class S3DownloadConfig(BaseAdapterConfig):
    """Config for S3 download adapter."""

    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key (templated)")
    region: Optional[str] = Field(None, description="AWS region")
    output_filename: Optional[str] = Field(None, description="Output filename (optional)")


class GitHubCreateIssueConfig(BaseAdapterConfig):
    """Config for GitHub issue creation adapter."""

    repo: str = Field(..., description="Repository (owner/name)")
    title: str = Field(..., description="Issue title (templated)")
    body: Optional[str] = Field(None, description="Issue body (templated)")
    labels: Optional[List[str]] = Field(None, description="Issue labels")
    assignees: Optional[List[str]] = Field(None, description="Issue assignees")
    milestone: Optional[int] = Field(None, description="Milestone number")


class EmailSendConfig(BaseAdapterConfig):
    """Config for email sending adapter."""

    to: List[str] = Field(..., description="Recipient email addresses")
    subject: str = Field(..., description="Email subject (templated)")
    body: str = Field(..., description="Email body (templated)")
    body_type: Literal["text", "html"] = Field("text", description="Body content type")
    cc: Optional[List[str]] = Field(None, description="CC recipients")
    bcc: Optional[List[str]] = Field(None, description="BCC recipients")
    from_address: Optional[str] = Field(None, description="From address override")
    reply_to: Optional[str] = Field(None, description="Reply-To address")
    attachments: Optional[List[str]] = Field(None, description="file:// URIs of attachments")


class KanbanConfig(BaseAdapterConfig):
    """Config for Kanban board adapter."""

    action: Literal["create_board", "create_card", "move_card", "update_card", "delete_card", "list_cards", "list_boards"] = Field(
        "list_cards", description="Action to perform"
    )
    board_id: Optional[str] = Field(None, description="Board ID")
    board_name: Optional[str] = Field(None, description="Board name (for create)")
    card_id: Optional[str] = Field(None, description="Card ID")
    title: Optional[str] = Field(None, description="Card title")
    description: Optional[str] = Field(None, description="Card description (templated)")
    column: Optional[str] = Field(None, description="Target column")
    labels: Optional[List[str]] = Field(None, description="Card labels")
    due_date: Optional[str] = Field(None, description="Due date (ISO format)")
    assignees: Optional[List[str]] = Field(None, description="Card assignees")


class ChatbooksConfig(BaseAdapterConfig):
    """Config for chatbooks adapter."""

    action: Literal["export", "import", "list", "delete"] = Field(
        "list", description="Action to perform"
    )
    chatbook_id: Optional[str] = Field(None, description="Chatbook ID")
    format: Literal["json", "markdown"] = Field("json", description="Export/import format")
    include_metadata: bool = Field(True, description="Include metadata in export")
    file_uri: Optional[str] = Field(None, description="file:// path for import/export")


class CharacterChatConfig(BaseAdapterConfig):
    """Config for character chat adapter."""

    character_id: Optional[str] = Field(None, description="Character ID")
    character_card: Optional[Dict[str, Any]] = Field(None, description="Character card data")
    message: str = Field(..., description="User message (templated)")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID")
    system_prompt: Optional[str] = Field(None, description="System prompt override")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model to use")
    temperature: float = Field(0.8, ge=0, le=2, description="Temperature for responses")
    max_tokens: Optional[int] = Field(None, ge=1, description="Max response tokens")
