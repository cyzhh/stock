#!/usr/bin/env python3
"""基于 hhxg 快照生成 A 股每日资金流向复盘报告（四维度框架）。"""

from __future__ import annotations

import re
from typing import Any


def _flat_sectors(sectors: list) -> list[dict]:
    rows: list[dict] = []
    for group in sectors or []:
        if not isinstance(group, dict):
            continue
        label = group.get("label") or "板块"
        for side, key in (("in", "strong"), ("out", "weak")):
            for item in group.get(key) or []:
                if not isinstance(item, dict):
                    continue
                net = item.get("net_yi")
                if net is None:
                    continue
                rows.append({
                    "name": item.get("name") or "—",
                    "net_yi": float(net),
                    "bias_pct": item.get("bias_pct"),
                    "leader": item.get("leader") or "",
                    "group": label,
                    "side": side,
                })
    return rows


def _bucket_stats(market: dict) -> dict:
    buckets = market.get("buckets") or []
    up = sum(b.get("count") or 0 for b in buckets if b.get("dir") == "up")
    down = sum(b.get("count") or 0 for b in buckets if b.get("dir") == "down")
    prev_up = sum(b.get("prev") or 0 for b in buckets if b.get("dir") == "up")
    prev_down = sum(b.get("prev") or 0 for b in buckets if b.get("dir") == "down")
    return {
        "up": up,
        "down": down,
        "ratio": round(up / down, 2) if down else None,
        "up_delta": up - prev_up,
        "down_delta": down - prev_down,
        "buckets": buckets,
    }


def _parse_main_fund_highlight(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"净流入\s*([+-]?\d+(?:\.\d+)?)\s*亿", text)
    if m:
        return float(m.group(1))
    m = re.search(r"净流出\s*(\d+(?:\.\d+)?)\s*亿", text)
    if m:
        return -float(m.group(1))
    return None


def _mood_label(sentiment: float, up_ratio: float | None, limit_up: int, fried: int) -> str:
    fried_rate = fried / (limit_up + fried) if (limit_up + fried) else 0
    if sentiment >= 65 and (up_ratio or 0) >= 2.5:
        return "积极进攻"
    if sentiment < 45 or fried_rate > 0.55:
        return "防御撤退"
    return "存量博弈"


def _sector_nature(item: dict) -> str:
    net = item.get("net_yi") or 0
    bias = item.get("bias_pct")
    if net >= 20:
        return "主线抱团" if (bias or 0) >= 0 else "逆势吸筹"
    if net <= -50:
        return "高位派发" if (bias or 0) < 0 else "暗中吸筹"
    if net >= 5:
        return "持续性流入"
    if net <= -20:
        return "获利回吐"
    return "轮动试探"


def _concentration(themes: list) -> dict:
    nets = [t.get("net_yi") for t in themes if t.get("net_yi") is not None]
    if not nets:
        return {"style": "数据不足", "positive": 0, "negative": 0}
    pos = sum(1 for n in nets if n > 0)
    neg = sum(1 for n in nets if n < 0)
    top = max(nets, key=abs)
    if pos <= 2 and abs(top) >= 5:
        style = "抱团主线"
    elif pos >= 4 and neg >= 4:
        style = "电风扇轮动"
    else:
        style = "分化撕裂"
    return {"style": style, "positive": pos, "negative": neg, "top_abs": top}


