#!/usr/bin/env python3
"""选股策略（参考 InStock 内置策略子集，纯规则实现）。"""

from __future__ import annotations

from typing import Any, Callable

from indicators import compute_all, sma


StrategyFn = Callable[[list[dict[str, Any]], dict[str, Any]], dict[str, Any] | None]


def _last_n(bars: list[dict], n: int) -> list[dict]:
    return bars[-n:] if len(bars) >= n else bars


def volume_breakout(bars: list[dict], cfg: dict) -> dict | None:
    """放量上涨：成交额 >= min_amount，量比 >= volume_ratio_min，收涨。"""
    if len(bars) < 6:
        return None
    ind = compute_all(bars)
    latest = ind["latest"]
    min_yi = float(cfg.get("min_amount_yi", 1.0))
    vol_ratio_min = float(cfg.get("volume_ratio_min", 1.5))
    if latest["amount_yi"] < min_yi:
        return None
    if (latest.get("volume_ratio") or 0) < vol_ratio_min:
        return None
    if latest["change_pct"] is None or latest["change_pct"] <= 0:
        return None
    return {
        "strategy": "volume_breakout",
        "name": "放量上涨",
        "score": min(100, int((latest.get("volume_ratio") or 1) * 30 + latest["change_pct"] * 5)),
        "reason": f"成交额 {latest['amount_yi']} 亿，量比 {latest.get('volume_ratio', 0):.2f}，涨幅 {latest['change_pct']:.2f}%",
    }


def ma_bullish(bars: list[dict], _cfg: dict) -> dict | None:
    """均线多头：MA5 > MA10 > MA20 > MA30 且收盘在 MA5 上方。"""
    if len(bars) < 35:
        return None
    closes = [float(b["close"]) for b in bars]
    ma5, ma10, ma20, ma30 = sma(closes, 5), sma(closes, 10), sma(closes, 20), sma(closes, 30)
    i = len(closes) - 1
    if None in (ma5[i], ma10[i], ma20[i], ma30[i]):
        return None
    if not (ma5[i] > ma10[i] > ma20[i] > ma30[i] and closes[i] > ma5[i]):
        return None
    spread = (ma5[i] - ma30[i]) / ma30[i] * 100
    return {
        "strategy": "ma_bullish",
        "name": "均线多头",
        "score": min(95, int(60 + spread)),
        "reason": f"MA5/10/20/30 多头排列，价差 {spread:.1f}%",
    }


def macd_golden_cross(bars: list[dict], _cfg: dict) -> dict | None:
    """MACD 金叉：DIF 上穿 DEA。"""
    if len(bars) < 35:
        return None
    ind = compute_all(bars)
    from indicators import macd

    closes = [float(b["close"]) for b in bars]
    m = macd(closes)
    i = len(closes) - 1
    if i < 1 or m["dif"][i] is None or m["dea"][i] is None:
        return None
    if not (m["dif"][i - 1] <= m["dea"][i - 1] and m["dif"][i] > m["dea"][i]):
        return None
    return {
        "strategy": "macd_golden_cross",
        "name": "MACD金叉",
        "score": 78,
        "reason": f"DIF {m['dif'][i]:.3f} 上穿 DEA {m['dea'][i]:.3f}",
    }


def kdj_oversold_bounce(bars: list[dict], _cfg: dict) -> dict | None:
    """KDJ 超卖反弹：K<20 且当日 K 上穿 D。"""
    if len(bars) < 15:
        return None
    from indicators import kdj

    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    kd = kdj(highs, lows, closes)
    i = len(closes) - 1
    if i < 1 or kd["k"][i] is None:
        return None
    if kd["k"][i] >= 25:
        return None
    if not (kd["k"][i - 1] <= kd["d"][i - 1] and kd["k"][i] > kd["d"][i]):
        return None
    return {
        "strategy": "kdj_oversold",
        "name": "KDJ超卖反弹",
        "score": int(70 + (25 - kd["k"][i])),
        "reason": f"K={kd['k'][i]:.1f} 低位金叉",
    }


def platform_breakout(bars: list[dict], _cfg: dict) -> dict | None:
    """突破平台：60 日内震荡后放量突破。"""
    if len(bars) < 65:
        return None
    window = _last_n(bars, 60)
    closes = [float(b["close"]) for b in window]
    ma60 = sma([float(b["close"]) for b in bars], 60)
    i = len(bars) - 1
    if ma60[i] is None:
        return None
    prior = closes[:-1]
    if not prior:
        return None
    dev = [(c - ma60[i]) / ma60[i] for c in prior]
    if any(d < -0.05 or d > 0.20 for d in dev):
        return None
    last = bars[-1]
    if float(last["close"]) < ma60[i] or float(last["close"]) < float(last["open"]):
        return None
    ind = compute_all(bars)
    if (ind["latest"].get("volume_ratio") or 0) < 1.8:
        return None
    return {
        "strategy": "platform_breakout",
        "name": "突破平台",
        "score": 82,
        "reason": "60日平台整理后放量突破均线",
    }


STRATEGIES: list[tuple[str, StrategyFn]] = [
    ("volume_breakout", volume_breakout),
    ("ma_bullish", ma_bullish),
    ("macd_golden_cross", macd_golden_cross),
    ("kdj_oversold", kdj_oversold_bounce),
    ("platform_breakout", platform_breakout),
]


def run_all_strategies(bars: list[dict], cfg: dict) -> list[dict]:
    hits: list[dict] = []
    for _key, fn in STRATEGIES:
        hit = fn(bars, cfg)
        if hit:
            hits.append(hit)
    hits.sort(key=lambda x: x.get("score", 0), reverse=True)
    return hits
