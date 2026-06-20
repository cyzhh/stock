#!/usr/bin/env python3
"""周线 BBI 牛熊线分析：阶段划分、关键区间、信号与风控。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app_config import get_section, path_from_config
from indicators import bbi, sma
from kline_fetcher import bars_to_dicts, fetch_klines
from sq_logging import setup_logging

log = setup_logging("stock_quant.weekly_bbi")

ROOT = Path(__file__).parent


def _round(v: float | None, n: int = 3) -> float | None:
    if v is None:
        return None
    return round(float(v), n)


def _pct(a: float, b: float) -> float | None:
    if not b:
        return None
    return round((a - b) / b * 100, 2)


def _body_ratio(bar: dict) -> float:
    rng = float(bar["high"]) - float(bar["low"])
    if rng <= 0:
        return 0.0
    return abs(float(bar["close"]) - float(bar["open"])) / rng


def _candle_type(bar: dict) -> str:
    o, c, h, l = float(bar["open"]), float(bar["close"]), float(bar["high"]), float(bar["low"])
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    rng = h - l
    if rng <= 0:
        return "doji"
    if body / rng < 0.1:
        return "doji"
    if upper > body * 2 and c < o:
        return "shooting_star"
    if lower > body * 2 and c > o:
        return "hammer"
    if c > o and body / rng > 0.6:
        return "strong_bull"
    if c < o and body / rng > 0.6:
        return "strong_bear"
    return "bull" if c > o else "bear"


def find_pivots(bars: list[dict], window: int = 3) -> tuple[list[dict], list[dict]]:
    """局部高低点（用于支撑/压力）。"""
    highs: list[dict] = []
    lows: list[dict] = []
    n = len(bars)
    for i in range(window, n - window):
        h = float(bars[i]["high"])
        l = float(bars[i]["low"])
        if all(h >= float(bars[j]["high"]) for j in range(i - window, i + window + 1) if j != i):
            highs.append({"index": i, "date": bars[i]["date"], "price": h})
        if all(l <= float(bars[j]["low"]) for j in range(i - window, i + window + 1) if j != i):
            lows.append({"index": i, "date": bars[i]["date"], "price": l})
    return highs, lows


def bbi_crossovers(bars: list[dict], bbi_line: list[float | None]) -> list[dict]:
    events: list[dict] = []
    for i in range(1, len(bars)):
        if bbi_line[i] is None or bbi_line[i - 1] is None:
            continue
        prev_c, curr_c = float(bars[i - 1]["close"]), float(bars[i]["close"])
        prev_b, curr_b = bbi_line[i - 1], bbi_line[i]
        if prev_c >= prev_b and curr_c < curr_b:
            events.append({"date": bars[i]["date"], "type": "break_down", "close": curr_c, "bbi": curr_b})
        elif prev_c <= prev_b and curr_c > curr_b:
            events.append({"date": bars[i]["date"], "type": "break_up", "close": curr_c, "bbi": curr_b})
    return events


def count_bbi_bounces(bars: list[dict], bbi_line: list[float | None], lookback: int = 52) -> int:
    """深度回调触及 BBI 后收阳站回的次数。"""
    start = max(0, len(bars) - lookback)
    count = 0
    for i in range(start + 1, len(bars) - 1):
        if bbi_line[i] is None:
            continue
        low, close = float(bars[i]["low"]), float(bars[i]["close"])
        b = bbi_line[i]
        if low <= b * 1.02 and close > b and float(bars[i]["close"]) > float(bars[i]["open"]):
            count += 1
    return count


def detect_phase(
    bars: list[dict],
    bbi_line: list[float | None],
    stage_high: float,
    stage_high_idx: int,
) -> dict[str, Any]:
    i = len(bars) - 1
    close = float(bars[i]["close"])
    curr_bbi = bbi_line[i]
    above = curr_bbi is not None and close > curr_bbi
    weeks_since_high = i - stage_high_idx

    cross = bbi_crossovers(bars, bbi_line)
    last_cross = cross[-1] if cross else None
    recent_break_down = last_cross and last_cross["type"] == "break_down" and last_cross["date"] == bars[i]["date"]

    # 高点后震荡：距阶段高点 <15% 且未创新高超过 4 周
    near_high = stage_high > 0 and close >= stage_high * 0.88
    no_new_high = weeks_since_high >= 4

    if recent_break_down or (not above and last_cross and last_cross["type"] == "break_down" and weeks_since_high <= 8):
        phase_id, phase_name, signal = "breakdown", "破位回调", "bear"
        summary = "周线收盘跌破 BBI 牛熊线，中期趋势由多转空，调整周期开启。"
    elif near_high and no_new_high and above:
        phase_id, phase_name, signal = "consolidation", "高位震荡", "neutral"
        summary = "阶段高点后 K 线在 BBI 上方横盘，多头动能衰减，需警惕背离。"
    elif above:
        phase_id, phase_name, signal = "uptrend", "多头主升", "bull"
        summary = "价格运行在 BBI 上方，中期多头结构，回调踩稳牛熊线为主基调。"
    else:
        phase_id, phase_name, signal = "downtrend", "空头调整", "bear"
        summary = "价格持续位于 BBI 下方，中期偏空，反弹至 BBI 附近视为压力。"

    return {
        "id": phase_id,
        "name": phase_name,
        "signal": signal,
        "summary": summary,
        "above_bbi": above,
        "weeks_since_stage_high": weeks_since_high,
        "last_crossover": last_cross,
    }


def build_levels(
    bars: list[dict],
    bbi_line: list[float | None],
    pivot_highs: list[dict],
    pivot_lows: list[dict],
    stage_high: float,
    hist_low: float,
) -> dict[str, list[dict]]:
    i = len(bars) - 1
    close = float(bars[i]["close"])
    curr_bbi = bbi_line[i] or close

    resistances: list[dict] = []
    supports: list[dict] = []

    resistances.append({
        "price": _round(stage_high),
        "label": "强压力",
        "note": "阶段历史高点，套牢盘密集",
        "distance_pct": _pct(stage_high, close),
    })

    # 近 20 周 pivot 高点（在当前价上方）
    for p in sorted(pivot_highs, key=lambda x: x["price"], reverse=True):
        if p["price"] > close * 1.005 and len([r for r in resistances if r["price"] == _round(p["price"])]) == 0:
            resistances.append({
                "price": _round(p["price"]),
                "label": "次级压力",
                "note": f"Pivot 高点 {p['date']}",
                "distance_pct": _pct(p["price"], close),
            })
        if len(resistances) >= 4:
            break

    resistances.append({
        "price": _round(curr_bbi),
        "label": "BBI 牛熊线",
        "note": "反弹第一道阻力 / 多空分水岭",
        "distance_pct": _pct(curr_bbi, close),
    })

    # 按价格降序去重
    seen: set[float] = set()
    unique_res: list[dict] = []
    for r in sorted(resistances, key=lambda x: x["price"] or 0, reverse=True):
        p = r["price"]
        if p is None or p in seen:
            continue
        seen.add(p)
        unique_res.append(r)

    supports.append({
        "price": _round(close * 0.97 if close else None),
        "label": "现价附近",
        "note": "短期情绪支撑",
        "distance_pct": 0,
    })

    for p in sorted(pivot_lows, key=lambda x: x["price"], reverse=True):
        if p["price"] < close * 0.995:
            supports.append({
                "price": _round(p["price"]),
                "label": "Pivot 支撑",
                "note": f"Pivot 低点 {p['date']}",
                "distance_pct": _pct(p["price"], close),
            })
        if len(supports) >= 4:
            break

    supports.append({
        "price": _round(hist_low),
        "label": "历史低点",
        "note": "全样本周期最低点",
        "distance_pct": _pct(hist_low, close),
    })

    seen_s: set[float] = set()
    unique_sup: list[dict] = []
    for s in sorted(supports, key=lambda x: x["price"] or 0, reverse=True):
        p = s["price"]
        if p is None or p in seen_s:
            continue
        seen_s.add(p)
        unique_sup.append(s)

    return {"resistance": unique_res[:5], "support": unique_sup[:5]}


def build_phase_history(
    bars: list[dict],
    bbi_line: list[float | None],
    hist_low: float,
    stage_high: float,
    bounces: int,
) -> list[dict]:
    return [
        {
            "id": "uptrend",
            "title": "主升阶段",
            "range": f"{_round(hist_low)} → {_round(stage_high)}",
            "signal": "bull",
            "tags": ["BBI 全程支撑", f"深度回调止跌 {bounces} 次"],
            "analysis": [
                "阳线实体饱满、阴线短小，标准上升通道。",
                "每轮深度回调周线阴线多止跌于 BBI 黄线，随后收阳重新站上均线。",
                "波段高点不断抬升，低点同步上移。",
            ],
        },
        {
            "id": "consolidation",
            "title": "高位震荡",
            "signal": "neutral",
            "tags": ["高点不再创新高", "K 线与 BBI 距离收窄"],
            "analysis": [
                "触及阶段高点后出现长上影、十字星，小阴小阳交替。",
                "阳线实体逐步缩小，阴线实体放大，多头买盘衰竭。",
                "K 线与 BBI 距离持续收窄，动能提前走弱。",
            ],
        },
        {
            "id": "breakdown",
            "title": "破位回调",
            "signal": "bear",
            "tags": ["大阴线击穿 BBI", "中期转空"],
            "analysis": [
                "单根大阴线无下影或下影极短，放量击穿牛熊线。",
                "收盘完全位于 BBI 下方，趋势反转强信号。",
                "后续 2–3 周若无法重新站上 BBI，下跌周期延续。",
            ],
        },
    ]


def build_signals(
    bars: list[dict],
    bbi_line: list[float | None],
    phase: dict,
    levels: dict,
    stage_high: float,
) -> dict[str, Any]:
    i = len(bars) - 1
    close = float(bars[i]["close"])
    curr_bbi = bbi_line[i] or 0
    vol = float(bars[i]["volume"])
    vol_ma5 = sma([float(b["volume"]) for b in bars], 5)
    vol_ratio = (vol / vol_ma5[i]) if vol_ma5[i] else 1.0
    candle = _candle_type(bars[i])

    bear_triggered = not phase.get("above_bbi", True)
    bear_reasons: list[str] = []
    if bear_triggered:
        bear_reasons.append(f"周线收盘 {close:.3f} 跌破 BBI {_round(curr_bbi)}")
    if stage_high and close < stage_high * 0.95:
        bear_reasons.append(f"较阶段高点 {_round(stage_high)} 回撤 {_pct(close, stage_high)}%")
    if candle in ("strong_bear", "shooting_star"):
        bear_reasons.append("最新 K 线为大阴线或射击之星，无有效承接")
    if vol_ratio > 1.3 and float(bars[i]["close"]) < float(bars[i]["open"]):
        bear_reasons.append(f"放量阴线（量比 {vol_ratio:.2f}）")

    bull_conditions = [
        "单周收实体大阳线，收盘价重新站稳 BBI 上方",
        "阳线成交量放大（量比 > 1.2），收回震荡区间上沿",
        "回调不再创新低，低点逐步抬升",
    ]
    bull_met = (
        phase.get("above_bbi")
        and candle in ("strong_bull", "hammer", "bull")
        and vol_ratio > 1.2
    )

    sup_prices = [s["price"] for s in levels.get("support", []) if s.get("price")]
    stop_line = max([p for p in sup_prices if p and p < close] or [close * 0.97])
    res_bbi = curr_bbi

    return {
        "bias": "bear" if bear_triggered else ("bull" if bull_met else "neutral"),
        "bear": {
            "triggered": bear_triggered,
            "reasons": bear_reasons,
            "conclusion": "长线仓位优先减仓，短线不抄底。" if bear_triggered else "空头信号未完全确认，保持观望。",
        },
        "bull": {
            "conditions": bull_conditions,
            "partial_met": bull_met,
            "conclusion": "多头修复信号初现，可跟踪确认。" if bull_met else "反转入场条件尚未满足，等待放量站回 BBI。",
        },
        "risk_control": {
            "holder": [
                "跌破 BBI 后减仓 50%，规避中期回调风险",
                f"止损线：若跌破 {_round(stop_line)}，清仓剩余仓位",
                f"反弹减仓区：{_round(res_bbi * 0.99)} – {_round(res_bbi)}（BBI 压力）分批离场",
            ],
            "empty": [
                "禁止左侧抄底：破位空头周期中抄底易被套",
                f"机会 A（稳健）：周线放量收回 BBI {_round(curr_bbi)}，回踩不破再建仓",
                f"机会 B（左侧）：回撤至强支撑 {_round(sup_prices[1] if len(sup_prices) > 1 else stop_line)} 出现止跌阳试错",
            ],
        },
        "candle": {
            "type": candle,
            "body_ratio": _round(_body_ratio(bars[i]), 2),
            "volume_ratio": _round(vol_ratio, 2),
        },
        "warnings": [
            "BBI 周线破位后通常有 2–6 周调整，勿期待快速 V 反",
            "高股息宽基长线逻辑未必然破坏，但周线中期回调已开启",
            "宏观利率与红利资产估值波动可能令下方支撑二次试探",
        ],
    }


def analyze_symbol(code: str, name: str, market: str | None = None, weeks: int = 120) -> dict[str, Any]:
    bars_raw = fetch_klines(code, market=market, days=weeks, period="weekly")
    bars = bars_to_dicts(bars_raw)
    if len(bars) < 30:
        return {"code": code, "name": name, "ok": False, "reason": f"周线数据不足（{len(bars)} 根）"}

    closes = [float(b["close"]) for b in bars]
    bbi_line = bbi(closes)
    i = len(bars) - 1
    close = closes[i]
    curr_bbi = bbi_line[i]

    hist_low = min(closes)
    hist_low_idx = closes.index(hist_low)
    lookback = min(52, len(closes))
    stage_window = closes[-lookback:]
    stage_high = max(stage_window)
    stage_high_idx = len(closes) - lookback + stage_window.index(stage_high)

    pivot_highs, pivot_lows = find_pivots(bars)
    bounces = count_bbi_bounces(bars, bbi_line)
    phase = detect_phase(bars, bbi_line, stage_high, stage_high_idx)
    levels = build_levels(bars, bbi_line, pivot_highs, pivot_lows, stage_high, hist_low)
    cross_events = bbi_crossovers(bars, bbi_line)
    signals = build_signals(bars, bbi_line, phase, levels, stage_high)

    bbi_trend = "flat"
    if i >= 4 and bbi_line[i] is not None and bbi_line[i - 4] is not None:
        diff = bbi_line[i] - bbi_line[i - 4]
        bbi_trend = "up" if diff > 0.001 else ("down" if diff < -0.001 else "flat")

    chart_bars = []
    for j, b in enumerate(bars[-80:]):
        chart_bars.append({
            "date": b["date"],
            "open": b["open"],
            "high": b["high"],
            "low": b["low"],
            "close": b["close"],
            "volume": b["volume"],
            "bbi": bbi_line[len(bars) - 80 + j] if len(bars) > 80 else bbi_line[j],
        })

    drawdown = _pct(close, stage_high)

    return {
        "ok": True,
        "code": code,
        "name": name,
        "market": market or ("sh" if code.startswith(("6", "5", "9")) else "sz"),
        "period": "weekly",
        "overview": {
            "date": bars[i]["date"],
            "close": _round(close),
            "change_pct": bars[i].get("change_pct"),
            "current_bbi": _round(curr_bbi),
            "bbi_trend": bbi_trend,
            "above_bbi": phase["above_bbi"],
            "hist_low": _round(hist_low),
            "hist_low_date": bars[hist_low_idx]["date"],
            "stage_high": _round(stage_high),
            "stage_high_date": bars[stage_high_idx]["date"],
            "drawdown_from_high_pct": drawdown,
            "interpretation": phase["summary"],
        },
        "phase": phase,
        "phase_history": build_phase_history(bars, bbi_line, hist_low, stage_high, bounces),
        "levels": levels,
        "bbi_events": {
            "bounce_count": bounces,
            "recent_crossovers": cross_events[-6:],
        },
        "signals": signals,
        "klines": chart_bars,
    }


def load_watchlist() -> list[dict[str, str]]:
    cfg = get_section("weekly_bbi")
    wl_path = ROOT / str(cfg.get("watchlist", "data/kline_watchlist.json"))
    if wl_path.exists():
        data = json.loads(wl_path.read_text(encoding="utf-8"))
        return data.get("symbols") or data.get("stocks") or []
    return [{"code": "515080", "name": "中证红利ETF", "market": "sh"}]


def run_all() -> dict[str, Any]:
    cfg = get_section("weekly_bbi")
    weeks = int(cfg.get("weeks", 120))
    reports: list[dict] = []
    for item in load_watchlist():
        code = item.get("code", "")
        name = item.get("name", code)
        market = item.get("market")
        try:
            rep = analyze_symbol(code, name, market=market, weeks=weeks)
            reports.append(rep)
            if rep.get("ok"):
                log.info("BBI 分析完成 %s %s BBI=%s", code, name, rep["overview"]["current_bbi"])
            else:
                log.warning("BBI 跳过 %s: %s", code, rep.get("reason"))
        except Exception as e:
            log.exception("BBI 分析失败 %s", code)
            reports.append({"code": code, "name": name, "ok": False, "reason": str(e)})

    default_code = cfg.get("default_symbol") or (reports[0]["code"] if reports else "515080")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "default_symbol": default_code,
        "period_label": "周线",
        "indicator": "BBI 多空牛熊线 (3/6/12/24 周均线)",
        "reports": reports,
    }


def main() -> None:
    data = run_all()
    out_path = path_from_config("weekly_bbi_report", "output/weekly_bbi_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in data["reports"] if r.get("ok"))
    print(f"已写入 {out_path} · {ok}/{len(data['reports'])} 标的")


if __name__ == "__main__":
    main()
