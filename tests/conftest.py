import pytest


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    import app.database as database
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_BACKUP_DIR", tmp_path / "backups")
    database.init_db()