def _anomalies(market: dict, sectors: list, themes: list, main_fund: float | None) -> list[dict]:
    items: list[dict] = []
    bs = _bucket_stats(market)
    sentiment = market.get("sentiment_index") or 0
    up = bs["up"]
    down = bs["down"]

    if sentiment >= 60 and main_fund is not None and main_fund < -500:
        items.append({
            "type": "量价背离",
            "level": "warn",
            "text": f"赚钱效应 {sentiment}% 偏强，但主力资金大幅净流出 {abs(main_fund):.0f} 亿，指数与资金出现背离。",
        })

    for s in sectors:
        net = s.get("net_yi") or 0
        bias = s.get("bias_pct")
        if bias is not None and bias < -3 and net > 10:
            items.append({
                "type": "逆势吸筹",
                "level": "info",
                "text": f"{s['group']}·{s['name']} 跌 {abs(bias):.1f}% 但净流入 +{net:.0f} 亿，疑似暗中吸筹。",
            })
        if bias is not None and bias > 2 and net < -30:
            items.append({
                "type": "价涨钱出",
                "level": "warn",
                "text": f"{s['group']}·{s['name']} 涨 {bias:.1f}% 却净流出 {abs(net):.0f} 亿，高位派发迹象。",
            })

    drain = [s for s in sectors if (s.get("net_yi") or 0) <= -100]
    if drain:
        d = max(drain, key=lambda x: abs(x.get("net_yi") or 0))
        items.append({
            "type": "抽血效应",
            "level": "danger",
            "text": f"{d['name']} 单日净流出 {abs(d['net_yi']):.0f} 亿，对其他板块形成抽血，警惕跟风失血。",
        })

    if up and down and up > down * 2.5 and market.get("limit_up", 0) < 60:
        items.append({
            "type": "结构失真",
            "level": "info",
            "text": f"涨 {up} / 跌 {down} 家数悬殊，但涨停仅 {market.get('limit_up')} 家，普涨背后赚钱效应未必同步放大。",
        })

    theme_pos = [t for t in themes if (t.get("net_yi") or 0) > 3]
    theme_neg = [t for t in themes if (t.get("net_yi") or 0) < -3]
    if theme_pos and theme_neg:
        items.append({
            "type": "题材分歧",
            "level": "info",
            "text": f"题材游资净额分化：{theme_pos[0]['name']} +{theme_pos[0]['net_yi']:.1f}亿 vs {theme_neg[0]['name']} {theme_neg[0]['net_yi']:.1f}亿。",
        })

    return items[:6]


