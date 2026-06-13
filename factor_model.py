#!/usr/bin/env python3
"""多因子量化评分引擎：动能、量能、趋势、回调质量、反转共振。"""

from __future__ import annotations

from typing import Any

from app_config import factors_config, strategies_config
from indicators import boll, kdj, macd, rsi, sma


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _pct_change(closes: list[float], days: int) -> float | None:
    if len(closes) <= days:
        return None
    base = closes[-days - 1]
    if base <= 0:
        return None
    return (closes[-1] - base) / base * 100


def _is_limit_up(bar: dict, threshold: float) -> bool:
    chg = bar.get("change_pct")
    if chg is not None and float(chg) >= threshold:
        return True
    o, h, c = float(bar["open"]), float(bar["high"]), float(bar["close"])
    if o <= 0:
        return False
    intraday = (c - o) / o * 100
    return intraday >= threshold - 0.3 and c >= h * 0.998


def _series(bars: list[dict]) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    volumes = [float(b["volume"]) for b in bars]
    amounts = [float(b["amount"]) for b in bars]
    return closes, highs, lows, volumes, amounts


def score_momentum(bars: list[dict], cfg: dict) -> tuple[float, dict]:
    if len(bars) < 25:
        return 0.0, {}
    closes, highs, _, volumes, _ = _series(bars)
    i = len(closes) - 1
    ret5 = _pct_change(closes, 5) or 0
    ret10 = _pct_change(closes, 10) or 0
    ret20 = _pct_change(closes, 20) or 0
    win_high = max(highs[-20:])
    win_low = min(closes[-20:])
    pos = (closes[i] - win_low) / (win_high - win_low) * 100 if win_high > win_low else 50

    m = macd(closes)
    hist = m["hist"]
    hist_slope = 0.0
    if i >= 2 and hist[i] is not None and hist[i - 1] is not None:
        hist_slope = float(hist[i]) - float(hist[i - 1])

    ma20 = sma(closes, 20)[i]
    rs_ma = ((closes[i] - ma20) / ma20 * 100) if ma20 else 0

    mom5 = _clamp(ret5 * 4, 0, 100)
    mom10 = _clamp(ret10 * 2.5, 0, 100)
    pos_score = _clamp(pos, 0, 100)
    hist_score = _clamp(50 + hist_slope * 80, 0, 100)
    rs_score = _clamp(50 + rs_ma * 5, 0, 100)

    score = mom5 * 0.28 + mom10 * 0.22 + pos_score * 0.22 + hist_score * 0.14 + rs_score * 0.14
    detail = {
        "ret_5d": round(ret5, 2),
        "ret_10d": round(ret10, 2),
        "ret_20d": round(ret20, 2),
        "high_position": round(pos, 1),
        "macd_hist_slope": round(hist_slope, 4),
    }
    return round(score, 1), detail


def score_volume(bars: list[dict], cfg: dict) -> tuple[float, dict]:
    if len(bars) < 10:
        return 0.0, {}
    _, _, _, volumes, amounts = _series(bars)
    i = len(volumes) - 1
    vol_ma5 = sma(volumes, 5)
    vol_ma10 = sma(volumes, 10)
    ratio5 = (volumes[i] / vol_ma5[i]) if vol_ma5[i] else 1
    ratio10 = (volumes[i] / vol_ma10[i]) if vol_ma10[i] else 1
    amount_yi = amounts[i] / 1e8

    vol_score = _clamp((ratio5 - 0.8) * 35, 0, 100)
    amt_score = _clamp(amount_yi * 12, 0, 100)
    trend_vol = 0
    if i >= 3 and vol_ma5[i] and vol_ma5[i - 2]:
        trend_vol = (vol_ma5[i] - vol_ma5[i - 2]) / vol_ma5[i - 2] * 100
    trend_score = _clamp(50 + trend_vol * 3, 0, 100)

    score = vol_score * 0.45 + amt_score * 0.35 + trend_score * 0.20
    return round(score, 1), {
        "volume_ratio": round(ratio5, 2),
        "volume_ratio_10": round(ratio10, 2),
        "amount_yi": round(amount_yi, 2),
    }


