from __future__ import annotations

import re
import unicodedata
from .domain import Turn

SPEAKER_RE = re.compile(r"^\s*#?\s*(atendente|operador|agente|cliente|consumidor|usu[aá]rio)\s*[:\-]\s*(.*)$", re.I)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_transcript(text: str) -> list[Turn]:
    turns: list[Turn] = []
    cursor = 0
    current_speaker = "DESCONHECIDO"
    pending: list[str] = []
    pending_start = 0

    def flush(end: int) -> None:
        nonlocal pending
        value = normalize(" ".join(pending))
        if value:
            turns.append(Turn(len(turns) + 1, current_speaker, value, normalize(value).lower(), pending_start, end))
        pending = []

    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        match = SPEAKER_RE.match(line)
        if match:
            flush(cursor)
            label = match.group(1).lower()
            current_speaker = "ATENDENTE" if label in {"atendente", "operador", "agente"} else "CLIENTE"
            pending_start = cursor
            pending = [match.group(2)] if match.group(2) else []
        elif line.strip():
            if not pending:
                pending_start = cursor
            pending.append(line)
        cursor += len(raw)
    flush(len(text))
    return turns or [Turn(1, "DESCONHECIDO", normalize(text), normalize(text).lower(), 0, len(text))]

