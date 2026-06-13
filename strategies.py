#!/usr/bin/env python3
"""选股策略 + 多因子融合信号。"""

from __future__ import annotations

from typing import Any, Callable

from app_config import factors_config, strategies_config
from factor_model import _is_limit_up, _pct_change, compute_multi_factor
from indicators import compute_all, kdj, macd, sma

StrategyFn = Callable[[list[dict[str, Any]], dict[str, Any]], dict[str, Any] | None]

STRATEGY_NAMES = {
    "volume_breakout": "放量上涨",
    "ma_bullish": "均线多头",
    "macd_golden_cross": "MACD金叉",
    "kdj_oversold": "KDJ超卖反弹",
    "platform_breakout": "突破平台",
    "limit_up_pullback": "涨停回调",
    "high_momentum": "高动能",
    "multi_factor": "多因子共振",
}


def _merged_cfg(cfg: dict) -> dict:
    return {**strategies_config(), **factors_config(), **cfg}


def _last_n(bars: list[dict], n: int) -> list[dict]:
    return bars[-n:] if len(bars) >= n else bars


def volume_breakout(bars: list[dict], cfg: dict) -> dict | None:
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
        "name": STRATEGY_NAMES["volume_breakout"],
        "score": min(100, int((latest.get("volume_ratio") or 1) * 30 + latest["change_pct"] * 5)),
        "reason": f"成交额 {latest['amount_yi']} 亿，量比 {latest.get('volume_ratio', 0):.2f}，涨幅 {latest['change_pct']:.2f}%",
    }


def ma_bullish(bars: list[dict], _cfg: dict) -> dict | None:
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
        "name": STRATEGY_NAMES["ma_bullish"],
        "score": min(95, int(60 + spread)),
        "reason": f"MA5/10/20/30 多头排列，价差 {spread:.1f}%",
    }


def macd_golden_cross(bars: list[dict], _cfg: dict) -> dict | None:
    if len(bars) < 35:
        return None
    closes = [float(b["close"]) for b in bars]
    m = macd(closes)
    i = len(closes) - 1
    if i < 1 or m["dif"][i] is None or m["dea"][i] is None:
        return None
    if not (m["dif"][i - 1] <= m["dea"][i - 1] and m["dif"][i] > m["dea"][i]):
        return None
    return {
        "strategy": "macd_golden_cross",
        "name": STRATEGY_NAMES["macd_golden_cross"],
        "score": 78,
        "reason": f"DIF {m['dif'][i]:.3f} 上穿 DEA {m['dea'][i]:.3f}",
    }


def kdj_oversold_bounce(bars: list[dict], _cfg: dict) -> dict | None:
    if len(bars) < 15:
        return None
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
        "name": STRATEGY_NAMES["kdj_oversold"],
        "score": int(70 + (25 - kd["k"][i])),
        "reason": f"K={kd['k'][i]:.1f} 低位金叉",
    }


def platform_breakout(bars: list[dict], _cfg: dict) -> dict | None:
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
        "name": STRATEGY_NAMES["platform_breakout"],
        "score": 82,
        "reason": "60日平台整理后放量突破均线",
    }


def limit_up_pullback(bars: list[dict], cfg: dict) -> dict | None:
    """涨停回调：近 N 日有涨停，缩量回踩关键均线不破。"""
    cfg = _merged_cfg(cfg)
    mf = compute_multi_factor(bars, cfg)
    pb = mf["factors"].get("pullback", 0)
    pb_d = mf["factor_details"].get("pullback", {})
    if pb < 55 or not pb_d.get("has_limit_up"):
        return None
    if not pb_d.get("support_hold"):
        return None
    score = int(pb + mf["factors"].get("trend", 0) * 0.15)
    return {
        "strategy": "limit_up_pullback",
        "name": STRATEGY_NAMES["limit_up_pullback"],
        "score": min(98, score),
        "reason": (
            f"涨停后 {pb_d.get('days_since_limit', '?')} 日回调 {pb_d.get('pullback_pct', 0)}%，"
            f"{'缩量' if pb_d.get('shrink_volume') else '整理'}回踩支撑"
        ),
        "factor_scores": mf["factors"],
    }


def high_momentum(bars: list[dict], cfg: dict) -> dict | None:
    """高动能：短中期涨幅强 + 趋势向上 + 贴近阶段高点。"""
    cfg = _merged_cfg(cfg)
    if len(bars) < 25:
        return None
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    i = len(closes) - 1

    ret5 = _pct_change(closes, 5) or 0
    ret10 = _pct_change(closes, 10) or 0
    min5 = float(cfg.get("momentum_ret_5d", 6.0))
    min10 = float(cfg.get("momentum_ret_10d", 10.0))
    if ret5 < min5 or ret10 < min10:
        return None

    ma5, ma10, ma20 = sma(closes, 5)[i], sma(closes, 10)[i], sma(closes, 20)[i]
    if None in (ma5, ma10, ma20) or not (ma5 > ma10 > ma20):
        return None

    high20 = max(highs[-20:])
    if high20 <= 0 or closes[i] < high20 * 0.95:
        return None

    m = macd(closes)
    if m["hist"][i] is None or float(m["hist"][i]) <= 0:
        return None

    mf = compute_multi_factor(bars, cfg)
    mom = mf["factors"].get("momentum", 0)
    if mom < 60:
        return None

    score = int(mom * 0.6 + mf["factors"].get("trend", 0) * 0.25 + mf["factors"].get("volume", 0) * 0.15)
    return {
        "strategy": "high_momentum",
        "name": STRATEGY_NAMES["high_momentum"],
        "score": min(99, score),
        "reason": f"5日 +{ret5:.1f}% / 10日 +{ret10:.1f}%，贴近20日高点，动能 {mom:.0f}",
        "factor_scores": mf["factors"],
    }


def multi_factor_signal(bars: list[dict], cfg: dict) -> dict | None:
    """多因子共振：综合分达标且多因子同时活跃。"""
    cfg = _merged_cfg(cfg)
    mf = compute_multi_factor(bars, cfg)
    min_score = float(cfg.get("composite_min_score", 68))
    min_active = int(cfg.get("min_active_factors", 3))
    if mf["composite_score"] < min_score:
        return None
    if mf["active_factors"] < min_active:
        return None

    top = mf["top_factors"]
    return {
        "strategy": "multi_factor",
        "name": STRATEGY_NAMES["multi_factor"],
        "score": int(mf["composite_score"]),
        "reason": f"综合 {mf['composite_score']} 分，共振因子 {', '.join(top)}，强度 {mf['signal_strength']}",
        "factor_scores": mf["factors"],
        "composite_score": mf["composite_score"],
    }


STRATEGIES: list[tuple[str, StrategyFn]] = [
    ("multi_factor", multi_factor_signal),
    ("limit_up_pullback", limit_up_pullback),
    ("high_momentum", high_momentum),
    ("volume_breakout", volume_breakout),
    ("ma_bullish", ma_bullish),
    ("macd_golden_cross", macd_golden_cross),
    ("kdj_oversold", kdj_oversold_bounce),
    ("platform_breakout", platform_breakout),
]


def run_all_strategies(bars: list[dict], cfg: dict) -> list[dict]:
    cfg = _merged_cfg(cfg)
    hits: list[dict] = []
    seen: set[str] = set()
    for key, fn in STRATEGIES:
        hit = fn(bars, cfg)
        if hit and key not in seen:
            seen.add(key)
            hits.append(hit)
    hits.sort(key=lambda x: x.get("score", 0), reverse=True)
    return hits
