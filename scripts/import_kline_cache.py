#!/usr/bin/env python3
"""将 curl 拉取的东方财富 JSON 转为 data/kline_cache/*.json。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kline_fetcher import _save_cache, parse_klines


def main() -> None:
    n = 0
    for path in sorted(ROOT.glob("data/em_seed_*.json")):
        code = path.stem.replace("em_seed_", "")
        raw = json.loads(path.read_text(encoding="utf-8"))
        bars = parse_klines(raw)
        if not bars:
            print(f"skip {code}: no bars")
            continue
        _save_cache(code, "weekly", bars)
        print(f"cached {code} weekly x{len(bars)}")
        n += 1
    print(f"done {n} files")


if __name__ == "__main__":
    main()
