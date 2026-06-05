import base64
from pathlib import Path
import pytest
from md2x.site.deploy import vercel


def _site(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Hi</h1>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "site.css").write_text("body{}")
    return tmp_path


def test_collect_files_walks_recursively(tmp_path):
    files = vercel.collect_files(_site(tmp_path))
    paths = sorted(f["file"] for f in files)
    assert paths == ["assets/site.css", "index.html"]
    for f in files:
        assert f["encoding"] == "base64"
        base64.b64decode(f["data"])  # valid base64


def test_build_payload_shape(tmp_path):
    files = vercel.collect_files(_site(tmp_path))
    payload = vercel.build_payload("my-site", files, team_id=None,
                                   production=True)
    assert payload["name"] == "my-site"
    assert payload["projectSettings"]["framework"] is None
    assert payload["target"] == "production"
    assert payload["files"] == files


def test_deploy_missing_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    cfg = {"deploy": {"provider": "vercel", "token_env": "VERCEL_TOKEN",
                      "project": None, "team_id": None, "production": True}}
    with pytest.raises(RuntimeError):
        vercel.deploy_vercel(_site(tmp_path), cfg)
