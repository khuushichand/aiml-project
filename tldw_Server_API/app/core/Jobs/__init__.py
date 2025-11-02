"""
Core Jobs module package placeholder.

Currently provides migrations to initialize a generic `jobs` table for the
future core JobManager. Domain adopters (e.g., Chatbooks) may call the
`ensure_jobs_tables` helper during startup when `CHATBOOKS_JOBS_BACKEND=core`.
"""
