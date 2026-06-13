#!/usr/bin/env python3
"""一键：同步行情 → 策略扫描 → 回测 → 生成看板。"""

from __future__ import annotations

import sys

from generate_html import main as gen_html
from scanner import run_scan
from sq_logging import setup_logging
from sync_market import main as sync_market
from backtest import run_backtest

log = setup_logging("stock_quant.build")


def main() -> None:
    try:
        try:
            print(">>> 1/5 同步市场快照 (hhxg)")
            sync_market()
            print(">>> 2/5 同步板块20日资金排行")
            from sync_sector_flow import main as sync_sector_flow
            sync_sector_flow()
            print(">>> 3/5 策略扫描 + 技术指标")
        scan = run_scan()
        print(f"    扫描 {scan.get('universe_size', 0)} 只，命中 {scan.get('pick_count', 0)} 只")
        print(">>> 4/5 策略回测验证")
        bt = run_backtest(scan)
        best = (bt.get("overall") or {}).get("best_strategy")
        if best:
            print(f"    最优策略: {best.get('name')} 胜率 {best.get('win_rate')}%")
        print(">>> 5/5 生成 index.html")
        gen_html()
        print("完成。浏览器打开 stock-quant/index.html")
    except Exception:
        log.exception("build_all 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