def score_trend(bars: list[dict], _cfg: dict) -> tuple[float, dict]:
    if len(bars) < 35:
        return 0.0, {}
    closes, _, _, _, _ = _series(bars)
    i = len(closes) - 1
    ma5, ma10, ma20, ma30 = sma(closes, 5)[i], sma(closes, 10)[i], sma(closes, 20)[i], sma(closes, 30)[i]
    if None in (ma5, ma10, ma20, ma30):
        return 0.0, {}

    align = 0
    if ma5 > ma10:
        align += 25
    if ma10 > ma20:
        align += 25
    if ma20 > ma30:
        align += 20
    if closes[i] > ma5:
        align += 15
    if closes[i] > ma20:
        align += 15

    m = macd(closes)
    macd_bonus = 0
    if m["dif"][i] is not None and m["dea"][i] is not None:
        if m["dif"][i] > m["dea"][i]:
            macd_bonus += 12
        if m["dif"][i] > 0:
            macd_bonus += 8

    score = _clamp(align + macd_bonus, 0, 100)
    return round(score, 1), {
        "ma_align": align,
        "above_ma20": closes[i] > ma20,
        "macd_bullish": bool(m["dif"][i] and m["dea"][i] and m["dif"][i] > m["dea"][i]),
    }


def score_pullback(bars: list[dict], cfg: dict) -> tuple[float, dict]:
    """涨停回调质量：有涨停基因 + 缩量回踩 + 支撑有效。"""
    scfg = {**strategies_config(), **cfg}
    lookback = int(scfg.get("limit_up_lookback", 10))
    limit_pct = float(scfg.get("limit_up_pct", 9.5))
    pb_min = float(scfg.get("pullback_min_pct", 3.0))
    pb_max = float(scfg.get("pullback_max_pct", 12.0))
    shrink = float(scfg.get("pullback_shrink_vol", 0.85))

    if len(bars) < lookback + 5:
        return 0.0, {}

    closes, highs, lows, volumes, _ = _series(bars)
    i = len(closes) - 1
    window = bars[-lookback - 1 : -1] if len(bars) > lookback else bars[:-1]

    limit_idx = None
    limit_vol = None
    for j, bar in enumerate(window):
        if _is_limit_up(bar, limit_pct):
            limit_idx = j
            limit_vol = float(bar["volume"])

    if limit_idx is None:
        return 0.0, {"has_limit_up": False}

    recent_high = max(highs[-6:])
    if recent_high <= 0:
        return 0.0, {}
    pullback_pct = (recent_high - closes[i]) / recent_high * 100
    if pullback_pct < pb_min or pullback_pct > pb_max:
        return 0.0, {"has_limit_up": True, "pullback_pct": round(pullback_pct, 2)}

    vol_ok = limit_vol and volumes[i] <= limit_vol * shrink
    ma10 = sma(closes, 10)[i]
    ma20 = sma(closes, 20)[i]
    boll_mid = boll(closes)["mid"][i]
    support = closes[i] >= min(x for x in [ma10, ma20, boll_mid] if x) * 0.98 if any([ma10, ma20, boll_mid]) else True

    depth_score = _clamp(100 - abs(pullback_pct - 6) * 8, 0, 100)
    vol_score = 80 if vol_ok else 35
    sup_score = 85 if support else 30
    gene_score = 70 + min(30, (lookback - limit_idx) * 3)

    score = depth_score * 0.35 + vol_score * 0.30 + sup_score * 0.20 + gene_score * 0.15
    return round(score, 1), {
        "has_limit_up": True,
        "pullback_pct": round(pullback_pct, 2),
        "shrink_volume": vol_ok,
        "support_hold": support,
        "days_since_limit": len(window) - limit_idx,
    }


def score_reversal(bars: list[dict], _cfg: dict) -> tuple[float, dict]:
    if len(bars) < 15:
        return 0.0, {}
    closes, highs, lows, _, _ = _series(bars)
    kd = kdj(highs, lows, closes)
    rs = rsi(closes, 6)
    i = len(closes) - 1
    k, r = kd["k"][i], rs[i]
    if k is None or r is None:
        return 0.0, {}

    # 动能策略偏好 KDJ/RSI 中性偏强区间；超卖反弹另行加分
    sweet = 100 - (abs(k - 52) * 1.2 + abs(r - 55) * 1.0)
    oversold_bonus = 0
    if k < 28 and r < 35:
        oversold_bonus = 20
    if i >= 1 and kd["k"][i - 1] is not None and kd["d"][i - 1] is not None:
        if kd["k"][i - 1] <= kd["d"][i - 1] and k > kd["d"][i]:
            oversold_bonus += 15

    score = _clamp(sweet + oversold_bonus, 0, 100)
    return round(score, 1), {"kdj_k": round(k, 1), "rsi6": round(r, 1)}


