"""External integration adapters.

This module includes adapters for integration operations:
- webhook: Send webhooks
- notify: Send notifications
- mcp_tool: Execute MCP tools
- s3_upload: Upload to S3
- s3_download: Download from S3
- github_create_issue: Create GitHub issue
- email_send: Send email
- podcast_rss_publish: Publish/merge podcast RSS feeds
- kanban: Manage Kanban boards
- chatbooks: Manage chatbooks
- character_chat: Character chat
"""

from tldw_Server_API.app.core.Workflows.adapters.integration.email import (
    run_email_send_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.integration.github import (
    run_github_create_issue_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.integration.mcp import (
    run_mcp_tool_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.integration.messaging import (
    run_character_chat_adapter,
    run_chatbooks_adapter,
    run_kanban_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.integration.storage import (
    run_s3_download_adapter,
    run_s3_upload_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.integration.podcast_rss import (
    run_podcast_rss_publish_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.integration.webhook import (
    run_notify_adapter,
    run_webhook_adapter,
)

__all__ = [
    "run_webhook_adapter",
    "run_notify_adapter",
    "run_mcp_tool_adapter",
    "run_s3_upload_adapter",
    "run_s3_download_adapter",
    "run_podcast_rss_publish_adapter",
    "run_github_create_issue_adapter",
    "run_email_send_adapter",
    "run_kanban_adapter",
    "run_chatbooks_adapter",
    "run_character_chat_adapter",
]
