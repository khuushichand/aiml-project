-- Example RLS policies for per-tenant isolation using current_setting('app.current_user_id')
-- Note: The server sets both GUCs for compatibility:
--   app.current_user_id (preferred)
--   app.user_id         (legacy, still set)
-- Enable per-table RLS and attach policies that match the session tenant.

-- Notes/Characters (ChaChaNotes)
ALTER TABLE IF EXISTS notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS notes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notes_tenant_isolation ON notes;
CREATE POLICY notes_tenant_isolation ON notes
  USING (client_id = current_setting('app.current_user_id', true));

ALTER TABLE IF EXISTS character_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS character_cards FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS chars_tenant_isolation ON character_cards;
CREATE POLICY chars_tenant_isolation ON character_cards
  USING (client_id = current_setting('app.current_user_id', true));

-- Prompt Studio tables (example: projects stored with user_id)
ALTER TABLE IF EXISTS prompt_studio_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_projects FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_projects_tenant_isolation ON prompt_studio_projects;
CREATE POLICY ps_projects_tenant_isolation ON prompt_studio_projects
  USING (user_id = current_setting('app.current_user_id', true));

-- Prompts (scope via owning project)
ALTER TABLE IF EXISTS prompt_studio_prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_prompts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_prompts_tenant_isolation ON prompt_studio_prompts;
CREATE POLICY ps_prompts_tenant_isolation ON prompt_studio_prompts
  USING (
    EXISTS (
      SELECT 1 FROM prompt_studio_projects p
      WHERE p.id = prompt_studio_prompts.project_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Signatures (scope via owning project)
ALTER TABLE IF EXISTS prompt_studio_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_signatures FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_signatures_tenant_isolation ON prompt_studio_signatures;
CREATE POLICY ps_signatures_tenant_isolation ON prompt_studio_signatures
  USING (
    EXISTS (
      SELECT 1 FROM prompt_studio_projects p
      WHERE p.id = prompt_studio_signatures.project_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Test cases (scope via owning project)
ALTER TABLE IF EXISTS prompt_studio_test_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_test_cases FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_test_cases_tenant_isolation ON prompt_studio_test_cases;
CREATE POLICY ps_test_cases_tenant_isolation ON prompt_studio_test_cases
  USING (
    EXISTS (
      SELECT 1 FROM prompt_studio_projects p
      WHERE p.id = prompt_studio_test_cases.project_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Test runs (scope via owning project)
ALTER TABLE IF EXISTS prompt_studio_test_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_test_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_test_runs_tenant_isolation ON prompt_studio_test_runs;
CREATE POLICY ps_test_runs_tenant_isolation ON prompt_studio_test_runs
  USING (
    EXISTS (
      SELECT 1 FROM prompt_studio_projects p
      WHERE p.id = prompt_studio_test_runs.project_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Evaluations (scope via owning project)
ALTER TABLE IF EXISTS prompt_studio_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_evaluations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_evals_tenant_isolation ON prompt_studio_evaluations;
CREATE POLICY ps_evals_tenant_isolation ON prompt_studio_evaluations
  USING (
    EXISTS (
      SELECT 1 FROM prompt_studio_projects p
      WHERE p.id = prompt_studio_evaluations.project_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Optimizations (scope via owning project)
ALTER TABLE IF EXISTS prompt_studio_optimizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_optimizations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_opts_tenant_isolation ON prompt_studio_optimizations;
CREATE POLICY ps_opts_tenant_isolation ON prompt_studio_optimizations
  USING (
    EXISTS (
      SELECT 1 FROM prompt_studio_projects p
      WHERE p.id = prompt_studio_optimizations.project_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Optimization iterations (scope via optimization -> project)
ALTER TABLE IF EXISTS prompt_studio_optimization_iterations ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_optimization_iterations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_iter_tenant_isolation ON prompt_studio_optimization_iterations;
CREATE POLICY ps_iter_tenant_isolation ON prompt_studio_optimization_iterations
  USING (
    EXISTS (
      SELECT 1
      FROM prompt_studio_optimizations o
      JOIN prompt_studio_projects p ON p.id = o.project_id
      WHERE o.id = prompt_studio_optimization_iterations.optimization_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Job queue (scope via project or client_id)
ALTER TABLE IF EXISTS prompt_studio_job_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_job_queue FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_jobq_tenant_isolation ON prompt_studio_job_queue;
CREATE POLICY ps_jobq_tenant_isolation ON prompt_studio_job_queue
  USING (
    (client_id = current_setting('app.current_user_id', true))
    OR EXISTS (
      SELECT 1 FROM prompt_studio_projects p
      WHERE p.id = prompt_studio_job_queue.project_id
        AND p.user_id = current_setting('app.current_user_id', true)
    )
  );

-- Idempotency (allow own entries and NULL-scope)
ALTER TABLE IF EXISTS prompt_studio_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS prompt_studio_idempotency FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ps_idem_tenant_isolation ON prompt_studio_idempotency;
CREATE POLICY ps_idem_tenant_isolation ON prompt_studio_idempotency
  USING (
    user_id = current_setting('app.current_user_id', true)
    OR user_id IS NULL
  );

-- Optional: Prevent BYPASSRLS
-- ALTER TABLE notes FORCE ROW LEVEL SECURITY;
-- ALTER TABLE character_cards FORCE ROW LEVEL SECURITY;
-- ALTER TABLE prompt_studio_projects FORCE ROW LEVEL SECURITY;

-- Usage: set the session variable at connection time:
--   SET SESSION app.current_user_id = '<tenant-id>';
-- The server DB adapters set this automatically using the request/client context.
