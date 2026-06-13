#!/usr/bin/env python3
"""东方财富 K 线拉取（stdlib，无第三方依赖）。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app_config import sync_config
from sq_logging import setup_logging

log = setup_logging("stock_quant.kline")

KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


@dataclass
class Bar:
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    change_pct: float
    turnover: float


def secid(code: str, market: str | None = None) -> str:
    m = market or ("sh" if code.startswith(("6", "5", "9")) else "sz")
    prefix = "1" if m == "sh" else "0"
    return f"{prefix}.{code}"


def _request(url: str, params: dict[str, Any]) -> dict:
    cfg = sync_config()
    timeout = int(cfg.get("timeout_sec", 20))
    retries = int(cfg.get("retries", 2))
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    headers = {"User-Agent": "stock-quant/1.0"}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(full, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionResetError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"K线请求失败 {code_hint(params)}: {last_err}")


def code_hint(params: dict) -> str:
    return str(params.get("secid", ""))


def parse_klines(raw: dict) -> list[Bar]:
    kl = (raw.get("data") or {}).get("klines") or []
    bars: list[Bar] = []
    for row in kl:
        parts = row.split(",")
        if len(parts) < 11:
            continue
        bars.append(
            Bar(
                date=parts[0],
                open=float(parts[1]),
                close=float(parts[2]),
                high=float(parts[3]),
                low=float(parts[4]),
                volume=float(parts[5]),
                amount=float(parts[6]),
                change_pct=float(parts[8]),
                turnover=float(parts[10]),
            )
        )
    return bars


def fetch_klines(code: str, market: str | None = None, days: int | None = None) -> list[Bar]:
    cfg = sync_config()
    limit = days or int(cfg.get("kline_days", 120))
    params = {
        "secid": secid(code, market),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "end": "20500101",
        "lmt": str(limit),
    }
    raw = _request(KLINE_URL, params)
    bars = parse_klines(raw)
    if not bars:
        log.warning("无 K 线数据: %s", code)
    return bars


def bars_to_dicts(bars: list[Bar]) -> list[dict[str, Any]]:
    return [
        {
            "date": b.date,
            "open": b.open,
            "close": b.close,
            "high": b.high,
            "low": b.low,
            "volume": b.volume,
            "amount": b.amount,
            "change_pct": b.change_pct,
            "turnover": b.turnover,
        }
        for b in bars
    ]
