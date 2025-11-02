"""
Deprecated: This module targeted the old functional pipeline. All tests here
are skipped to remove usage of deprecated code; coverage is provided by
unified pipeline tests under RAG_NEW.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Functional pipeline is deprecated; tests removed in favor of unified pipeline.")
