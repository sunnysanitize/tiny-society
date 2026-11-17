"""Sentence embeddings for memory recall.

Memory retrieval used to score relevance by shared words, so "the abbot fell into a
fever" never recalled "our teacher is gravely ill" — the agent forgot yesterday's key
event whenever today's wording differed. A small local embedding model scores meaning
instead. It runs on CPU through ONNX (fastembed), so it adds no API cost.

Opt-in (MEMORY_EMBEDDINGS=on, plus `pip install fastembed`): a 16-vs-16 run A/B showed
no measurable story gain over word overlap (7.21 vs 7.24 judge mean), and the model
costs ~130MB and a few hundred MB of RAM. When off, not installed, or the model can't
load, `embed` returns None and callers keep the word-overlap scoring.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

MODEL_NAME = "BAAI/bge-small-en-v1.5"
# Memory texts recur across days and agents; cache their vectors.
_CACHE_MAX = 20_000

_lock = threading.Lock()
_model = None
_failed = False
_cache: dict[str, "object"] = {}


def enabled() -> bool:
    flag = os.getenv("MEMORY_EMBEDDINGS", "").strip().lower()
    return flag in ("on", "1", "true", "yes")


def _get_model():
    global _model, _failed
    if _model is not None or _failed:
        return _model
    try:
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL_NAME)
    except Exception as e:  # missing package, no network for the first download, ...
        logging.warning(f"Embeddings unavailable, using word overlap for memory recall: {e}")
        _failed = True
    return _model


def embed(texts: list[str]) -> Optional[list]:
    """Unit-normalized vectors for `texts`, or None if embeddings are unavailable."""
    if not texts or not enabled():
        return None
    with _lock:
        model = _get_model()
        if model is None:
            return None
        missing = list(dict.fromkeys(t for t in texts if t not in _cache))
        if missing:
            try:
                for t, v in zip(missing, model.embed(missing)):
                    _cache[t] = v
            except Exception as e:
                logging.warning(f"Embedding failed, using word overlap: {e}")
                return None
            if len(_cache) > _CACHE_MAX:
                for t in list(_cache)[: len(_cache) - _CACHE_MAX]:
                    del _cache[t]
        return [_cache[t] for t in texts]