def compute_multi_factor(bars: list[dict], cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or {}
    fcfg = factors_config()
    weights = dict(fcfg.get("weights") or {})
    default_w = {
        "momentum": 0.28,
        "volume": 0.18,
        "trend": 0.22,
        "pullback": 0.17,
        "reversal": 0.15,
    }
    for k, v in default_w.items():
        weights.setdefault(k, v)

    momentum, mom_d = score_momentum(bars, cfg)
    volume, vol_d = score_volume(bars, cfg)
    trend, tr_d = score_trend(bars, cfg)
    pullback, pb_d = score_pullback(bars, cfg)
    reversal, rev_d = score_reversal(bars, cfg)

    factors = {
        "momentum": momentum,
        "volume": volume,
        "trend": trend,
        "pullback": pullback,
        "reversal": reversal,
    }
    details = {"momentum": mom_d, "volume": vol_d, "trend": tr_d, "pullback": pb_d, "reversal": rev_d}

    composite = sum(factors[k] * weights.get(k, 0) for k in factors)
    synergy_thr = float(fcfg.get("synergy_threshold", 55))
    synergy_bonus = float(fcfg.get("synergy_bonus", 8))
    active = sum(1 for v in factors.values() if v >= synergy_thr)
    if active >= int(fcfg.get("min_active_factors", 3)):
        composite += synergy_bonus * min(active - 2, 3)

    # 涨停回调 + 高动能共振额外加分
    if pullback >= 60 and momentum >= 60:
        composite += 5
    if trend >= 65 and volume >= 60:
        composite += 4

    composite = round(_clamp(composite), 1)
    ranked = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    return {
        "composite_score": composite,
        "factors": factors,
        "factor_details": details,
        "active_factors": active,
        "top_factors": [k for k, _ in ranked[:3]],
        "signal_strength": (
            "强" if composite >= 75 else "中" if composite >= 62 else "弱"
        ),
    }


def estimate_factors_from_latest(latest: dict[str, Any]) -> dict[str, Any]:
    """无 K 线历史时，用 latest 指标近似估算五维因子（供看板展示）。"""
    if not latest:
        return {"composite_score": 0, "factors": {}, "signal_strength": "弱", "estimated": True}

    fcfg = factors_config()
    weights = dict(fcfg.get("weights") or {})
    default_w = {"momentum": 0.28, "volume": 0.18, "trend": 0.22, "pullback": 0.17, "reversal": 0.15}
    for k, v in default_w.items():
        weights.setdefault(k, v)

    change = float(latest.get("change_pct") or 0)
    vol_ratio = float(latest.get("volume_ratio") or 1)
    amount_yi = float(latest.get("amount_yi") or 0)
    rsi6 = float(latest.get("rsi6") or 50)
    kdj_k = float(latest.get("kdj_k") or 50)

    momentum = _clamp(abs(change) * 6 + rsi6 * 0.35, 0, 100)
    volume = _clamp((vol_ratio - 0.5) * 35 + amount_yi * 4, 0, 100)

    trend = 25.0
    ma5, ma10, ma20 = latest.get("ma5"), latest.get("ma10"), latest.get("ma20")
    close = float(latest.get("close") or 0)
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            trend += 35
        if close > ma5:
            trend += 15
        if close > ma20:
            trend += 10
    dif, dea = latest.get("macd_dif"), latest.get("macd_dea")
    if dif is not None and dea is not None and dif > dea:
        trend += 15
    trend = _clamp(trend, 0, 100)

    pullback = 0.0
    if change >= 9.5:
        pullback = _clamp(45 + vol_ratio * 8, 0, 70)
    elif -4 <= change <= 2:
        pullback = _clamp(50 + (2 - abs(change)) * 10, 0, 85)

    reversal = _clamp(100 - abs(kdj_k - 52) * 1.2 - abs(rsi6 - 55) * 1.0, 0, 100)

    factors = {
        "momentum": round(momentum, 1),
        "volume": round(volume, 1),
        "trend": round(trend, 1),
        "pullback": round(pullback, 1),
        "reversal": round(reversal, 1),
    }
    composite = round(sum(factors[k] * weights.get(k, 0) for k in factors), 1)
    active = sum(1 for v in factors.values() if v >= 55)
    ranked = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    return {
        "composite_score": composite,
        "factors": factors,
        "active_factors": active,
        "top_factors": [k for k, _ in ranked[:3]],
        "signal_strength": "强" if composite >= 75 else "中" if composite >= 62 else "弱",
        "estimated": True,
    }
