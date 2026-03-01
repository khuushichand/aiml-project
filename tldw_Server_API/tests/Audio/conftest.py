"""Local pytest configuration for Audio tests."""

import os

# Audio test modules assert against /api/v1/audio REST and WS routes.
# Keep global MINIMAL_TEST_APP behavior, but opt this suite into mounting audio routers.
os.environ.setdefault("MINIMAL_TEST_INCLUDE_AUDIO", "1")
