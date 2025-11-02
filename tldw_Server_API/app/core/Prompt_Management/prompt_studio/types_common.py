"""
types_common.py

Shared type definitions for Prompt Studio to avoid circular imports.
"""

from enum import Enum


class MetricType(str, Enum):
    """Types of metrics for evaluation in Prompt Studio."""
    ACCURACY = "accuracy"
    F1_SCORE = "f1_score"
    PRECISION = "precision"
    RECALL = "recall"
    EXACT_MATCH = "exact_match"
    SIMILARITY = "similarity"
