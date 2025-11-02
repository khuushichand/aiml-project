-- Tool Catalogs (MCP) - PostgreSQL DDL (additive)
-- This file can be applied after the core AuthNZ schema to add tool catalog tables.

-- tool_catalogs: scoped by (org_id, team_id) with name unique per scope
CREATE TABLE IF NOT EXISTS tool_catalogs (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NULL,
    org_id INTEGER NULL REFERENCES organizations(id) ON DELETE SET NULL,
    team_id INTEGER NULL REFERENCES teams(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tool_catalogs_scope UNIQUE (name, org_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_tool_catalogs_org_team ON tool_catalogs(org_id, team_id);
CREATE INDEX IF NOT EXISTS idx_tool_catalogs_name ON tool_catalogs(name);

-- tool_catalog_entries
CREATE TABLE IF NOT EXISTS tool_catalog_entries (
    id SERIAL PRIMARY KEY,
    catalog_id INTEGER NOT NULL REFERENCES tool_catalogs(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    module_id TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tool_catalog_entries UNIQUE (catalog_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_tool_catalog_entries_catalog ON tool_catalog_entries(catalog_id);
CREATE INDEX IF NOT EXISTS idx_tool_catalog_entries_tool ON tool_catalog_entries(tool_name);
