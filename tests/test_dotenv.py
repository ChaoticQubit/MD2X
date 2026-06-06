import os
from md2x.dotenv import _parse, load_dotenv


def test_parse_basic_and_quotes_and_comments():
    text = (
        "# a comment\n"
        "\n"
        "FOO=bar\n"
        "export BAZ = qux\n"
        'QUOTED="with spaces"\n'
        "SQUOTED='single'\n"
        "HASHED=nv#api#key\n"   # '#' inside value preserved (not an inline comment)
        "NOEQUALS\n"            # skipped
        "=novalue\n"            # skipped (empty key)
    )
    d = _parse(text)
    assert d == {
        "FOO": "bar",
        "BAZ": "qux",
        "QUOTED": "with spaces",
        "SQUOTED": "single",
        "HASHED": "nv#api#key",
    }


def test_load_sets_missing_and_returns_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("MD2X_TEST_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("MD2X_TEST_KEY=fromfile\n", encoding="utf-8")
    loaded = load_dotenv([env, tmp_path / "missing.env"])
    assert loaded == [env]                       # only existing file reported
    assert os.environ["MD2X_TEST_KEY"] == "fromfile"


def test_real_env_is_never_overridden(tmp_path, monkeypatch):
    monkeypatch.setenv("MD2X_TEST_KEY", "fromenv")
    env = tmp_path / ".env"
    env.write_text("MD2X_TEST_KEY=fromfile\n", encoding="utf-8")
    load_dotenv([env])
    assert os.environ["MD2X_TEST_KEY"] == "fromenv"   # env wins over .env


def test_first_file_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("MD2X_TEST_KEY", raising=False)
    a = tmp_path / "a.env"
    b = tmp_path / "b.env"
    a.write_text("MD2X_TEST_KEY=first\n", encoding="utf-8")
    b.write_text("MD2X_TEST_KEY=second\n", encoding="utf-8")
    load_dotenv([a, b])
    assert os.environ["MD2X_TEST_KEY"] == "first"     # earlier path wins


def test_same_file_loaded_once(tmp_path, monkeypatch):
    monkeypatch.delenv("MD2X_TEST_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("MD2X_TEST_KEY=x\n", encoding="utf-8")
    loaded = load_dotenv([env, env])              # cwd == project root case
    assert loaded == [env]                        # reported once, not twice