def build_fund_flow_report(snapshot: dict) -> dict:
    """生成四维度资金流向复盘 + 图表数据。"""
    market = snapshot.get("market") or {}
    sectors_raw = snapshot.get("sectors") or []
    themes = snapshot.get("hot_themes") or []
    hotmoney = snapshot.get("hotmoney") or {}
    ai = snapshot.get("ai_summary") or {}
    if isinstance(ai, str):
        ai = {"news_highlight": ai}

    date = snapshot.get("date") or market.get("date") or "—"
    bs = _bucket_stats(market)
    flat = _flat_sectors(sectors_raw)
    inflows = sorted([s for s in flat if s["net_yi"] > 0], key=lambda x: x["net_yi"], reverse=True)[:5]
    outflows = sorted([s for s in flat if s["net_yi"] < 0], key=lambda x: x["net_yi"])[:5]
    top3_in = inflows[:3]
    top3_out = outflows[:3]

    sentiment = market.get("sentiment_index") or 0
    limit_up = market.get("limit_up") or 0
    fried = market.get("fried") or 0
    limit_down = market.get("limit_down") or 0
    mood = _mood_label(sentiment, bs["ratio"], limit_up, fried)
    main_fund = _parse_main_fund_highlight(ai.get("news_highlight") or "")
    hm_net = hotmoney.get("total_net_yi")
    conc = _concentration(themes)

    fried_rate = round(fried / (limit_up + fried) * 100, 1) if (limit_up + fried) else None

    # --- 图表数据 ---
    max_abs = max([abs(s["net_yi"]) for s in flat], default=1) or 1
    sector_bars = {
        "inflow": [
            {"name": f"{s['group']}·{s['name']}", "value": s["net_yi"], "pct": round(s["net_yi"] / max_abs * 100, 1),
             "bias_pct": s.get("bias_pct"), "leader": s.get("leader")}
            for s in top3_in
        ],
        "outflow": [
            {"name": f"{s['group']}·{s['name']}", "value": s["net_yi"], "pct": round(abs(s["net_yi"]) / max_abs * 100, 1),
             "bias_pct": s.get("bias_pct"), "leader": s.get("leader")}
            for s in top3_out
        ],
    }
    theme_bars = [
        {"name": t.get("name") or "—", "value": t.get("net_yi") or 0,
         "limitup": t.get("limitup_count"), "pct": round(abs(t.get("net_yi") or 0) / max(
             [abs(x.get("net_yi") or 0) for x in themes] or [1]
         ) * 100, 1)}
        for t in themes[:8] if t.get("net_yi") is not None
    ]
    bucket_trend = [
        {"name": b.get("name"), "count": b.get("count"), "prev": b.get("prev"),
         "delta": (b.get("count") or 0) - (b.get("prev") or 0), "dir": b.get("dir")}
        for b in bs["buckets"]
    ]

    anomalies = _anomalies(market, flat, themes, main_fund)

    # 明日观察
    watch_sectors = [s["name"] for s in inflows[:2]]
    if not watch_sectors and themes:
        watch_sectors = [themes[0].get("name", "")]
    risks: list[str] = []
    if main_fund is not None and main_fund < 0:
        risks.append(f"主力资金净流出 {abs(main_fund):.0f} 亿，增量资金不足")
    if fried_rate and fried_rate > 50:
        risks.append(f"炸板率 {fried_rate}%，追高接力风险高")
    if conc["style"] == "电风扇轮动":
        risks.append("板块电风扇轮动，追热点易两面挨打")
    if outflows and outflows[0]["net_yi"] <= -100:
        risks.append(f"{outflows[0]['name']} 大幅失血，拖累相关产业链")

    # --- 四维度文案 ---
    s1_points = [
        f"**涨跌结构**：涨 {bs['up']} 家 / 跌 {bs['down']} 家"
        + (f"（涨跌比 {bs['ratio']:.1f}）" if bs["ratio"] else ""),
        f"**涨停生态**：涨停 {limit_up} · 炸板 {fried}"
        + (f"（炸板率 {fried_rate}%）" if fried_rate is not None else "")
        + f" · 跌停 {limit_down}",
        f"**赚钱效应**：{sentiment}%（{market.get('sentiment_label') or '—'}），较昨日结构差 {market.get('struct_diff', '—')}pp",
        f"**资金定性**：当前处于 **{mood}** 阶段",
    ]
    if main_fund is not None:
        s1_points.append(
            f"**主力资金**：周累计净流入 **{main_fund:+.0f} 亿**"
            + ("，大资金偏防守" if main_fund < 0 else "，大资金仍有一定承接")
        )
    if hm_net is not None:
        s1_points.append(f"**游资龙虎榜**：单日净买入 **{hm_net:+.1f} 亿**（短线情绪指标）")

    s2_points = []
    for i, s in enumerate(top3_in, 1):
        nature = _sector_nature(s)
        bias = s.get("bias_pct")
        bias_s = f"，板块涨跌 {bias:+.1f}%" if bias is not None else ""
        s2_points.append(
            f"**吸金 #{i} {s['group']}·{s['name']}**：净流入 **+{s['net_yi']:.0f} 亿**{bias_s}，龙头 {s.get('leader') or '—'}，判定 **{nature}**"
        )
    for i, s in enumerate(top3_out, 1):
        nature = _sector_nature(s)
        bias = s.get("bias_pct")
        bias_s = f"，板块涨跌 {bias:+.1f}%" if bias is not None else ""
        s2_points.append(
            f"**失血 #{i} {s['group']}·{s['name']}**：净流出 **{s['net_yi']:.0f} 亿**{bias_s}，判定 **{nature}**"
        )
    s2_points.append(
        f"**抱团 vs 轮动**：题材资金呈 **{conc['style']}**（{conc['positive']} 个题材净流入 / {conc['negative']} 个净流出）"
    )

    s3_points = [a["text"] for a in anomalies] or ["暂无明显量价背离或抽血异动，资金与涨跌结构大致匹配。"]

    s4_points = [
        f"**防守观察**：赚钱效应 {sentiment}% 区间"
        + ("，短线不宜盲目追高" if sentiment >= 70 else "，可沿强势板块回踩低吸"),
        f"**明日盯盘**：重点关注 **{'、'.join(watch_sectors) or '—'}**（资金惯性 + 龙头效应）",
    ]
    if ai.get("focus_direction"):
        s4_points.append(f"**方向参考**：{ai['focus_direction']}")
    if risks:
        s4_points.append("**风险警示**：" + "；".join(risks))
    else:
        s4_points.append("**风险警示**：资金面暂无极端风险信号，仍需关注炸板率与主线持续性。")

    return {
        "title": f"A股每日资金流向复盘 · {date}",
        "date": date,
        "mood": mood,
        "metrics": {
            "sentiment": sentiment,
            "up_count": bs["up"],
            "down_count": bs["down"],
            "up_down_ratio": bs["ratio"],
            "limit_up": limit_up,
            "fried_rate": fried_rate,
            "main_fund_weekly_yi": main_fund,
            "hotmoney_net_yi": hm_net,
            "concentration": conc["style"],
        },
        "charts": {
            "sector_inflow": sector_bars["inflow"],
            "sector_outflow": sector_bars["outflow"],
            "theme_flow": theme_bars,
            "bucket_trend": bucket_trend,
        },
        "anomalies": anomalies,
        "sections": [
            {"id": "market", "title": "1. 大盘资金大局观", "points": s1_points},
            {"id": "sector", "title": "2. 板块资金风向标", "points": s2_points},
            {"id": "anomaly", "title": "3. 异常与异动信号", "points": s3_points},
            {"id": "outlook", "title": "4. 明日观察与策略", "points": s4_points},
        ],
        "watchlist": watch_sectors,
        "risks": risks,
    }
