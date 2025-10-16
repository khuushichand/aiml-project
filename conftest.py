"""Top-level test configuration.

Defines pytest plugins needed across nested suites to avoid the
non-top-level pytest_plugins deprecation.
"""

pytest_plugins = [
    "tldw_Server_API.tests.helpers.pg",
    "tldw_Server_API.tests.helpers.pgvector",
]
