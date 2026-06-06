"""Central logging for md2x.

stdlib ``logging``, everything namespaced under the ``md2x`` logger. Library
modules call ``get_logger(__name__)`` and never configure handlers; the CLI
calls ``setup_logging()`` once (twice in practice — an early default-init so
startup steps are captured, then a reconfigure once flags are parsed).

Levels:
  - INFO  (default)  — one line per pipeline step, so a normal run reads like a
                       trace: config loaded, N docs, architect plan, each page,
                       write, deploy.
  - DEBUG (-v)       — model spec, prompt sizes, raw model responses, timings,
                       token usage.
  - WARNING          — every degradation or guardrail trip.
  - ERROR            — failures.

A ``--log-file`` always records the full DEBUG trace regardless of the console
level, so you can run quietly and still keep a complete log on disk.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

ROOT = "md2x"

_CONSOLE_FMT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
_CONSOLE_DATEFMT = "%H:%M:%S"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"

_LEVEL_NAMES = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Keep the library silent until an application configures handlers (and stop
# Python emitting "No handlers could be found" if it never does).
logging.getLogger(ROOT).addHandler(logging.NullHandler())


def _resolve_console_level(verbosity: int, quiet: bool,
                           level: str | None) -> tuple[int, str | None]:
    """Return (numeric level, invalid-name-or-None).

    Precedence: explicit --log-level > MD2X_LOG_LEVEL env > --quiet > -v > INFO.
    A bad explicit/env name is ignored (falls through) and reported back so the
    caller can warn once a handler exists.
    """
    name = level or os.environ.get("MD2X_LOG_LEVEL")
    if name:
        canon = name.strip().upper()
        if canon in _LEVEL_NAMES:
            return getattr(logging, canon), None
        bad = name  # remember to warn, then fall through to flag-based level
    else:
        bad = None
    if quiet:
        return logging.WARNING, bad
    if verbosity >= 1:
        return logging.DEBUG, bad
    return logging.INFO, bad


def setup_logging(verbosity: int = 0, *, quiet: bool = False,
                  level: str | None = None,
                  log_file: str | Path | None = None) -> logging.Logger:
    """(Re)configure the ``md2x`` logger. Idempotent — safe to call repeatedly."""
    logger = logging.getLogger(ROOT)
    console_level, bad_name = _resolve_console_level(verbosity, quiet, level)

    # Replace any handlers from a previous call so re-init never duplicates
    # (and closes file handles from an earlier --log-file).
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler()  # stderr; stdout stays for program output
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, _CONSOLE_DATEFMT))
    logger.addHandler(console)

    effective = console_level
    if log_file:
        path = Path(log_file)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(path), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # full trace on disk, always
        file_handler.setFormatter(logging.Formatter(_CONSOLE_FMT, _FILE_DATEFMT))
        logger.addHandler(file_handler)
        effective = min(effective, logging.DEBUG)

    # The logger must pass anything its handlers might want.
    logger.setLevel(effective)

    if bad_name is not None:
        logger.warning("ignoring invalid log level %r (use one of %s)",
                       bad_name, ", ".join(_LEVEL_NAMES))
    if log_file:
        logger.debug("writing full debug trace to %s", log_file)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ``md2x`` namespace.

    Pass ``__name__`` from any module inside the ``md2x`` package (already
    ``md2x.*``) and it is returned as-is; a bare name is prefixed with ``md2x.``.
    """
    if not name or name == ROOT:
        return logging.getLogger(ROOT)
    if name.startswith(ROOT + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT}.{name}")
