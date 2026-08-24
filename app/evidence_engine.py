from __future__ import annotations

import re
import unicodedata
from .catalog import DETECTORS
from .config import NEGATION_WINDOW
from .domain import Evidence, Turn


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def _negated(text: str, start: int) -> bool:
    before = _plain(text[max(0, start - NEGATION_WINDOW):start])
    return bool(re.search(r"(?:\bnao\b|\bnunca\b|\bnem\b|\bjamais\b)\s+(?:\w+\s+){0,4}$", before))


def collect_evidence(turns: list[Turn]) -> list[Evidence]:
    found: list[Evidence] = []
    for turn in turns:
        for detector in DETECTORS:
            if detector.speaker != "ANY" and detector.speaker != turn.speaker:
                continue
            for match in re.finditer(detector.pattern, turn.text_original, detector.flags):
                negated = _negated(turn.text_original, match.start())
                # Patterns that encode negation are events in their own right.
                if detector.name in {"nao_resolucao", "transferencia_negada", "contestacao"}:
                    negated = False
                found.append(Evidence(detector.name, detector.regex_id, detector.group, turn.speaker,
                    match.group(0), turn.text_normalized, turn.char_start + match.start(),
                    turn.char_start + match.end(), turn.number, negated, "ALTA", list(detector.criteria)))
    return found

