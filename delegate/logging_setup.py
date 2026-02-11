"""Unified logging configuration for Delegate.

Provides a single rotated log file shared by the daemon and all agent turns.
A ``contextvars.ContextVar`` carries the *caller* identity (agent name + role,
or ``"daemon"``) so every log line is attributed without per-module loggers.

Usage::

    from delegate.logging_setup import configure_logging, log_caller

    configure_logging(hc_home)          # call once at process startup
    log_caller.set("alice:engineer")    # set per-turn in runtime.py
"""

import contextvars
import logging
import logging.handlers
from pathlib import Path

# ---------------------------------------------------------------------------
# Context variable — identifies who is logging
# ---------------------------------------------------------------------------

log_caller: contextvars.ContextVar[str] = contextvars.ContextVar(
    "log_caller", default="daemon",
)


# ---------------------------------------------------------------------------
# Filter that injects %(caller)s from the context var
# ---------------------------------------------------------------------------

class _CallerFilter(logging.Filter):
    """Inject *caller* into every log record from the context var."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.caller = log_caller.get()  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_configured = False

LOG_FORMAT = "%(asctime)s [%(caller)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    hc_home: Path | None = None,
    *,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console: bool = True,
) -> None:
    """Set up unified logging with rotation.

    * If *hc_home* is given, logs to ``{hc_home}/delegate.log`` with rotation.
    * If *console* is True (default), also logs to stderr.
    * Safe to call multiple times — only the first call takes effect.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    caller_filter = _CallerFilter()

    # File handler (rotated)
    if hc_home is not None:
        hc_home.mkdir(parents=True, exist_ok=True)
        log_path = hc_home / "delegate.log"
        fh = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)
        fh.addFilter(caller_filter)
        root.addHandler(fh)

    # Console handler
    if console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(fmt)
        ch.addFilter(caller_filter)
        root.addHandler(ch)


def log_file_path(hc_home: Path) -> Path:
    """Return the path to the log file (for daemon stderr redirect)."""
    return hc_home / "delegate.log"
