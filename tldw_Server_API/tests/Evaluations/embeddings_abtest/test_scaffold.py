import pytest

pytestmark = pytest.mark.embeddings_abtest


@pytest.fixture(scope="session")
def embeddings_abtest_scaffold():
    pytest.skip("Embeddings A/B test scaffolding only; enable once implementation milestones land.")


def test_embeddings_abtest_placeholder(embeddings_abtest_scaffold):
    """Placeholder to keep pytest discovery wired up."""
    pass
