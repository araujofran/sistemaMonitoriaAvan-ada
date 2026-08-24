def test_error_is_recorded_with_searchable_id(tmp_path, monkeypatch):
    import app.diagnostics as diagnostics
    monkeypatch.setattr(diagnostics, "DIAGNOSTICS_DIR", tmp_path)
    monkeypatch.setattr(diagnostics, "ERROR_LOG", tmp_path / "errors.jsonl")
    try:
        raise PermissionError("arquivo bloqueado")
    except PermissionError as exc:
        error_id = diagnostics.record_error("POST", "/upload", exc)
    errors = diagnostics.recent_errors()
    assert errors[0]["id"] == error_id
    assert errors[0]["type"] == "PermissionError"
    assert "arquivo bloqueado" in errors[0]["traceback"]
