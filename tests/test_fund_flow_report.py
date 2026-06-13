#!/usr/bin/env python3
"""资金流向报告单元测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fund_flow_report import build_fund_flow_report


def test_report_has_four_sections():
    import json
    snap = json.loads((Path(__file__).parent.parent / "data" / "market_snapshot.json").read_text(encoding="utf-8"))
    report = build_fund_flow_report(snap)
    assert len(report["sections"]) == 4
    assert report["charts"]["sector_inflow"]
    assert report["metrics"]["sentiment"] > 0


if __name__ == "__main__":
    test_report_has_four_sections()
    print("ok")
