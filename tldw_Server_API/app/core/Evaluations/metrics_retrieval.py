from __future__ import annotations

from typing import List
import math


def hit_at_k(ranked_ids: List[str], gt_ids: List[str], k: int) -> float:
    if not ranked_ids or not gt_ids:
        return 0.0
    topk = set(ranked_ids[:k])
    return 1.0 if any(str(x) in topk for x in gt_ids) else 0.0


def recall_at_k(ranked_ids: List[str], gt_ids: List[str], k: int) -> float:
    if not gt_ids:
        return 0.0
    topk = set(ranked_ids[:k])
    hits = sum(1 for x in gt_ids if str(x) in topk)
    return float(hits) / float(len(gt_ids))


def mrr(ranked_ids: List[str], gt_ids: List[str], k: int) -> float:
    if not ranked_ids or not gt_ids:
        return 0.0
    gt = set(str(x) for x in gt_ids)
    for idx, rid in enumerate(ranked_ids[:k]):
        if rid in gt:
            return 1.0 / float(idx + 1)
    return 0.0


def ndcg(ranked_ids: List[str], gt_ids: List[str], k: int) -> float:
    if not ranked_ids or not gt_ids:
        return 0.0
    gt = set(str(x) for x in gt_ids)
    dcg = 0.0
    for i, rid in enumerate(ranked_ids[:k]):
        rel = 1.0 if rid in gt else 0.0
        if rel > 0:
            dcg += (2.0**rel - 1.0) / math.log2(i + 2.0)
    # Ideal DCG
    ideal_hits = min(len(gt_ids), k)
    idcg = 0.0
    for i in range(ideal_hits):
        idcg += (2.0**1.0 - 1.0) / math.log2(i + 2.0)
    return (dcg / idcg) if idcg > 0 else 0.0
