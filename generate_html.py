#!/usr/bin/env python3
"""汇总数据并生成 index.html 看板。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app_config import path_from_config
from enrich_factors import enrich_scan_data
from fund_flow_report import build_fund_flow_report
from kline_patterns import registry_for_ui
from weekly_bbi_report import run_all as run_weekly_bbi
try:
    from kline_patterns import HAS_TALIB
except ImportError:
    HAS_TALIB = False
from sq_logging import setup_logging

log = setup_logging("stock_quant.generate_html")

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "dashboard.html"
OUT = ROOT / "index.html"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _format_ai_summary(raw) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        parts = [raw.get(k) for k in ("market_state", "focus_direction", "theme_focus", "hotmoney_state", "news_highlight") if raw.get(k)]
        return " · ".join(parts)
    return ""


def build_dashboard_payload(enrich: bool = True) -> dict:
    snapshot = _load_json(path_from_config("market_snapshot", "data/market_snapshot.json"))
    scan = _load_json(path_from_config("scan_results", "output/scan_results.json"))
    if enrich and scan:
        import os
        fetch_kline = os.environ.get("CI_FAST") != "1"
        scan = enrich_scan_data(scan, fetch_kline=fetch_kline)
    backtest = _load_json(path_from_config("backtest_report", "output/backtest_report.json"))
    market = snapshot.get("market") or {}
    raw_news = snapshot.get("news") or snapshot.get("focus_news") or []
    news = []
    for item in raw_news[:12]:
        if not isinstance(item, dict):
            continue
        news.append({
            "time": (item.get("t") or item.get("time") or item.get("date") or "")[:16].replace("T", " "),
            "cat": item.get("cat") or item.get("category") or "",
            "title": item.get("title") or item.get("content") or item.get("text") or "",
        })
    ai_raw = snapshot.get("ai_summary")
    sector_flow = _load_json(path_from_config("sector_flow_20d", "data/sector_flow_20d.json"))
    weekly_bbi = _load_json(path_from_config("weekly_bbi_report", "output/weekly_bbi_report.json"))
    if not weekly_bbi.get("reports"):
        import os
        if os.environ.get("CI_FAST") != "1":
            try:
                weekly_bbi = run_weekly_bbi()
            except Exception as e:
                log.warning("周线 BBI 分析失败: %s", e)
                weekly_bbi = {"reports": [], "error": str(e)}
        else:
            weekly_bbi = {"reports": [], "skipped": "CI_FAST"}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_date": snapshot.get("date") or scan.get("market_date"),
        "snapshot": {
            "meta": snapshot.get("meta") or {},
            "market": market,
            "hot_themes": snapshot.get("hot_themes") or [],
            "ladder_detail": snapshot.get("ladder_detail") or {},
            "ladder_summary": snapshot.get("ladder") or {},
            "hotmoney": snapshot.get("hotmoney") if isinstance(snapshot.get("hotmoney"), dict) else {},
            "sectors": snapshot.get("sectors") or [],
            "comparison": snapshot.get("comparison") or {},
            "links": snapshot.get("links") or {},
            "news": news,
            "ai_summary": _format_ai_summary(ai_raw),
            "ai_summary_detail": ai_raw if isinstance(ai_raw, dict) else {},
        },
        "scan": {
            "universe_size": scan.get("universe_size", 0),
            "pick_count": scan.get("pick_count", 0),
            "picks": scan.get("picks") or [],
            "all_results": scan.get("all_results") or [],
        },
        "backtest": {
            "summary": backtest.get("summary") or [],
            "overall": backtest.get("overall") or {},
            "stock_results": backtest.get("stock_results") or [],
        },
        "meta": {
            "engine": "stock-quant",
            "inspired_by": "InStock (myhhub/stock)",
            "data_sources": ["hhxg.top", "eastmoney"],
            "talib_available": HAS_TALIB,
        },
        "patterns": {
            "registry": registry_for_ui(),
            "selection": _load_json(path_from_config("pattern_selection", "data/pattern_selection.json")),
        },
        "fund_flow": build_fund_flow_report(snapshot),
        "sector_flow_20d": sector_flow,
        "weekly_bbi": weekly_bbi,
    }


def main() -> None:
    data = build_dashboard_payload()
    dash_path = path_from_config("dashboard_data", "output/dashboard.json")
    dash_path.parent.mkdir(parents=True, exist_ok=True)
    dash_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    template = TEMPLATE.read_text(encoding="utf-8")
    html = template.replace("/*__DASHBOARD__*/", json.dumps(data, ensure_ascii=False, indent=2))
    OUT.write_text(html, encoding="utf-8")
    log.info("已生成 %s", OUT)
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    main()
