#!/usr/bin/env python3
"""东方财富：行业/概念板块近 N 日主力资金净流入排行。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app_config import sync_config
from sq_logging import setup_logging

log = setup_logging("stock_quant.sector_flow")

HOST = "https://push2delay.eastmoney.com"
LIST_URL = f"{HOST}/api/qt/clist/get"
STOCK_URL = f"{HOST}/api/qt/stock/get"
FLOW_URL = f"{HOST}/api/qt/stock/fflow/daykline/get"
HIS_HOST = "https://push2his.eastmoney.com"
HIS_FLOW_URL = f"{HIS_HOST}/api/qt/stock/fflow/daykline/get"
UT = "bd1d9ddb04089700a9ac0ab8276a5cb2"

BOARD_FS = {
    "industry": "m:90+t:2",
    "concept": "m:90+t:3",
}

# 东财板块资金多周期字段（clist / stock/get）
PERIOD_FID = {
    5: "f176",
    10: "f170",
    20: "f180",
}


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/bkzj/hy.html",
    }


def _get(url: str, params: dict[str, Any]) -> dict:
    cfg = sync_config()
    timeout = int(cfg.get("timeout_sec", 20))
    retries = int(cfg.get("retries", 3))
    full = f"{url}?{urllib.parse.urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(full, headers=_headers())
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
                ConnectionResetError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"板块资金请求失败: {last_err}")


def _yi(val: Any) -> float | None:
    if val is None or val == "-" or val == "":
        return None
    try:
        return round(float(val) / 1e8, 2)
    except (TypeError, ValueError):
        return None


def fetch_board_ranking(
    board_type: str = "industry",
    days: int = 20,
    top_n: int = 10,
    page_size: int = 120,
) -> list[dict]:
    """单次请求按近 N 日主力净流入排序（东财 f180/f170/f176）。"""
    fid = PERIOD_FID.get(days, PERIOD_FID[20])
    fs = BOARD_FS.get(board_type, BOARD_FS["industry"])
    params = {
        "pn": "1", "pz": str(page_size), "po": "1", "np": "1",
        "ut": UT, "fltt": "2", "invt": "2", "fid": fid,
        "fs": fs,
        "fields": f"f12,f14,f2,f3,f62,f164,f170,f176,f180,f184,f128,f140,{fid}",
    }
    raw = _get(LIST_URL, params)
    diff = (raw.get("data") or {}).get("diff") or []
    rows: list[dict] = []
    for row in diff:
        if not isinstance(row, dict):
            continue
        code = row.get("f12")
        name = row.get("f14")
        if not code or not name:
            continue
        total = _yi(row.get(fid))
        if total is None:
            continue
        rows.append({
            "code": str(code),
            "name": str(name),
            "total_main_yi": total,
            "today_main_yi": _yi(row.get("f62")),
            "recent5_main_yi": _yi(row.get("f176")),
            "recent10_main_yi": _yi(row.get("f170")),
            "change_pct": row.get("f3"),
            "bias_pct": row.get("f184"),
            "leader": row.get("f128") or "",
        })
    rows.sort(key=lambda x: x["total_main_yi"], reverse=True)
    return rows[:top_n]


def _parse_f178(raw: Any) -> list[dict]:
    if not raw or raw == "-":
        return []
    try:
        arr = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return []
    out: list[dict] = []
    for item in arr or []:
        if not isinstance(item, dict):
            continue
        d = item.get("date")
        amt = item.get("mainNetAmt")
        if not d:
            continue
        yi = _yi(amt)
        if yi is None:
            continue
        out.append({"date": d, "main_yi": yi})
    return out


def fetch_recent_series(code: str, days: int = 20) -> list[dict]:
    """拉取板块日度主力净流入序列（优先 push2his，回退 f178 五日嵌入）。"""
    params = {
        "lmt": str(days),
        "klt": "101",
        "secid": f"90.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": UT,
    }
    for url in (HIS_FLOW_URL, FLOW_URL):
        try:
            raw = _get(url, params)
            klines = (raw.get("data") or {}).get("klines") or []
            series: list[dict] = []
            for row in klines:
                parts = str(row).split(",")
                if len(parts) < 2:
                    continue
                yi = _yi(parts[1])
                if yi is None:
                    continue
                series.append({"date": parts[0], "main_yi": yi})
            if len(series) >= 3:
                return series[-days:]
        except RuntimeError:
            continue

    try:
        raw = _get(STOCK_URL, {
            "secid": f"90.{code}",
            "fields": "f178,f62",
            "ut": UT,
        })
        series = _parse_f178((raw.get("data") or {}).get("f178"))
        today = _yi((raw.get("data") or {}).get("f62"))
        if today is not None and today != 0:
            from datetime import date
            td = date.today().isoformat()
            if not series or series[-1]["date"] != td:
                series.append({"date": td, "main_yi": today})
        return series[-days:]
    except RuntimeError:
        return []


def enrich_top_with_series(top: list[dict], days: int = 20, sleep_sec: float = 0.15) -> None:
    for i, item in enumerate(top):
        item["series"] = fetch_recent_series(item["code"], days=days)
        item["days"] = len(item["series"])
        if sleep_sec and i < len(top) - 1:
            time.sleep(sleep_sec)


def build_top_ranking(
    board_type: str = "industry",
    days: int = 20,
    top_n: int = 10,
    with_series: bool = True,
) -> dict:
    label = "行业" if board_type == "industry" else "概念"
    top = fetch_board_ranking(board_type, days=days, top_n=top_n)
    if with_series:
        enrich_top_with_series(top, days=days)
    for i, item in enumerate(top, 1):
        item["rank"] = i
    return {
        "board_type": board_type,
        "board_label": label,
        "days": days,
        "top_n": top_n,
        "metric": f"近{days}日主力净流入",
        "source": "eastmoney",
        "count_scanned": top_n,
        "top": top,
    }


def build_sector_flow_report(days: int = 20, top_n: int = 10) -> dict:
    industry = build_top_ranking("industry", days=days, top_n=top_n)
    time.sleep(0.3)
    concept = build_top_ranking("concept", days=days, top_n=top_n)
    dates: list[str] = []
    for item in (industry.get("top") or []) + (concept.get("top") or []):
        for p in item.get("series") or []:
            dates.append(p["date"])
    return {
        "days": days,
        "top_n": top_n,
        "date_range": {"start": min(dates) if dates else None, "end": max(dates) if dates else None},
        "industry": industry,
        "concept": concept,
    }
