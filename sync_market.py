#!/usr/bin/env python3
"""同步恢恢量化市场快照到本地 JSON。"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from app_config import path_from_config, sync_config
from sq_logging import setup_logging

log = setup_logging("stock_quant.sync")

HHXG_URL = "https://hhxg.top/static/data/assistant/skill_snapshot.json"


def _skill_script() -> Path:
    cfg = sync_config()
    rel = cfg.get("hhxg_skill_dir", "../.cursor/skills/hhxg-market/scripts")
    root = Path(__file__).parent
    return (root / rel / "fetch_snapshot.py").resolve()


def fetch_snapshot_direct() -> dict:
    """内置拉取（部署到 GitHub 时无 Cursor skill 目录）。"""
    cfg = sync_config()
    timeout = int(cfg.get("timeout_sec", 20))
    retries = int(cfg.get("retries", 2))
    headers = {"User-Agent": "stock-quant/1.0", "X-Skill-Client": "github-pages"}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(HHXG_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0)
    raise RuntimeError(f"hhxg 快照拉取失败: {last_err}")


def fetch_snapshot_via_skill() -> dict:
    script = _skill_script()
    if not script.exists():
        raise FileNotFoundError(f"找不到 hhxg 脚本: {script}")
    cmd = [sys.executable, str(script), "--json"]
    log.info("拉取市场快照: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "fetch_snapshot 失败")
    return json.loads(proc.stdout)


def fetch_snapshot() -> dict:
    script = _skill_script()
    if script.exists():
        try:
            return fetch_snapshot_via_skill()
        except Exception as e:
            log.warning("skill 拉取失败，回退直连: %s", e)
    log.info("直连拉取 hhxg 快照")
    return fetch_snapshot_direct()


def main() -> dict:
    out_path = path_from_config("market_snapshot", "data/market_snapshot.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_snapshot()
    data["_synced_at"] = datetime.now(timezone.utc).isoformat()
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("已保存 %s (date=%s)", out_path, data.get("date"))
    return data


if __name__ == "__main__":
    main()
