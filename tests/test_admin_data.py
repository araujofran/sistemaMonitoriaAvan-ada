from datetime import datetime
from pathlib import Path

from app.database import clear_database, history, list_database_backups, list_periods
from app.service import preflight_paths, process_paths


def _txt(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_duplicate_requires_choice_and_skip_keeps_existing(tmp_path: Path):
    content = "#Cliente: Quero cancelar meu cartão.\n#Atendente: Vou verificar."
    first = _txt(tmp_path / "original.txt", content)
    assert process_paths([first])["processed"] == 1
    renamed = _txt(tmp_path / "renomeado.txt", content)
    preflight = preflight_paths([renamed])
    assert preflight["duplicate_count"] == 1
    skipped = process_paths([renamed], reanalyze=False)
    assert skipped["processed"] == 0
    assert skipped["skipped"] == 1
    assert len(history()) == 1


def test_duplicate_inside_same_upload_is_processed_once(tmp_path: Path):
    content = "#Cliente: Quero renegociar.\n#Atendente: Vou verificar."
    first = _txt(tmp_path / "a.txt", content)
    second = _txt(tmp_path / "b.txt", content)
    preflight = preflight_paths([first, second])
    assert preflight["new"] == 1
    assert preflight["duplicate_count"] == 1
    result = process_paths([first, second])
    assert result["processed"] == 1
    assert result["skipped"] == 1


def test_reanalysis_overwrites_and_creates_safety_backup(tmp_path: Path):
    content = "#Cliente: Preciso de boleto.\n#Atendente: Foi enviado."
    first = _txt(tmp_path / "first.txt", content)
    second = _txt(tmp_path / "second.txt", content)
    process_paths([first])
    result = process_paths([second], reanalyze=True)
    assert result["overwritten"] == 1
    assert result["processed"] == 1
    assert len(history()) == 1
    assert len(list_database_backups()) == 1


def test_history_period_and_clear_product_are_recoverable(tmp_path: Path):
    path = _txt(tmp_path / "vehicle.txt", "#Cliente: Meu veículo está com problema.\n#Atendente: Vou verificar.")
    process_paths([path])
    today = datetime.now().date().isoformat()
    assert list_periods()["days"] == [{"day":today,"interactions":1}]
    assert len(history(day=today, product="Veículos")) == 1
    result = clear_database("Veículos")
    assert result["deleted"] == 1
    assert result["backup"]["filename"].endswith(".db")
    assert history() == []
