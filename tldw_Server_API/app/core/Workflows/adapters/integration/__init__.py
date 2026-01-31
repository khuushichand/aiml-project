"""External integration adapters.

This module includes adapters for integration operations:
- webhook: Send webhooks
- notify: Send notifications
- mcp_tool: Execute MCP tools
- s3_upload: Upload to S3
- s3_download: Download from S3
- github_create_issue: Create GitHub issue
- email_send: Send email
- kanban: Manage Kanban boards
- chatbooks: Manage chatbooks
- character_chat: Character chat

Adapters in this module are registered via the legacy bridge during migration.
"""

# Adapters are registered via _legacy_bridge.py
