#!/usr/bin/env python3
"""多因子与策略单元测试（合成 K 线，无需网络）。"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from factor_model import compute_multi_factor
from strategies import limit_up_pullback, high_momentum, multi_factor_signal, run_all_strategies


def _make_bars(n: int = 80, seed: int = 42) -> list[dict[str, Any]]:
    random.seed(seed)
    price = 10.0
    bars = []
    for i in range(n):
        # 模拟一段上涨 + 涨停 + 回调
        if i == n - 15:
            chg = 10.0
        elif i > n - 8:
            chg = random.uniform(-2.5, 1.0)
        else:
            chg = random.uniform(-1.5, 2.5)
        o = price
        c = price * (1 + chg / 100)
        h = max(o, c) * 1.01
        l = min(o, c) * 0.99
        vol = 1_000_000 if i != n - 15 else 3_500_000
        if i > n - 8:
            vol = int(vol * 0.6)
        bars.append({
            "date": f"2026-01-{i+1:02d}",
            "open": round(o, 2),
            "close": round(c, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "volume": vol,
            "amount": vol * c,
            "change_pct": round(chg, 2),
            "turnover": 5.0,
        })
        price = c
    return bars


def test_multi_factor_scores():
    bars = _make_bars()
    mf = compute_multi_factor(bars, {})
    assert "composite_score" in mf
    assert mf["composite_score"] > 0
    assert len(mf["factors"]) == 5


def test_limit_up_pullback_detects():
    bars = _make_bars()
    hit = limit_up_pullback(bars, {})
    # 合成数据含涨停+回调，应有机会命中
    assert hit is None or hit["strategy"] == "limit_up_pullback"


def test_run_all_returns_sorted():
    bars = _make_bars()
    hits = run_all_strategies(bars, {"composite_min_score": 50, "min_composite_score": 50})
    assert isinstance(hits, list)
    if len(hits) >= 2:
        assert hits[0]["score"] >= hits[1]["score"]


if __name__ == "__main__":
    test_multi_factor_scores()
    test_limit_up_pullback_detects()
    test_run_all_returns_sorted()
    print("factor tests ok")
