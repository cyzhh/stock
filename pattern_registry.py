#!/usr/bin/env python3
"""61 种 K 线形态注册表（对齐 InStock / TA-Lib）。"""

from __future__ import annotations

from typing import TypedDict


class PatternDef(TypedDict):
    id: str
    name: str
    talib: str
    category: str


PATTERN_REGISTRY: list[PatternDef] = [
    {"id": "two_crows", "name": "两只乌鸦", "talib": "CDL2CROWS", "category": "看跌"},
    {"id": "three_black_crows", "name": "三只乌鸦", "talib": "CDL3BLACKCROWS", "category": "看跌"},
    {"id": "three_inside", "name": "三内部上涨和下跌", "talib": "CDL3INSIDE", "category": "双向"},
    {"id": "three_line_strike", "name": "三线打击", "talib": "CDL3LINESTRIKE", "category": "双向"},
    {"id": "three_outside", "name": "三外部上涨和下跌", "talib": "CDL3OUTSIDE", "category": "双向"},
    {"id": "three_stars_south", "name": "南方三星", "talib": "CDL3STARSINSOUTH", "category": "看涨"},
    {"id": "three_white_soldiers", "name": "三个白兵", "talib": "CDL3WHITESOLDIERS", "category": "看涨"},
    {"id": "abandoned_baby", "name": "弃婴", "talib": "CDLABANDONEDBABY", "category": "双向"},
    {"id": "advance_block", "name": "大敌当前", "talib": "CDLADVANCEBLOCK", "category": "看跌"},
    {"id": "belt_hold", "name": "捉腰带线", "talib": "CDLBELTHOLD", "category": "双向"},
    {"id": "breakaway", "name": "脱离", "talib": "CDLBREAKAWAY", "category": "双向"},
    {"id": "closing_marubozu", "name": "收盘缺影线", "talib": "CDLCLOSINGMARUBOZU", "category": "双向"},
    {"id": "concealing_baby_swallow", "name": "藏婴吞没", "talib": "CDLCONCEALBABYSWALL", "category": "看涨"},
    {"id": "counterattack", "name": "反击线", "talib": "CDLCOUNTERATTACK", "category": "双向"},
    {"id": "dark_cloud_cover", "name": "乌云压顶", "talib": "CDLDARKCLOUDCOVER", "category": "看跌"},
    {"id": "doji", "name": "十字", "talib": "CDLDOJI", "category": "中性"},
    {"id": "doji_star", "name": "十字星", "talib": "CDLDOJISTAR", "category": "中性"},
    {"id": "dragonfly_doji", "name": "蜻蜓十字", "talib": "CDLDRAGONFLYDOJI", "category": "看涨"},
    {"id": "engulfing", "name": "吞噬模式", "talib": "CDLENGULFING", "category": "双向"},
    {"id": "evening_doji_star", "name": "十字暮星", "talib": "CDLEVENINGDOJISTAR", "category": "看跌"},
    {"id": "evening_star", "name": "暮星", "talib": "CDLEVENINGSTAR", "category": "看跌"},
    {"id": "gap_side_white", "name": "跳空并列阳线", "talib": "CDLGAPSIDESIDEWHITE", "category": "双向"},
    {"id": "gravestone_doji", "name": "墓碑十字", "talib": "CDLGRAVESTONEDOJI", "category": "看跌"},
    {"id": "hammer", "name": "锤头", "talib": "CDLHAMMER", "category": "看涨"},
    {"id": "hanging_man", "name": "上吊线", "talib": "CDLHANGINGMAN", "category": "看跌"},
    {"id": "harami", "name": "母子线", "talib": "CDLHARAMI", "category": "双向"},
    {"id": "harami_cross", "name": "十字孕线", "talib": "CDLHARAMICROSS", "category": "双向"},
    {"id": "high_wave", "name": "风高浪大线", "talib": "CDLHIGHWAVE", "category": "中性"},
    {"id": "hikkake", "name": "陷阱", "talib": "CDLHIKKAKE", "category": "双向"},
    {"id": "hikkake_mod", "name": "修正陷阱", "talib": "CDLHIKKAKEMOD", "category": "双向"},
    {"id": "homing_pigeon", "name": "家鸽", "talib": "CDLHOMINGPIGEON", "category": "看涨"},
    {"id": "identical_three_crows", "name": "三胞胎乌鸦", "talib": "CDLIDENTICAL3CROWS", "category": "看跌"},
    {"id": "in_neck", "name": "颈内线", "talib": "CDLINNECK", "category": "看跌"},
    {"id": "inverted_hammer", "name": "倒锤头", "talib": "CDLINVERTEDHAMMER", "category": "看涨"},
    {"id": "kicking", "name": "反冲形态", "talib": "CDLKICKING", "category": "双向"},
    {"id": "kicking_by_length", "name": "长缺影线反冲", "talib": "CDLKICKINGBYLENGTH", "category": "双向"},
    {"id": "ladder_bottom", "name": "梯底", "talib": "CDLLADDERBOTTOM", "category": "看涨"},
    {"id": "long_legged_doji", "name": "长脚十字", "talib": "CDLLONGLEGGEDDOJI", "category": "中性"},
    {"id": "long_line", "name": "长蜡烛", "talib": "CDLLONGLINE", "category": "双向"},
    {"id": "marubozu", "name": "光头光脚", "talib": "CDLMARUBOZU", "category": "双向"},
    {"id": "matching_low", "name": "相同低价", "talib": "CDLMATCHINGLOW", "category": "看涨"},
    {"id": "mat_hold", "name": "铺垫", "talib": "CDLMATHOLD", "category": "看涨"},
    {"id": "morning_doji_star", "name": "十字晨星", "talib": "CDLMORNINGDOJISTAR", "category": "看涨"},
    {"id": "morning_star", "name": "晨星", "talib": "CDLMORNINGSTAR", "category": "看涨"},
    {"id": "on_neck", "name": "颈上线", "talib": "CDLONNECK", "category": "看跌"},
    {"id": "piercing", "name": "刺透形态", "talib": "CDLPIERCING", "category": "看涨"},
    {"id": "rickshaw_man", "name": "黄包车夫", "talib": "CDLRICKSHAWMAN", "category": "中性"},
    {"id": "rise_fall_three_methods", "name": "上升/下降三法", "talib": "CDLRISEFALL3METHODS", "category": "双向"},
    {"id": "separating_lines", "name": "分离线", "talib": "CDLSEPARATINGLINES", "category": "双向"},
    {"id": "shooting_star", "name": "射击之星", "talib": "CDLSHOOTINGSTAR", "category": "看跌"},
    {"id": "short_line", "name": "短蜡烛", "talib": "CDLSHORTLINE", "category": "中性"},
    {"id": "spinning_top", "name": "纺锤", "talib": "CDLSPINNINGTOP", "category": "中性"},
    {"id": "stalled_pattern", "name": "停顿形态", "talib": "CDLSTALLEDPATTERN", "category": "看跌"},
    {"id": "stick_sandwich", "name": "条形三明治", "talib": "CDLSTICKSANDWICH", "category": "看涨"},
    {"id": "takuri", "name": "探水竿", "talib": "CDLTAKURI", "category": "看涨"},
    {"id": "tasuki_gap", "name": "跳空并列阴阳线", "talib": "CDLTASUKIGAP", "category": "双向"},
    {"id": "thrusting", "name": "插入", "talib": "CDLTHRUSTING", "category": "看跌"},
    {"id": "tristar", "name": "三星", "talib": "CDLTRISTAR", "category": "中性"},
    {"id": "unique_three_river", "name": "奇特三河床", "talib": "CDLUNIQUE3RIVER", "category": "看涨"},
    {"id": "upside_gap_two_crows", "name": "向上跳空两只乌鸦", "talib": "CDLUPSIDEGAP2CROWS", "category": "看跌"},
    {"id": "side_gap_three_methods", "name": "跳空三法", "talib": "CDLXSIDEGAP3METHODS", "category": "双向"},
]

PATTERN_BY_ID = {p["id"]: p for p in PATTERN_REGISTRY}
PATTERN_BY_TALIB = {p["talib"]: p for p in PATTERN_REGISTRY}


def signal_label(value: int) -> str:
    if value > 0:
        return "买入"
    if value < 0:
        return "卖出"
    return "无"
