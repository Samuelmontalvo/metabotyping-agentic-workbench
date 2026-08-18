"""Logging helpers."""

from __future__ import annotations

import logging


def get_logger(name: str = "metabotyping_agentic") -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return logging.getLogger(name)

