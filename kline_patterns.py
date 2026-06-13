#!/usr/bin/env python3
"""K 线形态识别：优先 TA-Lib（61 种），无依赖时纯 Python 子集。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_config import path_from_config
from pattern_registry import PATTERN_BY_ID, PATTERN_REGISTRY, signal_label
from sq_logging import setup_logging

log = setup_logging("stock_quant.patterns")

try:
    import numpy as np
    import talib

    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


def _ohlc(bars: list[dict]) -> tuple[list[float], list[float], list[float], list[float]]:
    o = [float(b["open"]) for b in bars]
    h = [float(b["high"]) for b in bars]
    l = [float(b["low"]) for b in bars]
    c = [float(b["close"]) for b in bars]
    return o, h, l, c


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _upper(o: float, h: float, c: float) -> float:
    return h - max(o, c)


def _lower(o: float, l: float, c: float) -> float:
    return min(o, c) - l


def _bull(o: float, c: float) -> bool:
    return c >= o


# ── 纯 Python 子集（无 TA-Lib 时） ─────────────────────────────


def _pp_doji(o, h, l, c) -> int:
    rng = h - l
    if rng <= 0:
        return 0
    return 100 if _body(o, c) / rng < 0.1 else 0


def _pp_hammer(o, h, l, c) -> int:
    b, lo, up = _body(o, c), _lower(o, l, c), _upper(o, h, c)
    if b <= 0:
        return 0
    return 100 if lo >= 2 * b and up <= 0.3 * b else 0


def _pp_hanging_man(o, h, l, c) -> int:
    return -_pp_hammer(o, h, l, c) if _pp_hammer(o, h, l, c) else 0


def _pp_shooting_star(o, h, l, c) -> int:
    b, lo, up = _body(o, c), _lower(o, l, c), _upper(o, h, c)
    if b <= 0:
        return 0
    return -100 if up >= 2 * b and lo <= 0.3 * b else 0


def _pp_engulfing(bars: list[dict], i: int) -> int:
    if i < 1:
        return 0
    p, cur = bars[i - 1], bars[i]
    po, pc = float(p["open"]), float(p["close"])
    o, c = float(cur["open"]), float(cur["close"])
    if pc < po and c > o and o <= pc and c >= po:
        return 100
    if pc > po and c < o and o >= pc and c <= po:
        return -100
    return 0


def _pp_morning_star(bars: list[dict], i: int) -> int:
    if i < 2:
        return 0
    a, b, c = bars[i - 2], bars[i - 1], bars[i]
    ao, ac = float(a["open"]), float(a["close"])
    bo, bc = float(b["open"]), float(b["close"])
    co, cc = float(c["open"]), float(c["close"])
    if ac < ao and _body(bo, bc) < _body(ao, ac) * 0.4 and cc > co and cc > (ao + ac) / 2:
        return 100
    return 0


def _pp_evening_star(bars: list[dict], i: int) -> int:
    if i < 2:
        return 0
    a, b, c = bars[i - 2], bars[i - 1], bars[i]
    ao, ac = float(a["open"]), float(a["close"])
    bo, bc = float(b["open"]), float(b["close"])
    co, cc = float(c["open"]), float(c["close"])
    if ac > ao and _body(bo, bc) < _body(ao, ac) * 0.4 and cc < co and cc < (ao + ac) / 2:
        return -100
    return 0


def _pp_three_white_soldiers(bars: list[dict], i: int) -> int:
    if i < 2:
        return 0
    ok = True
    for j in range(i - 2, i + 1):
        o, c = float(bars[j]["open"]), float(bars[j]["close"])
        if c <= o:
            ok = False
    if ok and float(bars[i]["close"]) > float(bars[i - 1]["close"]) > float(bars[i - 2]["close"]):
        return 100
    return 0


def _pp_three_black_crows(bars: list[dict], i: int) -> int:
    if i < 2:
        return 0
    ok = True
    for j in range(i - 2, i + 1):
        o, c = float(bars[j]["open"]), float(bars[j]["close"])
        if c >= o:
            ok = False
    if ok and float(bars[i]["close"]) < float(bars[i - 1]["close"]) < float(bars[i - 2]["close"]):
        return -100
    return 0


def _pp_dark_cloud(bars: list[dict], i: int) -> int:
    if i < 1:
        return 0
    p, c = bars[i - 1], bars[i]
    if float(p["close"]) <= float(p["open"]):
        return 0
    o, cl = float(c["open"]), float(c["close"])
    if o > float(p["close"]) and cl < (float(p["open"]) + float(p["close"])) / 2 and cl > float(p["open"]):
        return -100
    return 0


def _pp_piercing(bars: list[dict], i: int) -> int:
    if i < 1:
        return 0
    p, c = bars[i - 1], bars[i]
    if float(p["close"]) >= float(p["open"]):
        return 0
    o, cl = float(c["open"]), float(c["close"])
    if o < float(p["close"]) and cl > (float(p["open"]) + float(p["close"])) / 2 and cl < float(p["open"]):
        return 100
    return 0


PURE_DETECTORS: dict[str, Any] = {
    "doji": lambda bars, i: _pp_doji(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i]["close"])),
    "hammer": lambda bars, i: _pp_hammer(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i]["close"])),
    "hanging_man": lambda bars, i: _pp_hanging_man(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i]["close"])),
    "shooting_star": lambda bars, i: _pp_shooting_star(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i]["close"])),
    "engulfing": _pp_engulfing,
    "morning_star": _pp_morning_star,
    "evening_star": _pp_evening_star,
    "three_white_soldiers": _pp_three_white_soldiers,
    "three_black_crows": _pp_three_black_crows,
    "dark_cloud_cover": _pp_dark_cloud,
    "piercing": _pp_piercing,
    "inverted_hammer": lambda bars, i: _pp_hammer(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i]["close"])),
    "dragonfly_doji": lambda bars, i: (
        100
        if _pp_doji(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i]["close"]))
        and _lower(float(bars[i]["open"]), float(bars[i]["low"]), float(bars[i]["close"]))
        > 2 * max(_body(float(bars[i]["open"]), float(bars[i]["close"])), 1e-9)
        else 0
    ),
    "gravestone_doji": lambda bars, i: (
        -100
        if _pp_doji(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["low"]), float(bars[i]["close"]))
        and _upper(float(bars[i]["open"]), float(bars[i]["high"]), float(bars[i]["close"]))
        > 2 * max(_body(float(bars[i]["open"]), float(bars[i]["close"])), 1e-9)
        else 0
    ),
}


def load_pattern_selection() -> dict[str, Any]:
    path = path_from_config("pattern_selection", "data/pattern_selection.json")
    if not path.exists():
        return {"enabled": "all", "signal_filter": "all"}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_enabled_ids(selection: dict | None = None) -> list[str]:
    sel = selection or load_pattern_selection()
    enabled = sel.get("enabled", "all")
    if enabled == "all" or enabled is None:
        return [p["id"] for p in PATTERN_REGISTRY]
    return [str(x) for x in enabled if x in PATTERN_BY_ID]


def _detect_talib(bars: list[dict], enabled_ids: list[str], lookback: int = 3) -> list[dict]:
    o, h, l, c = _ohlc(bars)
    oa, ha, la, ca = np.array(o), np.array(h), np.array(l), np.array(c)
    i = len(bars) - 1
    hits: list[dict] = []
    for pid in enabled_ids:
        meta = PATTERN_BY_ID.get(pid)
        if not meta:
            continue
        fn = getattr(talib, meta["talib"], None)
        if fn is None:
            continue
        arr = fn(oa, ha, la, ca)
        for off in range(lookback):
            idx = i - off
            if idx < 0:
                continue
            val = int(arr[idx])
            if val == 0:
                continue
            hits.append({
                "id": pid,
                "name": meta["name"],
                "category": meta["category"],
                "signal": val,
                "signal_label": signal_label(val),
                "date": bars[idx]["date"],
                "bars_ago": off,
            })
            break
    return hits


def _detect_pure(bars: list[dict], enabled_ids: list[str], lookback: int = 3) -> list[dict]:
    i = len(bars) - 1
    hits: list[dict] = []
    for pid in enabled_ids:
        fn = PURE_DETECTORS.get(pid)
        if not fn:
            continue
        meta = PATTERN_BY_ID[pid]
        for off in range(lookback):
            idx = i - off
            if idx < 0:
                continue
            val = int(fn(bars, idx))
            if val == 0:
                continue
            hits.append({
                "id": pid,
                "name": meta["name"],
                "category": meta["category"],
                "signal": val,
                "signal_label": signal_label(val),
                "date": bars[idx]["date"],
                "bars_ago": off,
            })
            break
    return hits


def detect_patterns(
    bars: list[dict],
    enabled_ids: list[str] | None = None,
    lookback: int = 3,
    signal_filter: str = "all",
) -> dict[str, Any]:
    """扫描近 lookback 根 K 线的形态命中。"""
    if len(bars) < 5:
        return {"hits": [], "engine": "none", "bullish": 0, "bearish": 0}

    ids = enabled_ids or resolve_enabled_ids()
    if HAS_TALIB:
        hits = _detect_talib(bars, ids, lookback)
        engine = "talib"
    else:
        hits = _detect_pure(bars, ids, lookback)
        engine = "pure_python"

    if signal_filter == "bullish":
        hits = [h for h in hits if h["signal"] > 0]
    elif signal_filter == "bearish":
        hits = [h for h in hits if h["signal"] < 0]

    return {
        "hits": hits,
        "engine": engine,
        "talib_available": HAS_TALIB,
        "bullish": sum(1 for h in hits if h["signal"] > 0),
        "bearish": sum(1 for h in hits if h["signal"] < 0),
        "enabled_count": len(ids),
    }


def registry_for_ui() -> list[dict]:
    return [
        {"id": p["id"], "name": p["name"], "category": p["category"], "pure_python": p["id"] in PURE_DETECTORS}
        for p in PATTERN_REGISTRY
    ]
