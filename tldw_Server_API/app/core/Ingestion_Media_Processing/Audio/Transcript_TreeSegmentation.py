"""
Transcript Tree Segmentation (TreeSeg) for diarization-aware editing.

This module implements the tree-segmentation algorithm described in
"TreeSeg: Hierarchical Segmentation of Sequential Data" (arXiv:2407.12028v1)
adapted for transcript utterances. It forms expanded utterance blocks,
embeds them, and recursively splits to produce coherent conversational
segments that can aid diarization and user editing of recorded meetings.

Key ideas:
- Build blocks by concatenating up to W preceding utterances with current.
- Compute embeddings for each block (provider-agnostic via injectable embedder).
- Recursively split sequence to minimize within-segment squared error with
  an optional balance penalty to discourage degenerate splits.

Integration notes:
- Embeddings are pluggable. Pass an async embedder callable or allow the
  built-in integration with AsyncEmbeddingService to be used.
- Input entries are minimally required to contain a "composite" field
  (text for each utterance). Optional metadata (speaker, start/end times)
  is preserved and carried through to segments.

Usage example:
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Transcript_TreeSegmentation import (
        TreeSegmenter,
    )

    entries = [
        {"composite": "Hello everyone", "start": 0.0, "end": 2.5, "speaker": "A"},
        {"composite": "Project update ...", "start": 2.6, "end": 8.0, "speaker": "B"},
        # ...
    ]

    configs = {
        "MIN_SEGMENT_SIZE": 5,
        "LAMBDA_BALANCE": 0.01,
        "UTTERANCE_EXPANSION_WIDTH": 2,
        # Optional embedding settings if using built-in service:
        # "EMBEDDINGS_PROVIDER": "openai",
        # "EMBEDDINGS_MODEL": "text-embedding-3-small",
    }

    segmenter = TreeSegmenter(configs=configs, entries=entries)
    transitions = segmenter.segment_meeting(K=6)
    segments = segmenter.get_segments()

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import asyncio
import heapq
import numpy as np
from loguru import logger

try:
    # Local async embeddings service (preferred for providers/config)
    from tldw_Server_API.app.core.Embeddings.async_embeddings import (
        create_embeddings_batch_async,
    )
    _EMBED_SERVICE_AVAILABLE = True
except Exception:
    _EMBED_SERVICE_AVAILABLE = False


# Types
EmbedderCallable = Callable[[List[str]], Awaitable[List[List[float]]]]


DEFAULT_CONFIGS: Dict[str, Any] = {
    "MIN_SEGMENT_SIZE": 5,
    "LAMBDA_BALANCE": 0.01,
    "UTTERANCE_EXPANSION_WIDTH": 2,
    "EMBEDDING_BATCH_SIZE": 256,
    "MIN_IMPROVEMENT_RATIO": 0.0,  # stop splitting when improvement ratio below this
    # Optional: provider/model used only if built-in embedder is used
    "EMBEDDINGS_PROVIDER": None,  # Use embeddings config defaults
    "EMBEDDINGS_MODEL": None,
}


def _squared_error(X: np.ndarray, mu: np.ndarray) -> float:
    return float(np.sum(np.sum(np.square(X - mu), axis=-1)))


class SegNode:
    """A node in the segmentation tree.

    Each node represents a contiguous sequence of entries, with a mean
    embedding and negative log-likelihood (sum of squared errors + balance).
    It can be split into left/right children by choosing the split that
    minimizes total loss subject to a minimum segment size.
    """

    def __init__(self, identifier: str, entries: List[Dict[str, Any]], configs: Dict[str, Any]):
        self.configs = configs
        self.MIN_SEGMENT_SIZE: int = int(configs["MIN_SEGMENT_SIZE"])
        self.LAMBDA_BALANCE: float = float(configs["LAMBDA_BALANCE"])

        self.entries: List[Dict[str, Any]] = entries
        self.segment: List[int] = [int(entry["index"]) for entry in entries]
        self.embs: np.ndarray = np.array([entry["embedding"] for entry in entries], dtype=float)
        self.mu: np.ndarray = np.mean(self.embs, axis=0)

        self.left: Optional[SegNode] = None
        self.right: Optional[SegNode] = None
        self.identifier: str = identifier
        self.is_leaf: bool = len(entries) < 2 * self.MIN_SEGMENT_SIZE

        if self.is_leaf:
            # No split possible due to min size constraint
            return

        self.compute_likelihood()
        self.optimize_split()

    def compute_likelihood(self) -> None:
        self.mu = np.mean(self.embs, axis=0, keepdims=True)
        self.negative_log_likelihood: float = _squared_error(self.embs, self.mu)
        # Balance penalty encourages more balanced splits
        self.negative_log_likelihood += self.LAMBDA_BALANCE * float(np.square(len(self.entries)))

    def optimize_split(self) -> None:
        N = len(self.entries)
        index = list(np.arange(N))

        min_loss = float("inf")
        S0 = None  # type: Optional[np.ndarray]
        S1 = None  # type: Optional[np.ndarray]

        # Prefix-sum updates for efficient loss computation across split points
        for n in range(self.MIN_SEGMENT_SIZE - 1, N - self.MIN_SEGMENT_SIZE):
            if S0 is None:
                idx0 = index[: n + 1]
                idx1 = index[n + 1 :]

                X0 = self.embs[idx0]
                X1 = self.embs[idx1]

                S0 = np.sum(X0, axis=0)
                SS0 = np.sum(np.square(X0), axis=0)

                S1 = np.sum(X1, axis=0)
                SS1 = np.sum(np.square(X1), axis=0)

                M0 = len(idx0)
                M1 = len(idx1)
            else:
                M0 += 1
                M1 -= 1

                v = self.embs[n]
                S0 += v
                S1 -= v
                SS0 += np.square(v)
                SS1 -= np.square(v)

            assert M0 + M1 == N

            mu0 = S0 / M0
            mu1 = S1 / M1

            # Sum of squared errors within each side (via SS - mu^2 * count)
            loss = float(np.sum(SS0 - np.square(mu0) * M0))
            loss += float(np.sum(SS1 - np.square(mu1) * M1))

            # Balance penalty on segment sizes
            balance_penalty = self.LAMBDA_BALANCE * float(np.square(M0) + np.square(M1))
            loss += balance_penalty

            if loss < min_loss:
                min_loss = loss
                self.split_negative_log_likelihood = loss
                self.split_entries = [self.entries[: n + 1], self.entries[n + 1 :]]

    def split_loss_delta(self) -> float:
        return float(self.split_negative_log_likelihood - self.negative_log_likelihood)

    def split(self) -> Tuple["SegNode", "SegNode"]:
        left_entries, right_entries = self.split_entries
        self.left = SegNode(
            identifier=self.identifier + "L",
            entries=left_entries,
            configs=self.configs,
        )
        self.right = SegNode(
            identifier=self.identifier + "R",
            entries=right_entries,
            configs=self.configs,
        )
        return self.left, self.right


class TreeSegmenter:
    """Provider-agnostic transcript tree segmentation.

    Args:
        configs: Required configuration. See DEFAULT_CONFIGS for keys.
        entries: List of dict entries; each must have a "composite" field (utterance text).
        embedder: Optional async callable that takes a list of strings and returns embeddings.
                  If not provided, built-in AsyncEmbeddingService is used (if available).
    """

    def __init__(
        self,
        configs: Dict[str, Any],
        entries: List[Dict[str, Any]],
        embedder: Optional[EmbedderCallable] = None,
        *,
        auto_embed: bool = True,
    ) -> None:
        self.configs = {**DEFAULT_CONFIGS, **(configs or {})}
        self.entries = list(entries)
        self.embedder = embedder

        self.blocks: List[Dict[str, Any]] = []
        self.leaves: List[SegNode] = []
        self.transitions_hat: List[int] = []

        self.extract_blocks()
        if auto_embed:
            self._embed_blocks_with_retry()

    @classmethod
    async def create_async(
        cls,
        configs: Dict[str, Any],
        entries: List[Dict[str, Any]],
        embedder: Optional[EmbedderCallable] = None,
    ) -> "TreeSegmenter":
        """Async factory: builds blocks and embeds asynchronously (no event loop conflicts)."""
        self = cls(configs=configs, entries=entries, embedder=embedder, auto_embed=False)
        await self.embed_blocks_async()
        return self

    def extract_blocks(self) -> None:
        entries = self.entries
        width = int(self.configs["UTTERANCE_EXPANSION_WIDTH"]) or 0

        blocks: List[Dict[str, Any]] = []
        for i, entry in enumerate(entries):
            convo_parts: List[str] = []
            for idx in range(max(0, i - width), i + 1):
                convo_parts.append(str(entries[idx].get("composite", "")))

            block: Dict[str, Any] = {
                "convo": "\n".join(convo_parts),
                "index": i,
            }
            # include original entry metadata for later segment synthesis
            block.update(entry)
            blocks.append(block)

        # Normalize indices in-case upstream entries had custom index fields
        for i, block in enumerate(blocks):
            block["index"] = i

        self.blocks = blocks

    async def _default_embedder(self, chunks: List[str]) -> List[List[float]]:
        if not _EMBED_SERVICE_AVAILABLE:
            raise RuntimeError(
                "Async embeddings service not available. Provide an embedder callable."
            )

        provider = self.configs.get("EMBEDDINGS_PROVIDER")
        model = self.configs.get("EMBEDDINGS_MODEL")
        embs = await create_embeddings_batch_async(
            chunks, model=model, provider=provider
        )
        return embs

    async def embed_blocks_async(self, retries: int = 2) -> None:
        logger.info("Embedding transcript blocks for TreeSeg (async)")
        chunks = [block["convo"] for block in self.blocks]
        batch_size = int(self.configs.get("EMBEDDING_BATCH_SIZE", 256) or 256)

        async def run_embed() -> List[List[float]]:
            # Process in batches to control concurrency and payload sizes
            all_embs: List[List[float]] = []
            for i in range(0, len(chunks), batch_size):
                sub = chunks[i:i + batch_size]
                if self.embedder is not None:
                    sub_embs = await self.embedder(sub)
                else:
                    sub_embs = await self._default_embedder(sub)
                all_embs.extend(sub_embs)
            return all_embs

        for attempt in range(1, retries + 1):
            try:
                embs: List[List[float]] = await run_embed()
                if len(embs) != len(chunks):
                    raise ValueError(
                        f"Embedding count mismatch: got {len(embs)} for {len(chunks)} chunks"
                    )
                for block, emb in zip(self.blocks, embs):
                    block["embedding"] = emb
                logger.info(f"Collected {len(embs)} embeddings for TreeSeg (async)")
                return
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"Async embedding failed (attempt {attempt}/{retries}): {e}; retrying...")
                    continue
                logger.error(f"Async embedding failed after {retries} attempts: {e}")
                raise

    def _embed_blocks_with_retry(self) -> None:
        logger.info("Embedding transcript blocks for TreeSeg")
        # Python 3.11+ may not have a default loop in the main thread; create one if needed.
        try:
            loop = asyncio.get_running_loop()
            in_running_loop = True
        except RuntimeError:
            in_running_loop = False
            loop = asyncio.new_event_loop()

        chunks = [block["convo"] for block in self.blocks]

        async def run_embed() -> List[List[float]]:
            if self.embedder is not None:
                return await self.embedder(chunks)
            return await self._default_embedder(chunks)

        # Simple retry loop to be resilient to transient embedding failures
        retries = 2
        for attempt in range(1, retries + 1):
            try:
                if in_running_loop:
                    # Cannot block a running loop; advise callers to use create_async() in async contexts.
                    raise RuntimeError("TreeSegmenter: use create_async() in async contexts")
                # Run the coroutine to completion on our temporary loop
                try:
                    asyncio.set_event_loop(loop)
                except Exception:
                    pass
                embs: List[List[float]] = loop.run_until_complete(run_embed())
                if len(embs) != len(chunks):
                    raise ValueError(
                        f"Embedding count mismatch: got {len(embs)} for {len(chunks)} chunks"
                    )
                for block, emb in zip(self.blocks, embs):
                    block["embedding"] = emb
                logger.info(f"Collected {len(embs)} embeddings for TreeSeg")
                return
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"Embedding failed (attempt {attempt}/{retries}): {e}; retrying...")
                    continue
                logger.error(f"Embedding failed after {retries} attempts: {e}")
                raise
            finally:
                if not in_running_loop:
                    try:
                        asyncio.set_event_loop(None)
                        loop.close()
                    except Exception:
                        pass

    def segment_meeting(self, K: int) -> List[int]:
        """Segment the meeting into up to K segments.

        Returns a transitions_hat vector of length N: 1 at the start index
        of each segment except the first; 0 elsewhere.
        """
        if not self.blocks:
            self.leaves = []
            self.transitions_hat = []
            return []

        root = SegNode(identifier="*", entries=self.blocks, configs=self.configs)
        self.root = root  # type: ignore[attr-defined]

        if root.is_leaf:
            logger.info("Root cannot be split further; single segment")
            self.leaves = [root]
            self.transitions_hat = [0] * len(root.segment)
            return self.transitions_hat

        leaves_heap: List[Tuple[int, SegNode]] = []
        # Use a numeric tiebreaker (start index) to avoid comparing SegNode on equal loss
        boundary: List[Tuple[float, int, SegNode]] = []
        heapq.heappush(boundary, (root.split_loss_delta(), root.segment[0], root))

        total_loss = root.negative_log_likelihood
        min_impr_ratio = float(self.configs.get("MIN_IMPROVEMENT_RATIO", 0.0) or 0.0)
        eps = 1e-12

        while boundary:
            if len(boundary) + len(leaves_heap) == K:
                logger.warning(f"Reached maximum of {K} segments; stopping further splits")
                while boundary:
                    _, _, node = heapq.heappop(boundary)
                    node.is_leaf = True
                    heapq.heappush(leaves_heap, (node.segment[0], node))
                break

            loss_delta, _, node = heapq.heappop(boundary)

            # Evaluate improvement ratio; if too small, stop splitting this node
            improvement_ratio = max(0.0, -loss_delta / (abs(total_loss) + eps))
            if min_impr_ratio > 0.0 and improvement_ratio < min_impr_ratio:
                node.is_leaf = True
                heapq.heappush(leaves_heap, (node.segment[0], node))
                continue

            total_loss += loss_delta

            left, right = node.split()

            for child in (left, right):
                if child.is_leaf:
                    heapq.heappush(leaves_heap, (child.segment[0], child))
                else:
                    heapq.heappush(boundary, (child.split_loss_delta(), child.segment[0], child))

        # Sort leaves by first index to produce ordered segments
        ordered_leaves: List[SegNode] = []
        while leaves_heap:
            ordered_leaves.append(heapq.heappop(leaves_heap)[1])

        self.leaves = ordered_leaves

        # transitions_hat marks segment starts (except the first)
        transitions_hat: List[int] = [0] * len(self.leaves[0].segment)
        transition_indices: List[int] = []
        for leaf in self.leaves[1:]:
            seg_trans = [0] * len(leaf.segment)
            seg_trans[0] = 1
            transition_indices.append(leaf.segment[0])
            transitions_hat.extend(seg_trans)

        self.transitions_hat = transitions_hat
        self.transition_indices = transition_indices  # type: ignore[attr-defined]
        return transitions_hat

    def get_segments(self) -> List[Dict[str, Any]]:
        """Return segments with indices and aggregated metadata.

        Each segment dictionary contains:
            - indices: List[int] indices of utterances in this segment
            - start_index, end_index: int boundaries (inclusive start, inclusive end)
            - start_time, end_time: if available in entries
            - speakers: set/list of speakers in the segment (if speaker is provided)
            - text: concatenated "composite" text of the segment
        """
        if not self.leaves:
            return []

        segments: List[Dict[str, Any]] = []
        for leaf in self.leaves:
            indices = list(leaf.segment)
            seg_entries = [self.blocks[i] for i in indices]
            text = "\n".join([str(e.get("composite", "")) for e in seg_entries]).strip()
            speakers = list({e.get("speaker") for e in seg_entries if e.get("speaker") is not None})
            start_time = None
            end_time = None
            if seg_entries:
                start_time = seg_entries[0].get("start")
                end_time = seg_entries[-1].get("end")

            segments.append(
                {
                    "indices": indices,
                    "start_index": indices[0],
                    "end_index": indices[-1],
                    "start_time": start_time,
                    "end_time": end_time,
                    "speakers": speakers,
                    "text": text,
                }
            )

        return segments

    def get_transition_indices(self) -> List[int]:
        if hasattr(self, "transition_indices"):
            return list(getattr(self, "transition_indices"))
        if not getattr(self, "leaves", None):
            return []
        return [leaf.segment[0] for leaf in self.leaves[1:]]
