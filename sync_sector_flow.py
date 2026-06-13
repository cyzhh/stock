#!/usr/bin/env python3
"""同步近20日板块主力净流入排行到本地 JSON。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app_config import path_from_config
from sector_flow import build_sector_flow_report
from sq_logging import setup_logging

log = setup_logging("stock_quant.sync_sector_flow")


def main() -> dict:
    out_path = path_from_config("sector_flow_20d", "data/sector_flow_20d.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fast = os.environ.get("CI_FAST") == "1"
    if fast and out_path.exists():
        log.info("CI_FAST：复用已有 %s", out_path)
        return json.loads(out_path.read_text(encoding="utf-8"))

    try:
        data = build_sector_flow_report(days=20, top_n=10)
        data["synced_at"] = datetime.now(timezone.utc).isoformat()
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("已保存 %s (行业TOP %s)", out_path, len(data["industry"]["top"]))
        return data
    except Exception as e:
        if out_path.exists():
            log.warning("拉取失败，使用缓存: %s", e)
            return json.loads(out_path.read_text(encoding="utf-8"))
        raise


if __name__ == "__main__":
    main()
