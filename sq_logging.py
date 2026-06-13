#!/usr/bin/env python3
"""日志配置。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app_config import logging_config, path_from_config


def setup_logging(name: str = "stock_quant") -> logging.Logger:
    cfg = logging_config()
    level = getattr(logging, str(cfg.get("level", "INFO")).upper(), logging.INFO)
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if cfg.get("console", True):
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)
    log_file = cfg.get("file")
    if log_file:
        path = path_from_config("logs_dir", "logs") / Path(log_file).name
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    return log
