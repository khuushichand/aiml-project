"""Pydantic config models for integration adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class WebhookConfig(BaseAdapterConfig):
    """Config for webhook adapter."""

    url: str = Field(..., description="Webhook URL (required)")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        "POST", description="HTTP method"
    )
    headers: dict[str, str] | None = Field(None, description="HTTP headers")
    body: Any | None = Field(None, description="Request body (templated)")
    content_type: str = Field("application/json", description="Content-Type header")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Request timeout")
    retry_count: int = Field(0, ge=0, le=5, description="Number of retries")
    retry_delay_ms: int = Field(1000, ge=100, description="Delay between retries in ms")
    auth: dict[str, str] | None = Field(None, description="Authentication config")


class NotifyConfig(BaseAdapterConfig):
    """Config for notification adapter."""

    channel: Literal["slack", "discord", "email", "webhook", "teams"] = Field(
        "webhook", description="Notification channel"
    )
    message: str = Field(..., description="Notification message (templated)")
    title: str | None = Field(None, description="Notification title")
    url: str | None = Field(None, description="Webhook/endpoint URL")
    recipients: list[str] | None = Field(None, description="Recipients (for email)")
    attachments: list[dict[str, Any]] | None = Field(None, description="Attachments")


class MCPToolConfig(BaseAdapterConfig):
    """Config for MCP tool execution adapter."""

    tool_name: str = Field(..., description="Name of the MCP tool to execute")
    server: str | None = Field(None, description="MCP server to use")
    arguments: dict[str, Any] | None = Field(None, description="Tool arguments")
    timeout_seconds: int = Field(60, ge=1, le=600, description="Execution timeout")


class ACPStageConfig(BaseAdapterConfig):
    """Config for ACP-backed workflow stage execution."""

    stage: str = Field(..., description="Logical stage name (e.g., plan, impl, test)")
    prompt_template: str | None = Field(
        None,
        description="Templated user prompt (rendered with workflow context)",
    )
    prompt: list[dict[str, Any]] | str | None = Field(
        None,
        description="ACP prompt payload. If string, treated as a user message.",
    )
    session_id: str | None = Field(
        None,
        description="Optional ACP session id override",
    )
    session_context_key: str = Field(
        "acp_session_id",
        description="Context key used to reuse/persist ACP session id",
    )
    create_session: bool = Field(
        True,
        description="Create ACP session when session id is not provided/resolved",
    )
    cwd: str = Field("/workspace", description="ACP session working directory")
    agent_type: str | None = Field(None, description="Optional ACP agent type")
    persona_id: str | None = Field(None, description="Optional ACP persona id")
    workspace_id: str | None = Field(None, description="Optional ACP workspace id")
    workspace_group_id: str | None = Field(None, description="Optional ACP workspace group id")
    scope_snapshot_id: str | None = Field(None, description="Optional ACP scope snapshot id")
    timeout_seconds: int = Field(
        300,
        ge=1,
        le=3600,
        description="Timeout in seconds for ACP prompt execution",
    )
    review_counter_key: str | None = Field(
        None,
        description="Context counter key used to guard review loops",
    )
    max_review_loops: int | None = Field(
        None,
        ge=1,
        le=20,
        description="Maximum allowed review iterations before blocking",
    )
    fail_on_error: bool = Field(
        False,
        description="Raise AdapterError when normalized stage outcome is error/blocked",
    )


class S3UploadConfig(BaseAdapterConfig):
    """Config for S3 upload adapter."""

    file_uri: str = Field(..., description="file:// path to upload (required)")
    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key (templated)")
    region: str | None = Field(None, description="AWS region")
    acl: str | None = Field(None, description="S3 ACL (private, public-read, etc.)")
    content_type: str | None = Field(None, description="Content-Type override")
    metadata: dict[str, str] | None = Field(None, description="S3 object metadata")
    storage_class: str | None = Field(None, description="S3 storage class")


class S3DownloadConfig(BaseAdapterConfig):
    """Config for S3 download adapter."""

    bucket: str = Field(..., description="S3 bucket name")
    key: str = Field(..., description="S3 object key (templated)")
    region: str | None = Field(None, description="AWS region")
    output_filename: str | None = Field(None, description="Output filename (optional)")


class GitHubCreateIssueConfig(BaseAdapterConfig):
    """Config for GitHub issue creation adapter."""

    repo: str = Field(..., description="Repository (owner/name)")
    title: str = Field(..., description="Issue title (templated)")
    body: str | None = Field(None, description="Issue body (templated)")
    labels: list[str] | None = Field(None, description="Issue labels")
    assignees: list[str] | None = Field(None, description="Issue assignees")
    milestone: int | None = Field(None, description="Milestone number")


class EmailSendConfig(BaseAdapterConfig):
    """Config for email sending adapter."""

    to: list[str] = Field(..., description="Recipient email addresses")
    subject: str = Field(..., description="Email subject (templated)")
    body: str = Field(..., description="Email body (templated)")
    body_type: Literal["text", "html"] = Field("text", description="Body content type")
    cc: list[str] | None = Field(None, description="CC recipients")
    bcc: list[str] | None = Field(None, description="BCC recipients")
    from_address: str | None = Field(None, description="From address override")
    reply_to: str | None = Field(None, description="Reply-To address")
    attachments: list[str] | None = Field(None, description="file:// URIs of attachments")


class KanbanConfig(BaseAdapterConfig):
    """Config for Kanban board adapter."""

    action: Literal["create_board", "create_card", "move_card", "update_card", "delete_card", "list_cards", "list_boards"] = Field(
        "list_cards", description="Action to perform"
    )
    board_id: str | None = Field(None, description="Board ID")
    board_name: str | None = Field(None, description="Board name (for create)")
    card_id: str | None = Field(None, description="Card ID")
    title: str | None = Field(None, description="Card title")
    description: str | None = Field(None, description="Card description (templated)")
    column: str | None = Field(None, description="Target column")
    labels: list[str] | None = Field(None, description="Card labels")
    due_date: str | None = Field(None, description="Due date (ISO format)")
    assignees: list[str] | None = Field(None, description="Card assignees")


class ChatbooksConfig(BaseAdapterConfig):
    """Config for chatbooks adapter."""

    action: Literal["export", "import", "list", "delete"] = Field(
        "list", description="Action to perform"
    )
    chatbook_id: str | None = Field(None, description="Chatbook ID")
    format: Literal["json", "markdown"] = Field("json", description="Export/import format")
    include_metadata: bool = Field(True, description="Include metadata in export")
    file_uri: str | None = Field(None, description="file:// path for import/export")


class CharacterChatConfig(BaseAdapterConfig):
    """Config for character chat adapter."""

    character_id: str | None = Field(None, description="Character ID")
    character_card: dict[str, Any] | None = Field(None, description="Character card data")
    message: str = Field(..., description="User message (templated)")
    conversation_id: str | None = Field(None, description="Existing conversation ID")
    system_prompt: str | None = Field(None, description="System prompt override")
    provider: str | None = Field(None, description="LLM provider")
    model: str | None = Field(None, description="Model to use")
    temperature: float = Field(0.8, ge=0, le=2, description="Temperature for responses")
    max_tokens: int | None = Field(None, ge=1, description="Max response tokens")


class PodcastRSSPublishConfig(BaseAdapterConfig):
    """Config for podcast RSS publication adapter."""

    feed_uri: str = Field(
        ...,
        description="Destination RSS feed file path/URI (supports file://)",
    )
    episode: dict[str, Any] = Field(
        ...,
        description="Episode payload (title, guid, audio/file URI, description, link, pub_date)",
    )
    channel: dict[str, Any] | None = Field(
        None,
        description="Optional channel metadata overrides (title, link, description, language)",
    )
    max_items: int = Field(200, ge=1, le=5000, description="Maximum items retained in feed")
    expected_version: int | None = Field(
        None,
        ge=0,
        description="Optimistic concurrency token; compared with current item-count version",
    )
    allow_remote_fetch: bool = Field(
        False,
        description="Allow fetching source_feed_url when destination feed does not yet exist",
    )
    source_feed_url: str | None = Field(
        None,
        description="Optional source RSS URL to seed initial feed when allow_remote_fetch=true",
    )
