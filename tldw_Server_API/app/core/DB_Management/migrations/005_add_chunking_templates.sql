-- Migration 005: Add ChunkingTemplates table
-- This migration adds the ChunkingTemplates table which was missing from some v4 databases

-- Create ChunkingTemplates table if it doesn't exist
CREATE TABLE IF NOT EXISTS ChunkingTemplates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    template_json TEXT NOT NULL,
    is_builtin BOOLEAN DEFAULT 0 NOT NULL,
    tags TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    client_id TEXT NOT NULL,
    user_id TEXT,
    deleted BOOLEAN NOT NULL DEFAULT 0,
    prev_version INTEGER,
    merge_parent_uuid TEXT
);

-- Create indices for ChunkingTemplates
CREATE UNIQUE INDEX IF NOT EXISTS idx_template_name_not_deleted
    ON ChunkingTemplates(name) WHERE deleted = 0;
CREATE INDEX IF NOT EXISTS idx_template_is_builtin ON ChunkingTemplates(is_builtin);
CREATE INDEX IF NOT EXISTS idx_template_deleted ON ChunkingTemplates(deleted);

-- Add trigger for updated_at
CREATE TRIGGER IF NOT EXISTS update_chunking_templates_updated_at
AFTER UPDATE ON ChunkingTemplates
FOR EACH ROW
BEGIN
    UPDATE ChunkingTemplates SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
