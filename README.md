# A 股量化选股系统

参考 [InStock (myhhub/stock)](https://github.com/myhhub/stock) 核心能力，交互界面对齐 [worldcup](https://github.com/cyzhh/worldcup-prediction) 看板风格：Python 流水线 + 内嵌 JSON 的静态 HTML 看板。

**在线看板**：https://cyzhh.github.io/stock/

**功能概览**

| 模块 | 说明 |
|------|------|
| 市场概览 | 恢恢量化日报：赚钱效应、热门题材、连板、行业资金、快讯 |
| **资金流向** | 四维度资金面复盘：吸金/失血 TOP、题材净额、涨跌对比、异动与策略 |
| 技术指标 | MACD、KDJ、RSI、BOLL、均线（纯 Python，无 TA-Lib） |
| 策略选股 | 放量上涨、均线多头、MACD 金叉、KDJ 超卖、突破平台 |
| **多因子共振** | 动能 / 量能 / 趋势 / 回调 / 反转 五维加权 + 协同加分 |
| **涨停回调** | 近 N 日涨停后缩量回踩 MA/BOLL 支撑 |
| **高动能** | 5/10 日强势涨幅 + 趋势多头 + 贴近阶段高点 |
| **K 线形态** | 61 种 TA-Lib 形态，看板可自选筛选（买入/卖出/中性） |
| 回测验证 | 胜率 + **盈亏比** + 移动止损 |

## 快速开始

```powershell
git clone https://github.com/cyzhh/stock.git
cd stock
python build_all.py
# 浏览器打开 index.html
```

一键构建并推送部署：

```powershell
.\update-and-push.ps1
```

| 命令 | 说明 |
|------|------|
| `python build_all.py` | 完整流水线 |
| `python sync_market.py` | 仅同步 hhxg 市场快照 |
| `python scanner.py` | 仅策略扫描 |
| `python backtest.py` | 仅回测 |
| `python generate_html.py` | 仅生成看板 |
| `.\update-and-push.ps1` | 构建 + git push（触发 Pages 部署） |

推送到 `main` 后，GitHub Actions 自动构建并发布到 Pages；工作日 UTC 13:00 也会定时重建。

### 首次启用 Pages（解决 404）

1. 打开 [stock → Settings → Pages](https://github.com/cyzhh/stock/settings/pages)
2. **Build and deployment → Source** 任选其一：
   - **推荐**：`Deploy from a branch` → Branch: `gh-pages` → `/ (root)` → Save
   - 或：`GitHub Actions`（需 Actions 的 deploy 任务成功）
3. 等待 1–2 分钟，访问 https://cyzhh.github.io/stock/

若仍 404，到 [Actions](https://github.com/cyzhh/stock/actions) 确认最新 workflow 是否绿色。

## 架构

```
hhxg 快照 + 东方财富 K 线
    ↓
sync_market.py  →  data/market_snapshot.json
scanner.py      →  output/scan_results.json（指标 + 策略命中）
backtest.py     →  output/backtest_report.json
generate_html.py → index.html（内嵌 JSON）
```

## 多因子模型

五维因子（权重见 `config.yaml` → `factors.weights`）：

| 因子 | 含义 |
|------|------|
| 动能 | 5/10/20 日涨幅、20 日区间位置、MACD 柱斜率 |
| 量能 | 量比、成交额、量能趋势 |
| 趋势 | 均线多头、MACD 多空 |
| 回调 | 涨停基因 + 缩量回踩 + 支撑有效 |
| 反转 | KDJ/RSI 共振区间 |

**协同加分**：当 ≥3 个因子同时 ≥55 分时，综合分额外 +8；涨停回调 + 高动能共振再 +5。

## K 线形态（61 种）

对齐 [InStock](https://github.com/myhhub/stock)：两只乌鸦、三只乌鸦、锤头、晨星、暮星、吞噬模式等共 61 种。

- **看板自选**：打开「🕯️ K线形态」Tab，勾选要关注的形态（保存在浏览器）
- **扫描配置**：编辑 `data/pattern_selection.json` 控制后端扫描哪些形态

```json
{
  "enabled": ["hammer", "engulfing", "morning_star"],
  "signal_filter": "all"
}
```

安装 TA-Lib 解锁全部 61 种（未安装时使用纯 Python 子集约 14 种）：

```powershell
pip install -r requirements-patterns.txt
# Windows 需先安装 TA-Lib C 库: https://ta-lib.org/install/
```

## 配置

- `config.yaml`：因子权重、策略阈值、回测止盈止损
- `data/watchlist.json`：自选股列表（会自动合并热门题材龙头）

## 与 InStock 的差异

本系统为**轻量学习版**：无 MySQL、无自动交易、无筹码分布/K 线形态全量移植。侧重：

1. 零/少依赖（仅 Python 标准库）
2. 与 worldcup 一致的静态看板体验
3. 对接 [恢恢量化](https://hhxg.top) 行情数据

## 免责声明

股市有风险，本系统仅供学习与研究，不构成任何投资建议。
