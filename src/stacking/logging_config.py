"""Shared logging setup for the Sony Focus-Stacking app.

Importing this module configures the root logger with a Rich console handler.
"""

from __future__ import annotations

import logging
import os
from rich.logging import RichHandler

# Read desired level from env; default to INFO
_log_level = os.getenv("STACKING_LOG_LEVEL", "INFO").upper()
_logging_level = getattr(logging, _log_level, logging.INFO)

logging.basicConfig(
    level=_logging_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

# Convenience helper
def get_logger(name: str) -> logging.Logger:
    """Return a logger with *name* using the shared Rich configuration."""
    return logging.getLogger(name) 