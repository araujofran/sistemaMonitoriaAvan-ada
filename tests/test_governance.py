from pathlib import Path


def test_bootstrap_roles_and_product_assignments(tmp_path, monkeypatch):
    import app.governance as governance
    monkeypatch.setattr(governance, "GOVERNANCE_DB", tmp_path / "governance.db")
    for _, password_env, _, _ in governance.BOOTSTRAP:
        monkeypatch.setenv(password_env, "senha-segura-de-teste")
    governance.init_governance()
    data = governance.list_governance()
    users = {u["username"]: u for u in data["users"]}
    assert users["fran"]["role"] == "admin"
    assert users["joelma"]["role"] == "gestao"
    assert [p["slug"] for p in users["bruna"]["products"]] == ["veiculos"]
    assert {p["slug"] for p in users["marcela"]["products"]} == {"investe"}


def test_product_databases_are_physically_isolated(tmp_path: Path):
    import app.database as database
    from app.tenancy import ACTIVE_DATABASE
    vehicle_db, card_db = tmp_path / "veiculos.db", tmp_path / "cartao.db"
    token = ACTIVE_DATABASE.set(vehicle_db)
    try:
        database.init_db()
        with database.connect() as db:
            db.execute("INSERT INTO analysis_batches(id,name,status,total_files) VALUES('v','Veículos','DONE',1000)")
    finally: ACTIVE_DATABASE.reset(token)
    token = ACTIVE_DATABASE.set(card_db)
    try:
        database.init_db()
        with database.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM analysis_batches").fetchone()[0] == 0
            db.execute("INSERT INTO analysis_batches(id,name,status,total_files) VALUES('c','Cartão','DONE',100)")
    finally: ACTIVE_DATABASE.reset(token)
    assert vehicle_db.exists() and card_db.exists() and vehicle_db != card_db


def test_legacy_product_classification_is_conservative():
    from app.migration import classify_legacy_product
    assert classify_legacy_product("Cartão de Crédito") == "cartao"
    assert classify_legacy_product("Cartão Consignado") == "consignado"
    assert classify_legacy_product("Seguros") == "seguros"
    assert classify_legacy_product("Boleto") == "legado_nao_classificado"
