-- Migration 006: Add structured prompt fields to Prompt Studio prompts
-- This migration is additive and stores structured prompt metadata alongside
-- the existing legacy compatibility fields.

ALTER TABLE prompt_studio_prompts
    ADD COLUMN prompt_format TEXT NOT NULL DEFAULT 'legacy';

ALTER TABLE prompt_studio_prompts
    ADD COLUMN prompt_schema_version INTEGER;

ALTER TABLE prompt_studio_prompts
    ADD COLUMN prompt_definition JSON;
