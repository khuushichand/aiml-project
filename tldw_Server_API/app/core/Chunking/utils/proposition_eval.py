"""
Proposition extraction evaluation utilities.

Provides simple precision/recall/F1 metrics against a reference set and
diagnostics such as density and average length. Designed to be dependency-light
but can use scikit-learn TF-IDF for semantic matching when available.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from loguru import logger

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
    _SKLEARN_AVAILABLE = True
except Exception:
    _SKLEARN_AVAILABLE = False


@dataclass
class PropositionEvalResult:
    precision: float
    recall: float
    f1: float
    matched: int
    total_extracted: int
    total_reference: int
    claim_density_per_100_tokens: float
    avg_prop_len_tokens: float
    dedup_rate: float
    details: Dict[str, float]


def simple_tokenize(s: str) -> List[str]:
    return [t for t in s.strip().split() if t]


def _greedy_match_semantic(extracted: List[str], reference: List[str], threshold: float = 0.7) -> Tuple[int, List[int]]:
    """Greedy matching by cosine similarity over TF-IDF vectors.
    Returns number of matches and matched indices of reference.
    """
    if not _SKLEARN_AVAILABLE:
        logger.warning("scikit-learn not available; semantic matching disabled")
        return 0, []
    if not extracted or not reference:
        return 0, []
    vect = TfidfVectorizer()
    corpus = reference + extracted
    X = vect.fit_transform(corpus)
    ref_X = X[: len(reference)]
    ext_X = X[len(reference) :]
    sim = cosine_similarity(ext_X, ref_X)  # shape (E, R)
    matched_ref = set()
    matches = 0
    for i in range(sim.shape[0]):
        j = int(sim[i].argmax())
        if sim[i, j] >= threshold and j not in matched_ref:
            matched_ref.add(j)
            matches += 1
    return matches, sorted(list(matched_ref))


def _greedy_match_jaccard(extracted: List[str], reference: List[str], threshold: float = 0.6) -> Tuple[int, List[int]]:
    def jaccard(a: str, b: str) -> float:
        A = set(simple_tokenize(a.lower()))
        B = set(simple_tokenize(b.lower()))
        if not A or not B:
            return 0.0
        return len(A & B) / len(A | B)

    matched_ref = set()
    matches = 0
    for e in extracted:
        scores = [jaccard(e, r) for r in reference]
        if not scores:
            continue
        j = int(max(range(len(scores)), key=lambda k: scores[k]))
        if scores[j] >= threshold and j not in matched_ref:
            matched_ref.add(j)
            matches += 1
    return matches, sorted(list(matched_ref))


def evaluate_propositions(
    extracted: List[str],
    reference: List[str],
    method: str = "semantic",
    threshold: float = 0.7,
) -> PropositionEvalResult:
    """Compute precision/recall/F1 for extracted propositions vs reference.

    method: 'semantic' (TF-IDF cosine) or 'jaccard' (token Jaccard)
    """
    ex = [e.strip() for e in extracted if e and e.strip()]
    ref = [r.strip() for r in reference if r and r.strip()]
    total_ex = len(ex)
    total_ref = len(ref)
    if total_ex == 0 and total_ref == 0:
        return PropositionEvalResult(1.0, 1.0, 1.0, 0, 0, 0, 0.0, 0.0, 0.0, {})
    if total_ex == 0 or total_ref == 0:
        return PropositionEvalResult(0.0, 0.0, 0.0, 0, total_ex, total_ref, 0.0, 0.0, 0.0, {})

    if method == "semantic" and _SKLEARN_AVAILABLE:
        matched, matched_indices = _greedy_match_semantic(ex, ref, threshold)
    elif method == "semantic" and not _SKLEARN_AVAILABLE:
        matched, matched_indices = _greedy_match_jaccard(ex, ref, 0.6)
    else:
        matched, matched_indices = _greedy_match_jaccard(ex, ref, threshold)

    precision = matched / total_ex if total_ex else 0.0
    recall = matched / total_ref if total_ref else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    # Density per 100 tokens in the extracted set
    token_count = sum(len(simple_tokenize(e)) for e in ex)
    density = (len(ex) / token_count * 100) if token_count else 0.0

    # Average proposition length (tokens)
    avg_len = (token_count / len(ex)) if ex else 0.0

    # Dedup rate (exact string duplicates)
    dedup_rate = 1 - (len(set([e.lower() for e in ex])) / len(ex)) if ex else 0.0

    details = {
        "matched_reference_indices": len(matched_indices),
        "threshold": threshold,
        "method": 1.0 if method == "semantic" else 0.0,
    }

    return PropositionEvalResult(
        precision=precision,
        recall=recall,
        f1=f1,
        matched=matched,
        total_extracted=total_ex,
        total_reference=total_ref,
        claim_density_per_100_tokens=density,
        avg_prop_len_tokens=avg_len,
        dedup_rate=dedup_rate,
        details=details,
    )
