-- Prompt Studio optimization iterations table
-- Version: 003

CREATE TABLE IF NOT EXISTS prompt_studio_optimization_iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL DEFAULT (lower(hex(randomblob(16)))),
    optimization_id INTEGER NOT NULL REFERENCES prompt_studio_optimizations(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    prompt_variant JSON,
    metrics JSON,
    tokens_used INTEGER,
    cost REAL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ps_opt_iter_opt ON prompt_studio_optimization_iterations(optimization_id);
CREATE INDEX IF NOT EXISTS idx_ps_opt_iter_num ON prompt_studio_optimization_iterations(optimization_id, iteration_number);
