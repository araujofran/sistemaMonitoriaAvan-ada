from pathlib import Path
from app.database import batch_summary, connect, get_interaction
from app.service import process_paths
from app.migration import run_product_data_migrations
import json


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


def test_attendant_data_migration_is_automatic_and_idempotent():
    with connect() as db:
        db.execute("INSERT INTO analysis_batches(id,name,status,total_files) VALUES('legacy','Legado','DONE',1)")
        db.execute("""INSERT INTO interactions(id,batch_id,filename,content_hash,analysis_status,score_operator,
                   score_experience,product,motive,analysis_json) VALUES('old','legacy','old.txt','old-hash','VALID',0,0,'Consignado','Outro',?)""",
                   (json.dumps({"atendente":"Não identificado"}),))
        db.execute("INSERT INTO transcript_turns(interaction_id,turn_number,speaker,text_original) VALUES('old',1,'ATENDENTE','Bom dia, me chamo Laura.')")
    first = run_product_data_migrations()
    second = run_product_data_migrations()
    assert first["status"] == "applied" and first["updated"] == 1
    assert second["status"] == "already_applied"
    assert get_interaction("old")["atendente"] == "Laura"
    with connect() as db:
        assert db.execute("SELECT COUNT(*) FROM data_migrations").fetchone()[0] == 1
