from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import re
from typing import Any, Iterable

import pandas as pd

from .products import normalize_key

TEXT_EXTENSIONS = {".txt"}
DELIMITED_EXTENSIONS = {".csv", ".tsv"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls", ".xlsb", ".ods"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | DELIMITED_EXTENSIONS | EXCEL_EXTENSIONS
TRANSCRIPT_ALIASES = {"transcricao", "transcription", "texto", "texto_transcricao", "dialogo", "conversa", "atendimento", "conteudo"}


@dataclass(slots=True)
class SourceRecord:
    text: str
    source_filename: str
    display_filename: str
    source_type: str
    sheet_name: str | None = None
    source_row: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _clean(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try: return value.isoformat()
        except Exception: pass
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return str(value).strip() if not isinstance(value, (int, float, bool)) else value


def _transcript_column(frame: pd.DataFrame) -> Any | None:
    for column in frame.columns:
        if normalize_key(str(column)) in TRANSCRIPT_ALIASES:
            return column
    best, score = None, 0.0
    for column in frame.columns:
        values = frame[column].dropna().astype(str).head(100)
        if values.empty: continue
        speaker_ratio = values.str.contains(r"#?\s*(?:Atendente|Cliente)\s*:", case=False, regex=True).mean()
        length_ratio = values.str.len().mean() / 1000
        candidate = speaker_ratio * 10 + min(length_ratio, 3)
        if candidate > score:
            best, score = column, candidate
    return best if score >= 1 else None


def _records_from_frame(frame: pd.DataFrame, path: Path, sheet: str | None) -> list[SourceRecord]:
    frame = frame.dropna(how="all")
    transcript_column = _transcript_column(frame)
    if transcript_column is None:
        return []
    records: list[SourceRecord] = []
    for position, (_, row) in enumerate(frame.iterrows(), start=2):
        text = _clean(row.get(transcript_column))
        if not text: continue
        metadata = {str(column): _clean(row.get(column)) for column in frame.columns if column != transcript_column}
        metadata = {k: v for k, v in metadata.items() if v is not None}
        display = f"{path.name} · {sheet or 'dados'} · linha {position}"
        records.append(SourceRecord(str(text), path.name, display, path.suffix.lower().lstrip("."), sheet, position, metadata))
    return records


def load_source(path: Path) -> list[SourceRecord]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Formato não suportado: {suffix or 'sem extensão'}")
    if suffix in TEXT_EXTENSIONS:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        return [SourceRecord(raw, path.name, path.name, "txt")]
    if suffix in DELIMITED_EXTENSIONS:
        sep = "\t" if suffix == ".tsv" else None
        frame = pd.read_csv(path, sep=sep, engine="python", dtype=object, encoding_errors="replace")
        return _records_from_frame(frame, path, None)
    records: list[SourceRecord] = []
    # ExcelFile owns the engine's file handle. It must be closed explicitly on
    # Windows, otherwise TemporaryDirectory cannot remove the uploaded file.
    with pd.ExcelFile(path) as book:
        for sheet in book.sheet_names:
            frame = pd.read_excel(book, sheet_name=sheet, dtype=object)
            records.extend(_records_from_frame(frame, path, str(sheet)))
    if not records:
        raise ValueError("Nenhuma coluna de transcrição foi identificada nas abas do arquivo")
    return records


def load_sources(paths: Iterable[Path]) -> tuple[list[SourceRecord], list[dict[str, str]]]:
    records: list[SourceRecord] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            records.extend(load_source(path))
        except Exception as exc:
            errors.append({"filename": path.name, "error": str(exc)})
    return records, errors
