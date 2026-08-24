from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Turn:
    number: int
    speaker: str
    text_original: str
    text_normalized: str
    char_start: int
    char_end: int


@dataclass(slots=True)
class Evidence:
    detector: str
    regex_id: str
    category: str
    speaker: str
    text: str
    normalized_text: str
    start: int
    end: int
    turn_number: int
    is_negated: bool = False
    confidence: str = "ALTA"
    criteria: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CriterionResult:
    code: str
    name: str
    group: str
    weight: float
    classification: str
    factor: float
    score: float
    justification: str
    evidence: list[str] = field(default_factory=list)
    penalty: float = 0
    bonus: float = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

