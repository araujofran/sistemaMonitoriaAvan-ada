from pathlib import Path
from app.database import batch_summary, connect, get_interaction
from app.service import process_paths


def test_batch_persistence(tmp_path: Path):
    transcript = tmp_path / "one.txt"
    transcript.write_text("#Cliente: Quero um boleto.\n#Atendente: Foi enviado.", encoding="utf-8")
    result = process_paths([transcript], "Teste")
    assert result["failed"] == 0
    assert batch_summary(result["batch_id"])["total"] == 1
    assert get_interaction(result["items"][0]["id"])["analysis_status"] == "VALID"
    with connect() as db:
        causal = db.execute("SELECT mode,status FROM causal_analysis_results WHERE interaction_id=?", (result["items"][0]["id"],)).fetchone()
    assert causal["mode"] == "shadow"
