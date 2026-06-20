#!/usr/bin/env python3
"""东方财富 K 线拉取（stdlib，无第三方依赖）。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app_config import sync_config
from sq_logging import setup_logging

log = setup_logging("stock_quant.kline")

ROOT = Path(__file__).parent
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# 东方财富 klt：101 日 / 102 周 / 103 月
KLT_MAP = {"daily": "101", "weekly": "102", "monthly": "103"}


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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(full, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionResetError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2.0 * (attempt + 1))
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


def _cache_path(code: str, period: str) -> Path:
    return ROOT / "data" / "kline_cache" / f"{code}_{period}.json"


def _load_cache(code: str, period: str) -> list[Bar] | None:
    path = _cache_path(code, period)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [
                Bar(
                    date=str(b["date"]),
                    open=float(b["open"]),
                    close=float(b["close"]),
                    high=float(b["high"]),
                    low=float(b["low"]),
                    volume=float(b["volume"]),
                    amount=float(b.get("amount") or 0),
                    change_pct=float(b.get("change_pct") or 0),
                    turnover=float(b.get("turnover") or 0),
                )
                for b in raw
            ]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        log.warning("K线缓存无效 %s: %s", path, e)
    return None


def _save_cache(code: str, period: str, bars: list[Bar]) -> None:
    path = _cache_path(code, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bars_to_dicts(bars), ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_klines(
    code: str,
    market: str | None = None,
    days: int | None = None,
    period: str = "daily",
) -> list[Bar]:
    cfg = sync_config()
    klt = KLT_MAP.get(period, "101")
    if days is not None:
        limit = days
    elif period == "weekly":
        limit = int(cfg.get("kline_weeks", 120))
    elif period == "monthly":
        limit = int(cfg.get("kline_months", 60))
    else:
        limit = int(cfg.get("kline_days", 120))
    params = {
        "secid": secid(code, market),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": klt,
        "fqt": "1",
        "end": "20500101",
        "lmt": str(limit),
    }
    try:
        raw = _request(KLINE_URL, params)
    except RuntimeError as e:
        cached = _load_cache(code, period)
        if cached:
            log.warning("K线请求失败，使用缓存: %s (%s) — %s", code, period, e)
            return cached
        raise
    bars = parse_klines(raw)
    if not bars:
        cached = _load_cache(code, period)
        if cached:
            log.warning("远端无数据，使用缓存 K 线: %s (%s)", code, period)
            return cached
        log.warning("无 K 线数据: %s", code)
        return []
    _save_cache(code, period, bars)
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
