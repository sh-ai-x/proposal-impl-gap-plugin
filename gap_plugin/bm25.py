"""Hand-rolled Okapi BM25 index over the 'After bullets' evidence corpus (stdlib only)."""
from __future__ import annotations

import math
from collections import Counter

from gap_plugin.text import tokenize as _tokenize
from gap_plugin.types import Candidate, EvidenceItem

K1 = 1.5
B = 0.75


class BM25Index:
    def __init__(self) -> None:
        self._items: list[EvidenceItem] = []
        self._doc_tokens: list[Counter[str]] = []
        self._doc_lens: list[int] = []
        self._avg_len: float = 0.0
        self._idf: dict[str, float] = {}

    def build(self, corpus: list[EvidenceItem]) -> None:
        self._items = list(corpus)
        self._doc_tokens = [Counter(_tokenize(item.text)) for item in self._items]
        self._doc_lens = [sum(c.values()) for c in self._doc_tokens]
        n = len(self._items)
        self._avg_len = (sum(self._doc_lens) / n) if n else 0.0

        df: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            df.update(tokens.keys())
        self._idf = {
            term: math.log((n - freq + 0.5) / (freq + 0.5) + 1) for term, freq in df.items()
        }

    def query(self, text: str, k: int = 10) -> list[Candidate]:
        if not self._items:
            return []
        q_tokens = set(_tokenize(text))
        scores: list[tuple[float, int]] = []
        for i, tokens in enumerate(self._doc_tokens):
            dl = self._doc_lens[i]
            score = 0.0
            for term in q_tokens:
                f = tokens.get(term, 0)
                if f == 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = f + K1 * (1 - B + B * dl / self._avg_len) if self._avg_len else f
                score += idf * (f * (K1 + 1)) / denom
            if score > 0:
                scores.append((score, i))

        scores.sort(key=lambda pair: pair[0], reverse=True)
        results: list[Candidate] = []
        for score, i in scores[:k]:
            item = self._items[i]
            results.append(
                Candidate(
                    file_path=item.file_path,
                    snippet=item.text[:280],
                    score=score,
                    source="bm25",
                )
            )
        return results
