from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimilarityScore:
    value: float

    def __post_init__(self) -> None:
        score = float(self.value)
        if score < 0.0 or score > 1.0:
            raise ValueError("Similarity score must be between 0 and 1.")
        object.__setattr__(self, "value", score)
