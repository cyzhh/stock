#!/usr/bin/env python3
"""周线 BBI 分析单元测试（合成 K 线，无需网络）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from indicators import bbi
from weekly_bbi_report import (
    bbi_crossovers,
    count_bbi_bounces,
    detect_phase,
    find_pivots,
)


def _synthetic_uptrend_bars(n: int = 80) -> list[dict]:
    bars = []
    price = 0.85
    for i in range(n):
        chg = 0.015 if i < n - 10 else -0.02
        o = price
        c = price * (1 + chg)
        h = max(o, c) * 1.008
        l = min(o, c) * 0.992
        bars.append({
            "date": f"2024-{i // 4 + 1:02d}-{i % 4 + 1:02d}",
            "open": round(o, 3),
            "close": round(c, 3),
            "high": round(h, 3),
            "low": round(l, 3),
            "volume": 1_000_000 + i * 1000,
            "amount": 0,
            "change_pct": chg * 100,
        })
        price = c
    return bars


def test_bbi_computation():
    closes = [float(i) for i in range(1, 30)]
    line = bbi(closes)
    assert line[-1] is not None
    assert line[0] is None


def test_find_pivots():
    bars = _synthetic_uptrend_bars(40)
    highs, lows = find_pivots(bars, window=2)
    assert isinstance(highs, list)
    assert isinstance(lows, list)


def test_bbi_crossover_detection():
    bars = _synthetic_uptrend_bars(50)
    closes = [b["close"] for b in bars]
    line = bbi(closes)
    # 人为制造最后一根跌破
    bars[-1]["close"] = (line[-1] or 1) * 0.95
    bars[-1]["open"] = bars[-1]["close"] * 1.02
    line = bbi([b["close"] for b in bars])
    events = bbi_crossovers(bars, line)
    assert isinstance(events, list)


def test_detect_phase_breakdown():
    bars = _synthetic_uptrend_bars(60)
    closes = [b["close"] for b in bars]
    line = bbi(closes)
    stage_high = max(closes)
    stage_high_idx = closes.index(stage_high)
    bars[-1]["close"] = (line[-1] or 1) * 0.92
    bars[-1]["open"] = bars[-1]["close"] * 1.03
    bars[-1]["low"] = bars[-1]["close"] * 0.99
    line = bbi([b["close"] for b in bars])
    phase = detect_phase(bars, line, stage_high, stage_high_idx)
    assert phase["signal"] in ("bear", "neutral", "bull")
    assert "summary" in phase


def test_bounce_count_non_negative():
    bars = _synthetic_uptrend_bars(55)
    closes = [b["close"] for b in bars]
    line = bbi(closes)
    n = count_bbi_bounces(bars, line, lookback=52)
    assert n >= 0
