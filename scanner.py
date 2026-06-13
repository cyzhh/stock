#!/usr/bin/env python3
"""扫描自选股 + 热门题材龙头，输出策略命中结果。"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app_config import path_from_config, scanner_config
from factor_model import compute_multi_factor
from indicators import compute_all
from kline_fetcher import bars_to_dicts, fetch_klines
from kline_patterns import detect_patterns, load_pattern_selection, registry_for_ui
from sq_logging import setup_logging
from strategies import run_all_strategies

log = setup_logging("stock_quant.scanner")


def load_watchlist() -> list[dict[str, str]]:
    path = path_from_config("watchlist", "data/watchlist.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("stocks") or [])


def _parse_code(raw: str) -> tuple[str, str]:
    """002971.SZ → (002971, sz)"""
    raw = str(raw or "").strip()
    if "." in raw:
        code, suffix = raw.split(".", 1)
        market = "sh" if suffix.upper() == "SH" else "sz"
        return code.zfill(6), market
    code = raw.zfill(6)
    market = "sh" if code.startswith(("6", "5", "9")) else "sz"
    return code, market


def stocks_from_snapshot(snapshot: dict) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []

    def add(code_raw: str, name: str) -> None:
        if not code_raw:
            return
        code, market = _parse_code(code_raw)
        if not code or code == "000000" or code in seen:
            return
        seen.add(code)
        out.append({"code": code, "name": name or code, "market": market})

    for theme in snapshot.get("hot_themes") or []:
        for stock in theme.get("top_stocks") or theme.get("leaders") or theme.get("stocks") or []:
            if isinstance(stock, dict):
                add(stock.get("code", ""), stock.get("name", ""))

    ladder_detail = snapshot.get("ladder_detail") or {}
    for level in ladder_detail.get("levels") or []:
        for stock in level.get("stocks") or []:
            if isinstance(stock, dict) and stock.get("is_success", True):
                add(stock.get("code", ""), stock.get("name", ""))

    hotmoney = snapshot.get("hotmoney") or {}
    for stock in hotmoney.get("top_buys") or hotmoney.get("stocks") or []:
        if isinstance(stock, dict):
            add(stock.get("code", ""), stock.get("name", ""))

    return out


def analyze_stock(stock: dict[str, str], cfg: dict) -> dict[str, Any] | None:
    code = stock["code"]
    try:
        bars = fetch_klines(code, stock.get("market") or None)
    except Exception as e:
        log.warning("K线失败 %s: %s", code, e)
        return None
    if len(bars) < 20:
        return None
    bar_dicts = bars_to_dicts(bars)
    ind = compute_all(bar_dicts)
    mf = compute_multi_factor(bar_dicts, cfg)
    hits = run_all_strategies(bar_dicts, cfg)
    latest = ind.get("latest") or {}
    composite = mf.get("composite_score", 0)
    min_composite = float(cfg.get("min_composite_score", 0))
    pattern_sel = load_pattern_selection()
    pat = detect_patterns(
        bar_dicts,
        signal_filter=pattern_sel.get("signal_filter", cfg.get("pattern_signal_filter", "all")),
        lookback=int(pattern_sel.get("lookback_days", cfg.get("pattern_lookback", 3))),
    )
    return {
        "code": code,
        "name": stock.get("name", code),
        "market": stock.get("market", ""),
        "latest": latest,
        "multi_factor": mf,
        "strategies": hits,
        "candlestick_patterns": pat,
        "pattern_hits": pat.get("hits", []),
        "strategy_count": len(hits),
        "pattern_count": len(pat.get("hits", [])),
        "top_score": max(composite, hits[0]["score"] if hits else 0),
        "composite_score": composite,
        "qualified": composite >= min_composite or len(hits) > 0 or len(pat.get("hits", [])) > 0,
    }


def run_scan(snapshot: dict | None = None, fast: bool = False) -> dict[str, Any]:
    cfg = scanner_config()
    watchlist = load_watchlist()
    snap_path = path_from_config("market_snapshot", "data/market_snapshot.json")
    if snapshot is None and snap_path.exists():
        snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    snapshot = snapshot or {}

    universe: list[dict[str, str]] = []
    seen: set[str] = set()
    for s in watchlist + ([] if fast else stocks_from_snapshot(snapshot)):
        code = str(s.get("code", "")).zfill(6)
        if not code or code in seen:
            continue
        seen.add(code)
        universe.append({**s, "code": code})

    results: list[dict] = []
    for i, stock in enumerate(universe):
        if i > 0:
            time.sleep(0.35)
        row = analyze_stock(stock, cfg)
        if row:
            results.append(row)
        log.info("扫描 %s %s → %s 策略命中", stock.get("code"), stock.get("name"), row["strategy_count"] if row else 0)

    results.sort(
        key=lambda r: (r.get("composite_score", 0), r.get("strategy_count", 0)),
        reverse=True,
    )
    picks = [
        r for r in results
        if r.get("qualified") and (r.get("composite_score", 0) >= float(cfg.get("min_composite_score", 62)) or r.get("strategy_count", 0) > 0)
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_date": snapshot.get("date"),
        "universe_size": len(universe),
        "scan_count": len(results),
        "pick_count": len(picks),
        "picks": picks,
        "all_results": results,
    }
    out = path_from_config("scan_results", "output/scan_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("扫描完成: %s 只，命中 %s 只", len(results), len(picks))
    return payload


def main() -> dict[str, Any]:
    import sys
    return run_scan(fast="--fast" in sys.argv)


if __name__ == "__main__":
    main()
