#!/usr/bin/env python3
"""策略回测：信号日买入，持有 N 日或止盈止损。"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from app_config import backtest_config, path_from_config
from kline_fetcher import bars_to_dicts, fetch_klines
from sq_logging import setup_logging
from strategies import STRATEGIES

log = setup_logging("stock_quant.backtest")


def _simulate_trade(bars: list[dict], entry_idx: int, cfg: dict) -> dict | None:
    if entry_idx >= len(bars) - 1:
        return None
    entry = float(bars[entry_idx]["close"])
    hold_days = int(cfg.get("hold_days", 5))
    stop = float(cfg.get("stop_loss_pct", 0.08))
    take = float(cfg.get("take_profit_pct", 0.15))
    exit_idx = None
    exit_reason = "hold_expire"
    for j in range(entry_idx + 1, min(entry_idx + hold_days + 1, len(bars))):
        px = float(bars[j]["close"])
        ret = (px - entry) / entry
        if ret <= -stop:
            exit_idx = j
            exit_reason = "stop_loss"
            break
        if ret >= take:
            exit_idx = j
            exit_reason = "take_profit"
            break
    if exit_idx is None:
        exit_idx = min(entry_idx + hold_days, len(bars) - 1)
    exit_px = float(bars[exit_idx]["close"])
    ret_pct = round((exit_px - entry) / entry * 100, 2)
    return {
        "entry_date": bars[entry_idx]["date"],
        "exit_date": bars[exit_idx]["date"],
        "entry_price": entry,
        "exit_price": exit_px,
        "return_pct": ret_pct,
        "win": ret_pct > 0,
        "exit_reason": exit_reason,
        "hold_days": exit_idx - entry_idx,
    }


def backtest_stock(code: str, market: str, strategy_key: str, cfg: dict) -> dict[str, Any]:
    fn = next((f for k, f in STRATEGIES if k == strategy_key), None)
    if not fn:
        raise ValueError(f"未知策略: {strategy_key}")
    bars = bars_to_dicts(fetch_klines(code, market, days=250))
    trades: list[dict] = []
    cooldown = 0
    for i in range(30, len(bars) - 5):
        if cooldown > 0:
            cooldown -= 1
            continue
        window = bars[: i + 1]
        hit = fn(window, cfg)
        if not hit:
            continue
        trade = _simulate_trade(bars, i, cfg)
        if trade:
            trade["strategy"] = strategy_key
            trade["strategy_name"] = hit.get("name", strategy_key)
            trades.append(trade)
            cooldown = int(cfg.get("hold_days", 5))
    wins = sum(1 for t in trades if t["win"])
    total = len(trades)
    avg_ret = round(sum(t["return_pct"] for t in trades) / total, 2) if total else 0.0
    return {
        "code": code,
        "strategy": strategy_key,
        "trades": total,
        "wins": wins,
        "win_rate": round(wins / total * 100, 1) if total else 0.0,
        "avg_return_pct": avg_ret,
        "trade_list": trades[-10:],
    }


def run_backtest(scan_data: dict | None = None) -> dict[str, Any]:
    from app_config import scanner_config

    cfg = {**scanner_config(), **backtest_config()}
    scan_path = path_from_config("scan_results", "output/scan_results.json")
    if scan_data is None and scan_path.exists():
        scan_data = json.loads(scan_path.read_text(encoding="utf-8"))
    scan_data = scan_data or {}
    picks = (scan_data.get("picks") or [])[:5]
    if not picks:
        picks = [{"code": "600519", "name": "贵州茅台", "market": "sh"}]

    strategy_keys = [k for k, _ in STRATEGIES]
    stock_results: list[dict] = []
    strategy_agg: dict[str, dict] = {k: {"trades": 0, "wins": 0, "returns": []} for k, _ in STRATEGIES}

    for pick in picks:
        code = pick["code"]
        market = pick.get("market") or ("sh" if code.startswith("6") else "sz")
        time.sleep(0.2)
        for sk in strategy_keys:
            try:
                bt = backtest_stock(code, market, sk, cfg)
            except Exception as e:
                log.warning("回测失败 %s %s: %s", code, sk, e)
                continue
            if bt["trades"] == 0:
                continue
            stock_results.append({**bt, "name": pick.get("name", code)})
            agg = strategy_agg[sk]
            agg["trades"] += bt["trades"]
            agg["wins"] += bt["wins"]
            agg["returns"].append(bt["avg_return_pct"])

    summary = []
    name_map = {
        "volume_breakout": "放量上涨",
        "ma_bullish": "均线多头",
        "macd_golden_cross": "MACD金叉",
        "kdj_oversold": "KDJ超卖反弹",
        "platform_breakout": "突破平台",
    }
    for key, _ in STRATEGIES:
        a = strategy_agg[key]
        if a["trades"] == 0:
            continue
        summary.append({
            "strategy": key,
            "name": name_map.get(key, key),
            "trades": a["trades"],
            "win_rate": round(a["wins"] / a["trades"] * 100, 1),
            "avg_return_pct": round(sum(a["returns"]) / len(a["returns"]), 2) if a["returns"] else 0,
        })
    summary.sort(key=lambda x: x["win_rate"], reverse=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": cfg,
        "summary": summary,
        "stock_results": stock_results,
        "overall": {
            "stocks_tested": len(picks),
            "total_trades": sum(s["trades"] for s in summary),
            "best_strategy": summary[0] if summary else None,
        },
    }
    out = path_from_config("backtest_report", "output/backtest_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("回测完成: %s 条策略汇总", len(summary))
    return report


def main() -> dict[str, Any]:
    return run_backtest()


if __name__ == "__main__":
    main()
