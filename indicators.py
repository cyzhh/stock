#!/usr/bin/env python3
"""技术指标计算（纯 Python，对齐 InStock 常用指标子集）。"""

from __future__ import annotations

from typing import Any


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i - period]
        if i >= period - 1:
            out[i] = s / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or not values:
        return out
    k = 2 / (period + 1)
    prev = sum(values[:period]) / period
    for i in range(period - 1, len(values)):
        if i == period - 1:
            out[i] = prev
        else:
            prev = values[i] * k + prev * (1 - k)
            out[i] = prev
    return out


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, list[float | None]]:
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif[i] = ema_fast[i] - ema_slow[i]
    dif_vals = [d if d is not None else 0.0 for d in dif]
    dea = ema(dif_vals, signal)
    hist: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if dif[i] is not None and dea[i] is not None:
            hist[i] = (dif[i] - dea[i]) * 2
    return {"dif": dif, "dea": dea, "hist": hist}


def kdj(highs: list[float], lows: list[float], closes: list[float], n: int = 9) -> dict[str, list[float | None]]:
    k_list: list[float | None] = [None] * len(closes)
    d_list: list[float | None] = [None] * len(closes)
    j_list: list[float | None] = [None] * len(closes)
    k_prev, d_prev = 50.0, 50.0
    for i in range(len(closes)):
        start = max(0, i - n + 1)
        window_h = max(highs[start : i + 1])
        window_l = min(lows[start : i + 1])
        if window_h == window_l:
            rsv = 50.0
        else:
            rsv = (closes[i] - window_l) / (window_h - window_l) * 100
        k_prev = k_prev * 2 / 3 + rsv / 3
        d_prev = d_prev * 2 / 3 + k_prev / 3
        k_list[i] = k_prev
        d_list[i] = d_prev
        j_list[i] = 3 * k_prev - 2 * d_prev
    return {"k": k_list, "d": d_list, "j": j_list}


def rsi(closes: list[float], period: int = 6) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = 100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, len(closes)):
        g, l = gains[i - 1], losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        out[i] = 100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def boll(closes: list[float], period: int = 20, mult: float = 2.0) -> dict[str, list[float | None]]:
    mid = sma(closes, period)
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if mid[i] is None:
            continue
        start = i - period + 1
        window = closes[start : i + 1]
        mean = mid[i]
        var = sum((x - mean) ** 2 for x in window) / period
        std = var ** 0.5
        upper[i] = mean + mult * std
        lower[i] = mean - mult * std
    return {"mid": mid, "upper": upper, "lower": lower}


def signal_label(indicator: str, value: float | None, extra: dict | None = None) -> str:
    if value is None:
        return "无数据"
    extra = extra or {}
    if indicator == "kdj":
        if value < 20:
            return "超卖"
        if value > 80:
            return "超买"
        return "中性"
    if indicator == "rsi":
        if value < 20:
            return "超卖"
        if value > 80:
            return "超买"
        return "中性"
    if indicator == "macd":
        dif = extra.get("dif")
        dea = extra.get("dea")
        if dif is not None and dea is not None:
            if dif > dea and dif > 0:
                return "金叉偏多"
            if dif < dea and dif < 0:
                return "死叉偏空"
        return "震荡"
    return "—"


def compute_all(bars: list[dict[str, Any]]) -> dict[str, Any]:
    if not bars:
        return {}
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    volumes = [float(b["volume"]) for b in bars]
    amounts = [float(b["amount"]) for b in bars]

    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma30 = sma(closes, 30)
    ma60 = sma(closes, 60)
    macd_vals = macd(closes)
    kdj_vals = kdj(highs, lows, closes)
    rsi6 = rsi(closes, 6)
    rsi12 = rsi(closes, 12)
    boll_vals = boll(closes)
    vol_ma5 = sma(volumes, 5)

    i = len(bars) - 1
    latest = {
        "date": bars[i]["date"],
        "close": closes[i],
        "change_pct": bars[i].get("change_pct"),
        "amount_yi": round(amounts[i] / 1e8, 2),
        "ma5": ma5[i],
        "ma10": ma10[i],
        "ma20": ma20[i],
        "ma30": ma30[i],
        "ma60": ma60[i],
        "macd_dif": macd_vals["dif"][i],
        "macd_dea": macd_vals["dea"][i],
        "macd_hist": macd_vals["hist"][i],
        "kdj_k": kdj_vals["k"][i],
        "kdj_d": kdj_vals["d"][i],
        "kdj_j": kdj_vals["j"][i],
        "rsi6": rsi6[i],
        "rsi12": rsi12[i],
        "boll_upper": boll_vals["upper"][i],
        "boll_mid": boll_vals["mid"][i],
        "boll_lower": boll_vals["lower"][i],
        "volume_ratio": (volumes[i] / vol_ma5[i]) if vol_ma5[i] else None,
    }
    latest["signals"] = {
        "kdj": signal_label("kdj", latest["kdj_k"]),
        "rsi": signal_label("rsi", latest["rsi6"]),
        "macd": signal_label(
            "macd",
            latest["macd_dif"],
            {"dif": latest["macd_dif"], "dea": latest["macd_dea"]},
        ),
    }
    return {"latest": latest, "series_len": len(bars)}
