"""Unit tests for retrieval_metrics module.

Tests cover all pure metric functions (precision@k, recall@k, MRR, NDCG@k, F1@k),
the evaluate_retrieval aggregator, the evaluate_retrieval_batch batch helper,
and the RetrievalMetrics frozen dataclass.
"""

from __future__ import annotations

import math

import pytest

from tldw_Server_API.app.core.RAG.rag_service.retrieval_metrics import (
    RetrievalMetrics,
    evaluate_retrieval,
    evaluate_retrieval_batch,
    f1_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def perfect_retrieval():
    """Retrieved and relevant sets are identical."""
    ids = ["a", "b", "c", "d", "e"]
    return ids[:], ids[:]


@pytest.fixture()
def partial_retrieval():
    """Some overlap between retrieved and relevant sets."""
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = ["b", "d", "f"]
    return retrieved, relevant


@pytest.fixture()
def no_overlap_retrieval():
    """Zero overlap between retrieved and relevant."""
    retrieved = ["a", "b", "c"]
    relevant = ["x", "y", "z"]
    return retrieved, relevant


# ===================================================================
# precision_at_k
# ===================================================================

class TestPrecisionAtK:

    @pytest.mark.unit
    def test_perfect_precision(self, perfect_retrieval):
        retrieved, relevant = perfect_retrieval
        assert precision_at_k(retrieved, relevant, 5) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_partial_precision(self, partial_retrieval):
        retrieved, relevant = partial_retrieval
        # top-5: a,b,c,d,e -> relevant: b,d => 2/5
        assert precision_at_k(retrieved, relevant, 5) == pytest.approx(0.4)

    @pytest.mark.unit
    def test_no_overlap(self, no_overlap_retrieval):
        retrieved, relevant = no_overlap_retrieval
        assert precision_at_k(retrieved, relevant, 3) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_less_than_retrieved(self):
        retrieved = ["a", "b", "c", "d"]
        relevant = ["a", "b"]
        # top-2: a,b -> both relevant => 2/2
        assert precision_at_k(retrieved, relevant, 2) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_k_greater_than_retrieved(self):
        retrieved = ["a", "b"]
        relevant = ["a"]
        # k=10, but only 2 retrieved => 1/2
        assert precision_at_k(retrieved, relevant, 10) == pytest.approx(0.5)

    @pytest.mark.unit
    def test_k_zero(self):
        assert precision_at_k(["a", "b"], ["a"], 0) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_negative(self):
        assert precision_at_k(["a"], ["a"], -1) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_retrieved(self):
        assert precision_at_k([], ["a", "b"], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_relevant(self):
        assert precision_at_k(["a", "b"], [], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_both_empty(self):
        assert precision_at_k([], [], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_equals_one_relevant_first(self):
        assert precision_at_k(["a", "b", "c"], ["a"], 1) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_k_equals_one_irrelevant_first(self):
        assert precision_at_k(["b", "a", "c"], ["a"], 1) == pytest.approx(0.0)


# ===================================================================
# recall_at_k
# ===================================================================

class TestRecallAtK:

    @pytest.mark.unit
    def test_perfect_recall(self, perfect_retrieval):
        retrieved, relevant = perfect_retrieval
        assert recall_at_k(retrieved, relevant, 5) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_partial_recall(self, partial_retrieval):
        retrieved, relevant = partial_retrieval
        # top-5 retrieves b,d out of b,d,f => 2/3
        assert recall_at_k(retrieved, relevant, 5) == pytest.approx(2.0 / 3.0)

    @pytest.mark.unit
    def test_no_overlap(self, no_overlap_retrieval):
        retrieved, relevant = no_overlap_retrieval
        assert recall_at_k(retrieved, relevant, 3) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_greater_than_retrieved(self):
        retrieved = ["a"]
        relevant = ["a", "b"]
        # top-10 but only 1 retrieved: a is relevant => 1/2
        assert recall_at_k(retrieved, relevant, 10) == pytest.approx(0.5)

    @pytest.mark.unit
    def test_k_zero(self):
        assert recall_at_k(["a"], ["a"], 0) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_negative(self):
        assert recall_at_k(["a"], ["a"], -1) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_retrieved(self):
        assert recall_at_k([], ["a"], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_relevant(self):
        # No relevant docs => 0.0 by definition
        assert recall_at_k(["a", "b"], [], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_both_empty(self):
        assert recall_at_k([], [], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_small_k_partial_recall(self):
        retrieved = ["a", "b", "c"]
        relevant = ["a", "c"]
        # top-1: a -> 1/2
        assert recall_at_k(retrieved, relevant, 1) == pytest.approx(0.5)


# ===================================================================
# mrr
# ===================================================================

class TestMRR:

    @pytest.mark.unit
    def test_first_result_relevant(self):
        assert mrr(["a", "b", "c"], ["a"]) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_second_result_relevant(self):
        assert mrr(["x", "a", "b"], ["a", "b"]) == pytest.approx(0.5)

    @pytest.mark.unit
    def test_third_result_relevant(self):
        assert mrr(["x", "y", "a"], ["a"]) == pytest.approx(1.0 / 3.0)

    @pytest.mark.unit
    def test_no_relevant_found(self, no_overlap_retrieval):
        retrieved, relevant = no_overlap_retrieval
        assert mrr(retrieved, relevant) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_retrieved(self):
        assert mrr([], ["a"]) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_relevant(self):
        assert mrr(["a", "b"], []) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_both_empty(self):
        assert mrr([], []) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_perfect_retrieval(self, perfect_retrieval):
        retrieved, relevant = perfect_retrieval
        # First doc is relevant, so MRR = 1.0
        assert mrr(retrieved, relevant) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_only_last_relevant(self):
        retrieved = ["x", "y", "z", "w", "a"]
        relevant = ["a"]
        assert mrr(retrieved, relevant) == pytest.approx(1.0 / 5.0)


# ===================================================================
# ndcg_at_k
# ===================================================================

class TestNDCGAtK:

    @pytest.mark.unit
    def test_perfect_ranking(self):
        # All relevant docs at top positions
        retrieved = ["a", "b", "c"]
        relevant = ["a", "b", "c"]
        assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_reversed_ranking(self):
        # Relevant docs at the bottom
        retrieved = ["x", "y", "a"]
        relevant = ["a"]
        # DCG = 1/log2(3+1) = 1/2 = 0.5
        # IDCG = 1/log2(1+1) = 1/1 = 1.0
        expected = (1.0 / math.log2(4)) / (1.0 / math.log2(2))
        assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(expected)

    @pytest.mark.unit
    def test_no_overlap(self, no_overlap_retrieval):
        retrieved, relevant = no_overlap_retrieval
        assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_zero(self):
        assert ndcg_at_k(["a"], ["a"], 0) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_negative(self):
        assert ndcg_at_k(["a"], ["a"], -1) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_relevant(self):
        assert ndcg_at_k(["a", "b"], [], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_retrieved(self):
        assert ndcg_at_k([], ["a", "b"], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_both_empty(self):
        assert ndcg_at_k([], [], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_greater_than_retrieved(self):
        retrieved = ["a"]
        relevant = ["a", "b"]
        # DCG = 1/log2(2) = 1.0
        # IDCG with k=10 but only 2 relevant => 1/log2(2) + 1/log2(3)
        # But only 1 retrieved, so DCG = 1/log2(2) = 1.0
        # IDCG = 1/log2(2) + 1/log2(3) (min(2, 10) = 2)
        idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)
        expected = 1.0 / idcg
        assert ndcg_at_k(retrieved, relevant, 10) == pytest.approx(expected)

    @pytest.mark.unit
    def test_partial_ranking_two_of_three(self):
        retrieved = ["a", "x", "b", "y"]
        relevant = ["a", "b", "c"]
        k = 4
        # DCG: pos1 a=relevant -> 1/log2(2), pos2 x=no, pos3 b=relevant -> 1/log2(4), pos4 y=no
        dcg = 1.0 / math.log2(2) + 1.0 / math.log2(4)
        # IDCG: min(3, 4)=3 relevant -> 1/log2(2) + 1/log2(3) + 1/log2(4)
        idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3) + 1.0 / math.log2(4)
        assert ndcg_at_k(retrieved, relevant, k) == pytest.approx(dcg / idcg)


# ===================================================================
# f1_at_k
# ===================================================================

class TestF1AtK:

    @pytest.mark.unit
    def test_perfect_f1(self, perfect_retrieval):
        retrieved, relevant = perfect_retrieval
        assert f1_at_k(retrieved, relevant, 5) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_no_overlap_f1(self, no_overlap_retrieval):
        retrieved, relevant = no_overlap_retrieval
        assert f1_at_k(retrieved, relevant, 3) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_partial_f1(self, partial_retrieval):
        retrieved, relevant = partial_retrieval
        # precision@5 = 2/5 = 0.4, recall@5 = 2/3
        p = 0.4
        r = 2.0 / 3.0
        expected = 2 * p * r / (p + r)
        assert f1_at_k(retrieved, relevant, 5) == pytest.approx(expected)

    @pytest.mark.unit
    def test_k_zero(self):
        # precision=0, recall=0 => f1=0
        assert f1_at_k(["a"], ["a"], 0) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_both(self):
        assert f1_at_k([], [], 5) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_high_precision_low_recall(self):
        retrieved = ["a"]
        relevant = ["a", "b", "c", "d"]
        # precision@1 = 1.0, recall@1 = 0.25
        p = 1.0
        r = 0.25
        expected = 2 * p * r / (p + r)
        assert f1_at_k(retrieved, relevant, 1) == pytest.approx(expected)

    @pytest.mark.unit
    def test_low_precision_high_recall(self):
        retrieved = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        relevant = ["a"]
        # precision@10 = 1/10 = 0.1, recall@10 = 1.0
        p = 0.1
        r = 1.0
        expected = 2 * p * r / (p + r)
        assert f1_at_k(retrieved, relevant, 10) == pytest.approx(expected)


# ===================================================================
# RetrievalMetrics dataclass
# ===================================================================

class TestRetrievalMetrics:

    @pytest.mark.unit
    def test_frozen(self):
        m = RetrievalMetrics(
            precision=0.5, recall=0.6, mrr=0.8, ndcg=0.7, f1=0.55, k=10
        )
        with pytest.raises(AttributeError):
            m.precision = 0.9  # type: ignore[misc]

    @pytest.mark.unit
    def test_to_dict_keys(self):
        m = RetrievalMetrics(
            precision=0.5, recall=0.6, mrr=0.8, ndcg=0.7, f1=0.55, k=10
        )
        d = m.to_dict()
        expected_keys = {"precision_at_k", "recall_at_k", "mrr", "ndcg_at_k", "f1_at_k", "k"}
        assert set(d.keys()) == expected_keys

    @pytest.mark.unit
    def test_to_dict_values(self):
        m = RetrievalMetrics(
            precision=0.5, recall=0.6, mrr=0.8, ndcg=0.7, f1=0.55, k=10
        )
        d = m.to_dict()
        assert d["precision_at_k"] == pytest.approx(0.5)
        assert d["recall_at_k"] == pytest.approx(0.6)
        assert d["mrr"] == pytest.approx(0.8)
        assert d["ndcg_at_k"] == pytest.approx(0.7)
        assert d["f1_at_k"] == pytest.approx(0.55)
        assert d["k"] == 10


# ===================================================================
# evaluate_retrieval
# ===================================================================

class TestEvaluateRetrieval:

    @pytest.mark.unit
    def test_standard_evaluation(self):
        retrieved = ["a", "b", "c", "d", "e"]
        relevant = ["a", "c", "e"]
        result = evaluate_retrieval(retrieved, relevant, k=5)

        assert isinstance(result, RetrievalMetrics)
        assert result.k == 5
        # precision@5 = 3/5
        assert result.precision == pytest.approx(0.6)
        # recall@5 = 3/3
        assert result.recall == pytest.approx(1.0)
        # mrr: first relevant at rank 1
        assert result.mrr == pytest.approx(1.0)
        # f1 = 2 * 0.6 * 1.0 / (0.6 + 1.0)
        assert result.f1 == pytest.approx(2 * 0.6 * 1.0 / 1.6)

    @pytest.mark.unit
    def test_default_k(self):
        retrieved = ["a", "b"]
        relevant = ["a"]
        result = evaluate_retrieval(retrieved, relevant)
        assert result.k == 10

    @pytest.mark.unit
    def test_k_less_than_one_raises(self):
        with pytest.raises(ValueError, match="k must be at least 1"):
            evaluate_retrieval(["a"], ["a"], k=0)

    @pytest.mark.unit
    def test_k_negative_raises(self):
        with pytest.raises(ValueError, match="k must be at least 1"):
            evaluate_retrieval(["a"], ["a"], k=-5)

    @pytest.mark.unit
    def test_empty_retrieved(self):
        result = evaluate_retrieval([], ["a", "b"], k=5)
        assert result.precision == pytest.approx(0.0)
        assert result.recall == pytest.approx(0.0)
        assert result.mrr == pytest.approx(0.0)
        assert result.ndcg == pytest.approx(0.0)
        assert result.f1 == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_relevant(self):
        result = evaluate_retrieval(["a", "b"], [], k=5)
        assert result.precision == pytest.approx(0.0)
        assert result.recall == pytest.approx(0.0)
        assert result.mrr == pytest.approx(0.0)
        assert result.ndcg == pytest.approx(0.0)
        assert result.f1 == pytest.approx(0.0)

    @pytest.mark.unit
    def test_complete_overlap(self, perfect_retrieval):
        retrieved, relevant = perfect_retrieval
        result = evaluate_retrieval(retrieved, relevant, k=5)
        assert result.precision == pytest.approx(1.0)
        assert result.recall == pytest.approx(1.0)
        assert result.mrr == pytest.approx(1.0)
        assert result.ndcg == pytest.approx(1.0)
        assert result.f1 == pytest.approx(1.0)

    @pytest.mark.unit
    def test_no_overlap(self, no_overlap_retrieval):
        retrieved, relevant = no_overlap_retrieval
        result = evaluate_retrieval(retrieved, relevant, k=3)
        assert result.precision == pytest.approx(0.0)
        assert result.recall == pytest.approx(0.0)
        assert result.mrr == pytest.approx(0.0)
        assert result.ndcg == pytest.approx(0.0)
        assert result.f1 == pytest.approx(0.0)

    @pytest.mark.unit
    def test_k_larger_than_retrieved_list(self):
        retrieved = ["a", "b"]
        relevant = ["a", "b", "c"]
        result = evaluate_retrieval(retrieved, relevant, k=100)
        assert result.k == 100
        # precision = 2/2 = 1.0 (only 2 retrieved items)
        assert result.precision == pytest.approx(1.0)
        # recall = 2/3
        assert result.recall == pytest.approx(2.0 / 3.0)

    @pytest.mark.unit
    def test_result_is_frozen(self):
        result = evaluate_retrieval(["a"], ["a"], k=1)
        with pytest.raises(AttributeError):
            result.precision = 0.0  # type: ignore[misc]


# ===================================================================
# evaluate_retrieval_batch
# ===================================================================

class TestEvaluateRetrievalBatch:

    @pytest.mark.unit
    def test_empty_results(self):
        result = evaluate_retrieval_batch([], k=5)
        assert result["num_queries"] == 0
        assert result["k"] == 5
        assert result["avg_precision_at_k"] == pytest.approx(0.0)
        assert result["avg_recall_at_k"] == pytest.approx(0.0)
        assert result["avg_mrr"] == pytest.approx(0.0)
        assert result["avg_ndcg_at_k"] == pytest.approx(0.0)
        assert result["avg_f1_at_k"] == pytest.approx(0.0)

    @pytest.mark.unit
    def test_single_query(self):
        results = [(["a", "b", "c"], ["a", "c"])]
        batch = evaluate_retrieval_batch(results, k=3)
        single = evaluate_retrieval(["a", "b", "c"], ["a", "c"], k=3)

        assert batch["num_queries"] == 1
        assert batch["k"] == 3
        assert batch["avg_precision_at_k"] == pytest.approx(single.precision)
        assert batch["avg_recall_at_k"] == pytest.approx(single.recall)
        assert batch["avg_mrr"] == pytest.approx(single.mrr)
        assert batch["avg_ndcg_at_k"] == pytest.approx(single.ndcg)
        assert batch["avg_f1_at_k"] == pytest.approx(single.f1)

    @pytest.mark.unit
    def test_multiple_queries_averaging(self):
        # Query 1: perfect retrieval
        q1_ret = ["a", "b"]
        q1_rel = ["a", "b"]
        # Query 2: no overlap
        q2_ret = ["x", "y"]
        q2_rel = ["a", "b"]

        results = [(q1_ret, q1_rel), (q2_ret, q2_rel)]
        batch = evaluate_retrieval_batch(results, k=2)

        m1 = evaluate_retrieval(q1_ret, q1_rel, k=2)
        m2 = evaluate_retrieval(q2_ret, q2_rel, k=2)

        assert batch["num_queries"] == 2
        assert batch["avg_precision_at_k"] == pytest.approx(
            (m1.precision + m2.precision) / 2.0
        )
        assert batch["avg_recall_at_k"] == pytest.approx(
            (m1.recall + m2.recall) / 2.0
        )
        assert batch["avg_mrr"] == pytest.approx(
            (m1.mrr + m2.mrr) / 2.0
        )
        assert batch["avg_ndcg_at_k"] == pytest.approx(
            (m1.ndcg + m2.ndcg) / 2.0
        )
        assert batch["avg_f1_at_k"] == pytest.approx(
            (m1.f1 + m2.f1) / 2.0
        )

    @pytest.mark.unit
    def test_batch_expected_keys(self):
        results = [(["a"], ["a"])]
        batch = evaluate_retrieval_batch(results, k=5)
        expected_keys = {
            "avg_precision_at_k",
            "avg_recall_at_k",
            "avg_mrr",
            "avg_ndcg_at_k",
            "avg_f1_at_k",
            "num_queries",
            "k",
        }
        assert set(batch.keys()) == expected_keys

    @pytest.mark.unit
    def test_default_k(self):
        results = [(["a"], ["a"])]
        batch = evaluate_retrieval_batch(results)
        assert batch["k"] == 10

    @pytest.mark.unit
    def test_three_queries_mixed(self):
        # Query 1: perfect
        q1 = (["a", "b", "c"], ["a", "b", "c"])
        # Query 2: half overlap
        q2 = (["a", "x", "b", "y"], ["a", "b"])
        # Query 3: no overlap
        q3 = (["x", "y", "z"], ["a", "b", "c"])

        results = [q1, q2, q3]
        batch = evaluate_retrieval_batch(results, k=4)

        metrics = [evaluate_retrieval(r, rel, k=4) for r, rel in results]
        n = 3

        assert batch["num_queries"] == 3
        assert batch["avg_precision_at_k"] == pytest.approx(
            sum(m.precision for m in metrics) / n
        )
        assert batch["avg_recall_at_k"] == pytest.approx(
            sum(m.recall for m in metrics) / n
        )
        assert batch["avg_mrr"] == pytest.approx(
            sum(m.mrr for m in metrics) / n
        )
        assert batch["avg_ndcg_at_k"] == pytest.approx(
            sum(m.ndcg for m in metrics) / n
        )
        assert batch["avg_f1_at_k"] == pytest.approx(
            sum(m.f1 for m in metrics) / n
        )


# ===================================================================
# Cross-metric consistency checks
# ===================================================================

class TestCrossMetricConsistency:

    @pytest.mark.unit
    def test_f1_is_harmonic_mean_of_precision_and_recall(self):
        """Verify f1_at_k equals 2*P*R/(P+R) for non-zero P and R."""
        retrieved = ["a", "b", "c", "d"]
        relevant = ["a", "c", "e"]
        k = 4
        p = precision_at_k(retrieved, relevant, k)
        r = recall_at_k(retrieved, relevant, k)
        expected_f1 = 2 * p * r / (p + r)
        assert f1_at_k(retrieved, relevant, k) == pytest.approx(expected_f1)

    @pytest.mark.unit
    def test_ndcg_perfect_ranking_equals_one(self):
        """NDCG should be 1.0 when all relevant docs are at top positions."""
        relevant = ["a", "b", "c"]
        retrieved = ["a", "b", "c", "x", "y"]
        assert ndcg_at_k(retrieved, relevant, 5) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_precision_recall_bounds(self):
        """Precision and recall should always be between 0 and 1."""
        retrieved = ["a", "b", "c", "d", "e", "f"]
        relevant = ["b", "d", "g", "h"]
        for k in range(1, 8):
            p = precision_at_k(retrieved, relevant, k)
            r = recall_at_k(retrieved, relevant, k)
            assert 0.0 <= p <= 1.0, f"precision out of bounds at k={k}: {p}"
            assert 0.0 <= r <= 1.0, f"recall out of bounds at k={k}: {r}"

    @pytest.mark.unit
    def test_mrr_bounded(self):
        """MRR should always be between 0 and 1."""
        retrieved = ["x", "y", "a", "b"]
        relevant = ["a"]
        score = mrr(retrieved, relevant)
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_ndcg_bounded(self):
        """NDCG should always be between 0 and 1."""
        retrieved = ["x", "a", "y", "b"]
        relevant = ["a", "b", "c"]
        for k in range(1, 6):
            score = ndcg_at_k(retrieved, relevant, k)
            assert 0.0 <= score <= 1.0, f"ndcg out of bounds at k={k}: {score}"

    @pytest.mark.unit
    def test_evaluate_retrieval_matches_individual_functions(self):
        """evaluate_retrieval should aggregate individual metric functions."""
        retrieved = ["a", "x", "b", "y", "c"]
        relevant = ["a", "b", "c"]
        k = 5

        result = evaluate_retrieval(retrieved, relevant, k)

        assert result.precision == pytest.approx(precision_at_k(retrieved, relevant, k))
        assert result.recall == pytest.approx(recall_at_k(retrieved, relevant, k))
        assert result.mrr == pytest.approx(mrr(retrieved, relevant))
        assert result.ndcg == pytest.approx(ndcg_at_k(retrieved, relevant, k))
        assert result.f1 == pytest.approx(f1_at_k(retrieved, relevant, k))
