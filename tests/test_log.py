import logging

import pytest

import md2x.log as mlog


@pytest.fixture(autouse=True)
def _restore_logger():
    """Snapshot/restore the global md2x logger so tests don't leak state."""
    logger = logging.getLogger("md2x")
    saved, saved_level = list(logger.handlers), logger.level
    yield
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    for h in saved:
        logger.addHandler(h)
    logger.setLevel(saved_level)


def test_default_level_is_info():
    mlog.setup_logging()
    assert logging.getLogger("md2x").level == logging.INFO


def test_verbose_enables_debug():
    mlog.setup_logging(verbosity=1)
    assert logging.getLogger("md2x").level == logging.DEBUG


def test_quiet_sets_warning():
    mlog.setup_logging(quiet=True)
    assert logging.getLogger("md2x").level == logging.WARNING


def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("MD2X_LOG_LEVEL", "DEBUG")
    mlog.setup_logging()
    assert logging.getLogger("md2x").level == logging.DEBUG


def test_explicit_level_overrides_env(monkeypatch):
    monkeypatch.setenv("MD2X_LOG_LEVEL", "ERROR")
    mlog.setup_logging(level="DEBUG")
    assert logging.getLogger("md2x").level == logging.DEBUG


def test_invalid_level_falls_back_to_info_and_warns(capsys):
    mlog.setup_logging(level="LOUD")
    assert logging.getLogger("md2x").level == logging.INFO
    assert "invalid log level" in capsys.readouterr().err


def test_idempotent_no_duplicate_handlers():
    mlog.setup_logging()
    mlog.setup_logging()
    assert len(logging.getLogger("md2x").handlers) == 1


def test_log_file_captures_debug_even_when_console_quiet(tmp_path):
    logfile = tmp_path / "trace.log"
    mlog.setup_logging(quiet=True, log_file=logfile)
    mlog.get_logger("md2x.test").debug("hello-debug-trace")
    assert "hello-debug-trace" in logfile.read_text()


def test_console_respects_level(capsys):
    mlog.setup_logging(quiet=True)  # WARNING
    log = mlog.get_logger("md2x.test")
    log.info("info-should-not-appear")
    log.warning("warn-should-appear")
    err = capsys.readouterr().err
    assert "warn-should-appear" in err
    assert "info-should-not-appear" not in err


def test_log_file_parent_dir_is_created(tmp_path):
    logfile = tmp_path / "nested" / "dir" / "trace.log"
    mlog.setup_logging(log_file=logfile)
    mlog.get_logger("md2x.test").info("made-it")
    assert logfile.exists() and "made-it" in logfile.read_text()


def test_get_logger_namespacing():
    assert mlog.get_logger("md2x.site.x").name == "md2x.site.x"
    assert mlog.get_logger("foo").name == "md2x.foo"
    assert mlog.get_logger().name == "md2x"
