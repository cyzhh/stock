#!/usr/bin/env python3
"""为扫描结果补全 multi_factor 数据。"""

from __future__ import annotations

import time
from typing import Any

from app_config import scanner_config
from factor_model import compute_multi_factor, estimate_factors_from_latest
from kline_fetcher import bars_to_dicts, fetch_klines
from sq_logging import setup_logging

log = setup_logging("stock_quant.enrich")


def _needs_enrich(row: dict) -> bool:
    mf = row.get("multi_factor") or {}
    factors = mf.get("factors") or {}
    if not factors:
        return True
    return all(float(factors.get(k) or 0) == 0 for k in ("momentum", "volume", "trend", "pullback", "reversal"))


def enrich_stock_row(row: dict[str, Any], cfg: dict, fetch_kline: bool = True) -> dict[str, Any]:
    if not _needs_enrich(row):
        return row

    code = row.get("code", "")
    market = row.get("market") or ("sh" if str(code).startswith("6") else "sz")
    latest = row.get("latest") or {}

    if fetch_kline and code:
        try:
            bars = bars_to_dicts(fetch_klines(code, market))
            if len(bars) >= 20:
                mf = compute_multi_factor(bars, cfg)
                row = {**row, "multi_factor": mf, "composite_score": mf.get("composite_score", 0)}
                row["top_score"] = max(row.get("top_score", 0), row["composite_score"])
                return row
        except Exception as e:
            log.warning("补算因子失败 %s: %s，使用 latest 估算", code, e)

    if latest:
        mf = estimate_factors_from_latest(latest)
        row = {**row, "multi_factor": mf, "composite_score": mf.get("composite_score", 0)}
        row["top_score"] = max(row.get("top_score", 0), row["composite_score"])
    return row


def enrich_scan_data(scan: dict[str, Any], fetch_kline: bool = True) -> dict[str, Any]:
    if not scan:
        return scan
    cfg = scanner_config()
    enriched: dict[str, dict] = {}

    def _process(rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        for i, row in enumerate(rows):
            code = row.get("code")
            if code and code in enriched:
                out.append(enriched[code])
                continue
            if i > 0 and fetch_kline:
                time.sleep(0.3)
            updated = enrich_stock_row(row, cfg, fetch_kline=fetch_kline)
            if code:
                enriched[code] = updated
            out.append(updated)
        return out

    scan = dict(scan)
    scan["picks"] = _process(list(scan.get("picks") or []))
    scan["all_results"] = _process(list(scan.get("all_results") or scan.get("picks") or []))
    if scan["all_results"]:
        scan["picks"] = sorted(
            [r for r in scan["picks"] if r.get("qualified", True)],
            key=lambda r: (r.get("composite_score", 0), r.get("strategy_count", 0)),
            reverse=True,
        )
        scan["pick_count"] = len(scan["picks"])
    log.info("因子补全完成: picks=%s", scan.get("pick_count", 0))
    return scan
