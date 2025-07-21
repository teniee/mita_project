import os
from types import SimpleNamespace

import pytest

import scripts.backup_database as backup


def test_backup_missing_env(monkeypatch):
    with pytest.raises(RuntimeError):
        backup.backup_database()


def test_backup_runs(monkeypatch, tmp_path):
    env = {"DATABASE_URL": "postgres://db", "S3_BUCKET": "b"}
    monkeypatch.setattr(backup, "subprocess", SimpleNamespace(run=lambda *a, **k: None))
    dummy_s3 = SimpleNamespace(
        upload_file=lambda *a, **k: None,
        list_objects_v2=lambda Bucket: {"Contents": []},
        delete_object=lambda **k: None,
    )
    monkeypatch.setattr(backup.boto3, "client", lambda *a, **k: dummy_s3)
    monkeypatch.setattr(backup.tempfile, "TemporaryDirectory", lambda: tmp_path)
    monkeypatch.setitem(os.environ, "DATABASE_URL", env["DATABASE_URL"])
    monkeypatch.setitem(os.environ, "S3_BUCKET", env["S3_BUCKET"])
    backup.backup_database()
