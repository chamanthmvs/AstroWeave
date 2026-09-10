from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once for the whole process.

    Level defaults to the ASTROWEAVE_LOG_LEVEL env var, falling back to INFO.
    Safe to call multiple times; only the first call takes effect.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    resolved_level = (level or os.environ.get("ASTROWEAVE_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, ensuring logging is configured first."""
    configure_logging()
    return logging.getLogger(name)
