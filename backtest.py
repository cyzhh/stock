#!/usr/bin/env python3
"""策略回测：信号日买入，止盈止损 + 移动止损，统计胜率与盈亏比。"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from app_config import backtest_config, path_from_config, scanner_config
from factor_model import compute_multi_factor
from kline_fetcher import bars_to_dicts, fetch_klines
from sq_logging import setup_logging
from strategies import STRATEGIES, STRATEGY_NAMES

log = setup_logging("stock_quant.backtest")


def _simulate_trade(bars: list[dict], entry_idx: int, cfg: dict) -> dict | None:
    if entry_idx >= len(bars) - 1:
        return None
    entry = float(bars[entry_idx]["close"])
    hold_days = int(cfg.get("hold_days", 5))
    stop = float(cfg.get("stop_loss_pct", 0.06))
    take = float(cfg.get("take_profit_pct", 0.12))
    trail = float(cfg.get("trailing_stop_pct", 0.05))

    peak = entry
    exit_idx = None
    exit_reason = "hold_expire"
    for j in range(entry_idx + 1, min(entry_idx + hold_days + 1, len(bars))):
        px = float(bars[j]["close"])
        peak = max(peak, px)
        ret = (px - entry) / entry
        trail_stop = (px - peak) / peak if peak > 0 else 0

        if ret <= -stop:
            exit_idx = j
            exit_reason = "stop_loss"
            break
        if ret >= take:
            exit_idx = j
            exit_reason = "take_profit"
            break
        if peak > entry * 1.04 and trail_stop <= -trail:
            exit_idx = j
            exit_reason = "trailing_stop"
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


def _profit_factor(trades: list[dict]) -> float:
    wins = [t["return_pct"] for t in trades if t["return_pct"] > 0]
    losses = [t["return_pct"] for t in trades if t["return_pct"] <= 0]
    if not losses:
        return round(sum(wins) / len(wins), 2) if wins else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses))
    return round(avg_win / avg_loss, 2) if avg_loss else 0.0


def backtest_stock(code: str, market: str, strategy_key: str, cfg: dict) -> dict[str, Any]:
    fn = next((f for k, f in STRATEGIES if k == strategy_key), None)
    if not fn:
        raise ValueError(f"未知策略: {strategy_key}")
    bars = bars_to_dicts(fetch_klines(code, market, days=250))
    trades: list[dict] = []
    cooldown = 0
    min_composite = float(cfg.get("min_composite_score", 0))

    for i in range(30, len(bars) - 5):
        if cooldown > 0:
            cooldown -= 1
            continue
        window = bars[: i + 1]
        if min_composite > 0 and strategy_key in ("multi_factor", "limit_up_pullback", "high_momentum"):
            mf = compute_multi_factor(window, cfg)
            if mf["composite_score"] < min_composite:
                continue
        hit = fn(window, cfg)
        if not hit:
            continue
        trade = _simulate_trade(bars, i, cfg)
        if trade:
            trade["strategy"] = strategy_key
            trade["strategy_name"] = hit.get("name", strategy_key)
            trade["signal_score"] = hit.get("score", 0)
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
        "profit_factor": _profit_factor(trades),
        "trade_list": trades[-10:],
    }


def run_backtest(scan_data: dict | None = None) -> dict[str, Any]:
    cfg = {**scanner_config(), **backtest_config()}
    scan_path = path_from_config("scan_results", "output/scan_results.json")
    if scan_data is None and scan_path.exists():
        scan_data = json.loads(scan_path.read_text(encoding="utf-8"))
    scan_data = scan_data or {}
    picks = (scan_data.get("picks") or [])[:8]
    if not picks:
        picks = [{"code": "600519", "name": "贵州茅台", "market": "sh"}]

    strategy_keys = [k for k, _ in STRATEGIES]
    stock_results: list[dict] = []
    strategy_agg: dict[str, dict] = {
        k: {"trades": 0, "wins": 0, "returns": [], "profit_factors": []} for k, _ in STRATEGIES
    }

    for pick in picks:
        code = pick["code"]
        market = pick.get("market") or ("sh" if code.startswith("6") else "sz")
        time.sleep(0.25)
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
            agg["profit_factors"].append(bt["profit_factor"])

    summary = []
    for key, _ in STRATEGIES:
        a = strategy_agg[key]
        if a["trades"] == 0:
            continue
        pf = round(sum(a["profit_factors"]) / len(a["profit_factors"]), 2) if a["profit_factors"] else 0
        wr = round(a["wins"] / a["trades"] * 100, 1)
        summary.append({
            "strategy": key,
            "name": STRATEGY_NAMES.get(key, key),
            "trades": a["trades"],
            "win_rate": wr,
            "avg_return_pct": round(sum(a["returns"]) / len(a["returns"]), 2) if a["returns"] else 0,
            "profit_factor": pf,
            "score": round(wr * 0.5 + pf * 20 + (sum(a["returns"]) / len(a["returns"]) if a["returns"] else 0) * 2, 1),
        })
    summary.sort(key=lambda x: x["score"], reverse=True)

    all_trades = sum(s["trades"] for s in summary)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": cfg,
        "summary": summary,
        "stock_results": stock_results,
        "overall": {
            "stocks_tested": len(picks),
            "total_trades": all_trades,
            "best_strategy": summary[0] if summary else None,
            "best_win_rate": max(summary, key=lambda x: x["win_rate"]) if summary else None,
            "best_profit_factor": max(summary, key=lambda x: x["profit_factor"]) if summary else None,
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
