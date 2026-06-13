#!/usr/bin/env python3
"""汇总数据并生成 index.html 看板。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app_config import path_from_config
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


def build_dashboard_payload() -> dict:
    snapshot = _load_json(path_from_config("market_snapshot", "data/market_snapshot.json"))
    scan = _load_json(path_from_config("scan_results", "output/scan_results.json"))
    backtest = _load_json(path_from_config("backtest_report", "output/backtest_report.json"))
    market = snapshot.get("market") or {}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_date": snapshot.get("date") or scan.get("market_date"),
        "snapshot": {
            "market": market,
            "hot_themes": snapshot.get("hot_themes") or [],
            "ladder_detail": snapshot.get("ladder_detail") or {},
            "ladder_summary": snapshot.get("ladder") or {},
            "hotmoney": snapshot.get("hotmoney") if isinstance(snapshot.get("hotmoney"), dict) else {},
            "sectors": snapshot.get("sectors") or [],
            "news": (snapshot.get("news") or snapshot.get("focus_news") or [])[:8],
            "ai_summary": _format_ai_summary(snapshot.get("ai_summary")),
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
        },
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
