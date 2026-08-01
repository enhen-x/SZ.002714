# -*- coding: utf-8 -*-
"""
宏观经济分析 — 牧原股份 (SZ.002714)
证券分析八步流程 · 第1步：宏观经济评述

数据源：
  - 东方财富: GDP / CPI / PPI / PMI / LPR / M2 / 社会消费品零售总额
  - 金十数据: SHIBOR
  - 缓存猪周期数据: 生猪价格(周度) / 驱动因子(月度) / 全国生猪产能(年度)

本机网络环境对多个数据源有 SSL 限制（soozhu、yangzhu.vip、sina 等），
猪周期数据从 git 历史恢复上一轮流水线的缓存。
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------- 路径配置
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MACRO_DIR = DATA_DIR / "macro"
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "宏观经济分析报告.html"
MANIFEST_PATH = REPORTS_DIR / "宏观经济数据清单.json"

CACHED_PIG_FILES = [
    "全国生猪产能.csv",
    "生猪价格_历史.csv",
    "生猪价格_季度.csv",
    "生猪价格_数据说明.json",
    "猪周期驱动因子_月度.csv",
    "生猪期货远期曲线.csv",
]

# 报告主题色（与牧原红对应）
COLORS = {
    "red": "#c0392b",
    "dark_red": "#922b21",
    "blue": "#2980b9",
    "green": "#27ae60",
    "gray": "#95a5a6",
    "orange": "#e67e22",
    "purple": "#8e44ad",
}

# 当前日期标记
TODAY_STR = datetime.now().strftime("%Y-%m-%d")

# ==================== 手工补充数据（脚本拉取受限，来源见备注） ====================
# 能繁母猪存栏补充：官方月度监测源（soozhu/统计局直连）被 SSL 阻断，
# 补充国家统计局季度末公布数据（经农业农村部联合发布，媒体转引）
SOW_SUPPLEMENT = [
    ("2026-03-31", 3904, "国家统计局 2026Q1 季末（同比 -3.3%）"),
    ("2026-06-30", 3780, "国家统计局 2026Q2 季末（同比 -6.5%）"),
]

# 能繁母猪正常保有量历史（农业农村部官方调控目标，三次下调）：
#   2021 年起 4100 → 2024-02 下调至 3900 → 2026-05《生猪产能综合调控实施方案（2026年修订）》下调至 3750
SOW_NORMAL_HISTORY = [
    ("2021~2024-01", 4100),
    ("2024-02~2026-04", 3900),
    ("2026-05 起", 3750),
]
SOW_NORMAL = 3750  # 现行正常保有量

# 人民币汇率关键点位（中国人民银行授权公布中间价）
# 2025-12-31: 7.0288（2025 全年中间价累计升值 1596 基点 / +0.8%）
# 2026-06-30: 6.8109（2026 上半年累计升值约 3.1%）
# 2026-07-31: 6.7894（7 月单月升值 215 基点）
FX_POINTS = [
    ("2025-12-31", 7.0288, "2025 全年 +0.8%"),
    ("2026-06-30", 6.8109, "2026H1 +3.1%"),
    ("2026-07-31", 6.7894, "7 月 +215bp"),
]

# 猪肉进口（海关总署，2026-07-22 发布）
# 2026H1 猪肉 38 万吨（同比 -28.8%）；6 月 7 万吨（-23.4%）
# 含杂碎口径 2026H1 98 万吨（-14.4%），6 月 17 万吨（-10.3%）
IMPORT_PORK = {
    "h1_2026": 38.0, "h1_2025": 53.4, "h1_yoy": -28.8,
    "m6_2026": 7.0, "m6_2025": 9.1, "m6_yoy": -23.4,
    "h1_all_2026": 98.0, "h1_all_2025": 114.5, "h1_all_yoy": -14.4,
}

# 2026Q2 能繁母猪去化速度（统计局/农业农村部公布）
SOW_Q1_2026, SOW_Q2_2026 = 3904, 3780


# ---------------------------------------------------------------- 数据拉取
def fetch_with_retry(func, max_retries=3, delay=2.0, **kwargs):
    """带重试的数据拉取，避免网络抖动。"""
    for attempt in range(max_retries):
        try:
            return func(**kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  [失败] {func.__name__}: {type(e).__name__}")
                return None
            time.sleep(delay)
    return None


def restore_cached_pig_data():
    """从 git 历史恢复猪周期缓存数据（若 data/ 下缺失）。"""
    restored = []
    missing = [f for f in CACHED_PIG_FILES if not (DATA_DIR / f).exists()]
    if not missing:
        return restored
    try:
        result = subprocess.run(
            ["git", "checkout", "HEAD", "--", *[f"data/{f}" for f in missing]],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            for f in missing:
                if (DATA_DIR / f).exists():
                    restored.append(f)
        else:
            print(f"  [警告] git 恢复失败: {result.stderr[:200]}")
    except Exception as e:
        print(f"  [警告] git 恢复异常: {e}")
    return restored


def fetch_all_macro():
    """拉取所有宏观数据，返回 dict[str, DataFrame]。"""
    import akshare as ak

    data = {}
    print("== 拉取宏观经济数据 ==")

    print("1. GDP")
    df = fetch_with_retry(ak.macro_china_gdp)
    if df is not None:
        df = df.rename(
            columns={
                "季度": "日期",
                "国内生产总值-绝对值": "GDP_亿元",
                "国内生产总值-同比增长": "GDP同比_%",
            }
        )
        # 解析季度文本 -> 日期
        def parse_quarter(q):
            year = int(q[:4])
            qnum = int(q.split("第")[1][0])
            return pd.Timestamp(year=year, month=(qnum - 1) * 3 + 1, day=1)

        df["日期"] = df["日期"].map(parse_quarter)
        df = df.sort_values("日期").reset_index(drop=True)
        data["gdp"] = df

    print("2. CPI")
    df = fetch_with_retry(ak.macro_china_cpi)
    if df is not None:
        df = df.rename(
            columns={"月份": "日期", "全国-当月": "CPI当月", "全国-同比增长": "CPI同比_%"}
        )
        df["日期"] = pd.to_datetime(df["日期"], format="%Y年%m月份")
        df = df.sort_values("日期").reset_index(drop=True)
        data["cpi"] = df

    print("3. PPI")
    df = fetch_with_retry(ak.macro_china_ppi)
    if df is not None:
        df = df.rename(
            columns={"月份": "日期", "当月同比增长": "PPI同比_%"}
        )
        df["日期"] = pd.to_datetime(df["日期"], format="%Y年%m月份")
        df = df.sort_values("日期").reset_index(drop=True)
        data["ppi"] = df

    print("4. PMI")
    df = fetch_with_retry(ak.macro_china_pmi)
    if df is not None:
        df = df.rename(columns={"月份": "日期", "制造业-指数": "制造业PMI"})
        df["日期"] = pd.to_datetime(df["日期"], format="%Y年%m月份")
        df = df.sort_values("日期").reset_index(drop=True)
        data["pmi"] = df

    print("5. LPR")
    df = fetch_with_retry(ak.macro_china_lpr)
    if df is not None:
        df = df.rename(columns={"TRADE_DATE": "日期", "LPR1Y": "LPR1Y_%", "LPR5Y": "LPR5Y_%"})
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").reset_index(drop=True)
        data["lpr"] = df

    print("6. M2")
    df = fetch_with_retry(ak.macro_china_money_supply)
    if df is not None:
        df = df.rename(
            columns={
                "月份": "日期",
                "货币和准货币(M2)-数量(亿元)": "M2_亿元",
                "货币和准货币(M2)-同比增长": "M2同比_%",
                "货币(M1)-同比增长": "M1同比_%",
            }
        )
        df["日期"] = pd.to_datetime(df["日期"], format="%Y年%m月份")
        df = df.sort_values("日期").reset_index(drop=True)
        data["m2"] = df

    print("7. SHIBOR")
    df = fetch_with_retry(ak.macro_china_shibor_all)
    if df is not None:
        df = df.rename(columns={"日期": "日期", "O/N-定价": "ON_%", "3M-定价": "3M_%", "1Y-定价": "1Y_%"})
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").reset_index(drop=True)
        data["shibor"] = df

    print("8. 社会消费品零售总额")
    df = fetch_with_retry(ak.macro_china_consumer_goods_retail)
    if df is not None:
        df = df.rename(columns={"月份": "日期", "当月": "社零_亿元", "同比增长": "社零同比_%"})
        df["日期"] = pd.to_datetime(df["日期"], format="%Y年%m月份")
        df = df.sort_values("日期").reset_index(drop=True)
        data["consumption"] = df

    return data


def load_cached_pig_data():
    """加载猪周期缓存数据（来自 git 历史）。"""
    pig = {}

    # 生猪价格周度历史
    p = DATA_DIR / "生猪价格_历史.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").reset_index(drop=True)
        pig["hog_weekly"] = df

    # 猪周期驱动因子（月度：生猪/仔猪/母猪价格、猪粮比、玉米、豆粕）
    p = DATA_DIR / "猪周期驱动因子_月度.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["月份"] = pd.to_datetime(df["月份"])
        df = df.sort_values("月份").reset_index(drop=True)
        pig["drivers"] = df

    # 全国生猪产能（年度：能繁母猪、出栏）
    p = DATA_DIR / "全国生猪产能.csv"
    if p.exists():
        df = pd.read_csv(p)
        pig["capacity"] = df

    # 数据说明
    p = DATA_DIR / "生猪价格_数据说明.json"
    if p.exists():
        try:
            pig["meta"] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pig["meta"] = {}

    return pig


# ---------------------------------------------------------------- 指标计算
def latest(df, col):
    """取最新非空值。"""
    if df is None or col not in df.columns:
        return None
    s = df[col].dropna()
    return float(s.iloc[-1]) if len(s) else None


def yoy_change(df, col, months=12):
    """计算同比变化（最近值 vs 12个月前）。"""
    if df is None or col not in df.columns:
        return None
    s = df[col].dropna()
    if len(s) < 2:
        return None
    last = float(s.iloc[-1])
    prev = float(s.iloc[-12]) if len(s) > 12 else float(s.iloc[0])
    return last - prev


def build_cycle_position(drivers, capacity):
    """基于能繁母猪 + 猪价判断当前猪周期位置。"""
    pos = {}
    if drivers is not None:
        h = drivers["生猪价格_元每公斤"].dropna()
        if len(h):
            pos["current_hog_price"] = float(h.iloc[-1])
            pos["hog_price_3m_ago"] = float(h.iloc[-4]) if len(h) > 4 else None
            pos["hog_price_yoy"] = (
                (float(h.iloc[-1]) / float(h.iloc[-13]) - 1) * 100 if len(h) > 13 else None
            )
        pgr = drivers["猪粮比"].dropna()
        if len(pgr):
            pos["current_pig_grain_ratio"] = float(pgr.iloc[-1])
        corn = drivers["玉米价格_元每吨"].dropna()
        if len(corn):
            pos["current_corn"] = float(corn.iloc[-1])
            pos["corn_yoy"] = (float(corn.iloc[-1]) / float(corn.iloc[-13]) - 1) * 100 if len(corn) > 13 else None
        sm = drivers["豆粕价格_元每吨"].dropna()
        if len(sm):
            pos["current_soymeal"] = float(sm.iloc[-1])
            pos["soymeal_yoy"] = (float(sm.iloc[-1]) / float(sm.iloc[-13]) - 1) * 100 if len(sm) > 13 else None
    if capacity is not None and len(capacity):
        c = capacity.copy()
        c["日期_dt"] = pd.to_datetime(c["日期"])
        # 合并手工补充的官方季度末数据（去重：若序列已含该日期则不重复添加）
        for d, v, src in SOW_SUPPLEMENT:
            dt = pd.to_datetime(d)
            if not (c["日期_dt"] == dt).any():
                c = pd.concat([c, pd.DataFrame([{
                    "日期": d, "日期_dt": dt, "能繁母猪_万头": v, "期间": src,
                }])], ignore_index=True)
        c = c.sort_values("日期_dt")
        pos["sow_dates"] = c["日期_dt"].tolist()
        pos["sow_values"] = c["能繁母猪_万头"].tolist()
        sow = c.dropna(subset=["能繁母猪_万头"])
        if len(sow):
            pos["sow_last_date"] = sow["日期_dt"].iloc[-1].strftime("%Y-%m")
            pos["sow_last"] = float(sow["能繁母猪_万头"].iloc[-1])
        pos["sow_history"] = c
        pos["sow_normal"] = SOW_NORMAL  # 现行正常保有量（2026-05 修订）
    return pos


# ---------------------------------------------------------------- 图表
def chart_gdp_pmi(gdp, pmi):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("GDP 当季同比 (%)", "制造业 PMI (荣枯线 50)"),
        vertical_spacing=0.08, row_heights=[0.5, 0.5],
    )
    if gdp is not None:
        fig.add_trace(go.Scatter(x=gdp["日期"], y=gdp["GDP同比_%"], name="GDP同比",
                                 line=dict(color=COLORS["blue"], width=2)), row=1, col=1)
    if pmi is not None:
        fig.add_trace(go.Scatter(x=pmi["日期"], y=pmi["制造业PMI"], name="制造业PMI",
                                 line=dict(color=COLORS["red"], width=2)), row=2, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color=COLORS["gray"], row=2, col=1)
    fig.update_layout(height=460, margin=dict(l=40, r=20, t=40, b=40), showlegend=False)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_gdp_pmi")


def chart_cpi_ppi(cpi, ppi):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("CPI 同比 (%)", "PPI 同比 (%)"),
        vertical_spacing=0.08, row_heights=[0.5, 0.5],
    )
    if cpi is not None:
        fig.add_trace(go.Scatter(x=cpi["日期"], y=cpi["CPI同比_%"], name="CPI同比",
                                 line=dict(color=COLORS["blue"], width=2)), row=1, col=1)
        fig.add_hline(y=3, line_dash="dot", line_color=COLORS["gray"], row=1, col=1)
    if ppi is not None:
        fig.add_trace(go.Scatter(x=ppi["日期"], y=ppi["PPI同比_%"], name="PPI同比",
                                 line=dict(color=COLORS["orange"], width=2)), row=2, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color=COLORS["gray"], row=2, col=1)
    fig.update_layout(height=460, margin=dict(l=40, r=20, t=40, b=40), showlegend=False)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_cpi_ppi")


def chart_money(lpr, m2):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("LPR (%)", "M2 / M1 同比增速 (%)"),
        vertical_spacing=0.08, row_heights=[0.5, 0.5],
    )
    if lpr is not None:
        # LPR 2019-08 才推出，剔除 NaN 只画有效区间
        lpr1 = lpr.dropna(subset=["LPR1Y_%"])
        lpr5 = lpr.dropna(subset=["LPR5Y_%"])
        if len(lpr1):
            fig.add_trace(go.Scatter(x=lpr1["日期"], y=lpr1["LPR1Y_%"], name="LPR 1Y",
                                     line=dict(color=COLORS["blue"], width=2)), row=1, col=1)
        if len(lpr5):
            fig.add_trace(go.Scatter(x=lpr5["日期"], y=lpr5["LPR5Y_%"], name="LPR 5Y",
                                     line=dict(color=COLORS["purple"], width=2)), row=1, col=1)
    if m2 is not None:
        fig.add_trace(go.Scatter(x=m2["日期"], y=m2["M2同比_%"], name="M2同比",
                                 line=dict(color=COLORS["red"], width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=m2["日期"], y=m2["M1同比_%"], name="M1同比",
                                 line=dict(color=COLORS["green"], width=2)), row=2, col=1)
    fig.update_layout(height=460, margin=dict(l=40, r=20, t=40, b=40))
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_money")


def chart_shibor(shibor):
    fig = go.Figure()
    if shibor is not None:
        fig.add_trace(go.Scatter(x=shibor["日期"], y=shibor["ON_%"], name="隔夜",
                                 line=dict(color=COLORS["blue"], width=1.2)))
        fig.add_trace(go.Scatter(x=shibor["日期"], y=shibor["3M_%"], name="3个月",
                                 line=dict(color=COLORS["red"], width=1.8)))
        fig.add_trace(go.Scatter(x=shibor["日期"], y=shibor["1Y_%"], name="1年期",
                                 line=dict(color=COLORS["purple"], width=1.8)))
    fig.update_layout(
        title="SHIBOR 银行间同业拆借利率 (%)",
        height=380, margin=dict(l=40, r=20, t=50, b=40), showlegend=True,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_shibor")


def chart_hog_price(pig):
    """核心图：生猪价格历史 + 均线。"""
    fig = go.Figure()
    hw = pig.get("hog_weekly")
    if hw is not None:
        fig.add_trace(go.Scatter(x=hw["日期"], y=hw["价格_元每公斤"], name="生猪价格",
                                 line=dict(color=COLORS["red"], width=1.5)))
        for col, name, color in [
            ("4个月均线", "4月均线", COLORS["blue"]),
            ("12个月均线", "12月均线", COLORS["gray"]),
        ]:
            if col in hw.columns:
                s = hw[col].dropna()
                if len(s):
                    fig.add_trace(go.Scatter(x=hw.loc[s.index, "日期"], y=s, name=name,
                                             line=dict(color=color, width=1.5, dash="dot")))
    fig.update_layout(
        title="全国生猪成交均价（元/公斤，周度）",
        height=420, margin=dict(l=40, r=20, t=50, b=40), showlegend=True,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_hog")


def chart_feed_cost(drivers):
    """饲料成本：玉米 + 豆粕 + 猪粮比。

    注意：玉米/豆粕月度数据仅 2025-07 起可得（数据源 SSL 受限），
    因此独立子图限定自身时间范围，避免与猪粮比共用长时间轴造成"孤岛短线"。
    """
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("猪粮比（盈亏平衡约 6:1，数据自 2020 年起）",
                        "玉米 / 豆粕价格（元/吨，数据自 2025-07 起）"),
        vertical_spacing=0.1, row_heights=[0.5, 0.5],
    )
    if drivers is not None:
        # 子图1：猪粮比（有值范围 2020-01 ~ 2026-06，仅画有效区间）
        pgr = drivers[["月份", "猪粮比"]].dropna()
        if len(pgr):
            fig.add_trace(go.Scatter(x=pgr["月份"], y=pgr["猪粮比"], name="猪粮比",
                                     line=dict(color=COLORS["red"], width=1.8)), row=1, col=1)
            fig.add_hline(y=6, line_dash="dot", line_color=COLORS["gray"], row=1, col=1,
                          annotation_text="盈亏平衡 6:1")
            fig.update_xaxes(range=[pgr["月份"].min(), pgr["月份"].max()], row=1, col=1)

        # 子图2：玉米/豆粕（仅 2025-07 起可得，独立时间轴）
        corn = drivers[["月份", "玉米价格_元每吨"]].dropna()
        sm = drivers[["月份", "豆粕价格_元每吨"]].dropna()
        if len(corn):
            fig.add_trace(go.Scatter(x=corn["月份"], y=corn["玉米价格_元每吨"], name="玉米",
                                     line=dict(color=COLORS["orange"], width=1.8),
                                     mode="lines+markers"), row=2, col=1)
        if len(sm):
            fig.add_trace(go.Scatter(x=sm["月份"], y=sm["豆粕价格_元每吨"], name="豆粕",
                                     line=dict(color=COLORS["green"], width=1.8),
                                     mode="lines+markers"), row=2, col=1)
        both = pd.concat([corn["月份"], sm["月份"]]).drop_duplicates()
        if len(both):
            fig.update_xaxes(range=[both.min(), both.max()], row=2, col=1)
    fig.update_layout(height=520, margin=dict(l=40, r=20, t=40, b=40), showlegend=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_feed")


def chart_sow_capacity(capacity):
    """能繁母猪存栏（年度+季度/月度合并为一条连续线）。"""
    fig = go.Figure()
    if capacity is not None and len(capacity):
        c = capacity.copy()
        c["日期_dt"] = pd.to_datetime(c["日期"])
        c = c.sort_values("日期_dt")
        s = c.dropna(subset=["能繁母猪_万头"])
        if len(s):
            # 所有有效点连成一条线（年度→季度→月度），避免年度线和散点之间断裂
            fig.add_trace(go.Scatter(
                x=s["日期_dt"], y=s["能繁母猪_万头"], name="能繁母猪",
                line=dict(color=COLORS["red"], width=2), mode="lines+markers",
                marker=dict(size=6),
            ))
            # 正常保有量三条参考线（历史下调轨迹：4100 → 3900 → 3750）
            fig.add_hline(y=4100, line_dash="dot", line_color=COLORS["gray"],
                          annotation_text="保有量 4100（2024-02 前）", annotation_position="top right")
            fig.add_hline(y=3900, line_dash="dot", line_color=COLORS["orange"],
                          annotation_text="保有量 3900（2024-02 起）", annotation_position="top right")
            fig.add_hline(y=3750, line_dash="dot", line_color=COLORS["blue"],
                          annotation_text="现行保有量 3750（2026-05 修订）", annotation_position="top right")
            # 最新点标注
            last = s.iloc[-1]
            fig.add_annotation(
                x=last["日期_dt"], y=last["能繁母猪_万头"],
                text=f"{last['能繁母猪_万头']:.0f} 万头", showarrow=True, arrowhead=2,
                ax=40, ay=-30, font=dict(size=11, color=COLORS["dark_red"]))
            fig.update_xaxes(range=[s["日期_dt"].min(), s["日期_dt"].max()])
    fig.update_layout(
        title="能繁母猪存栏（万头，年度+季度/月度）",
        height=400, margin=dict(l=40, r=20, t=50, b=40), showlegend=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_sow")


def chart_consumption(consumption):
    fig = go.Figure()
    if consumption is not None:
        df = consumption.tail(120)  # 近10年
        # 每年 2 月数据缺失（春节合并发布），connectgaps 连接月度小缺口
        fig.add_trace(go.Scatter(x=df["日期"], y=df["社零同比_%"], name="社零同比",
                                 line=dict(color=COLORS["blue"], width=2),
                                 connectgaps=True))
        fig.add_hline(y=0, line_dash="dot", line_color=COLORS["gray"])
    fig.update_layout(
        title="社会消费品零售总额同比增速 (%)",
        height=380, margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_consumption")


def compute_cycle_benchmarks(pos, pig):
    """历史猪周期定量对比：能繁母猪峰谷 + 猪价谷底 + 本轮位置。

    能繁母猪序列为年度末/季度末混合频率，峰谷采用公开确认的历史极值；
    猪价谷底从周度历史数据动态计算月度均值低点。
    """
    bm = {}

    # --- 能繁母猪历史峰谷（万头，年份为年末数据） ---
    bm["sow_cycles"] = [
        # (阶段, 起点, 终点, 幅度%, 时长)
        ("2013~2019（去化）", "5132（2013 峰值）", "3080（2019 谷）", "-40.0%", "6 年，含非瘟冲击"),
        ("2019~2022（补栏）", "3080（2019 谷）", "4390（2022 峰）", "+42.5%", "3 年，超级周期"),
        ("2022~2024（去化）", "4390（2022 峰）", "4078（2024 谷）", "-7.1%", "2 年，温和去化"),
        ("2024~2025（企稳）", "4078（2024 谷）", "4043（2025-06）", "-0.9%", "企稳震荡"),
        ("2025-06~今（加速去化）", "4043（2025-06）", "3780（2026-06）", "-6.5%（进行中）", "1 年，Q2 环比 -3.2% 加速"),
    ]

    # --- 猪价历史谷底（月度均值，元/kg） ---
    hog_troughs = []
    if pig.get("hog_weekly") is not None:
        p = pig["hog_weekly"].copy()
        p["ym"] = p["日期"].dt.to_period("M")
        m = p.groupby("ym")["价格_元每公斤"].mean().dropna()
        for period in [("2015", "2015-03"), ("2018", "2018-05"), ("2022", "2022-03")]:
            y = int(period[0])
            seg = m[m.index.year == y]
            if len(seg):
                trough = seg.idxmin()
                hog_troughs.append((str(trough), round(float(seg.min()), 2)))
        # 本轮谷底：2026-04
        seg = m[m.index.year == 2026]
        if len(seg):
            trough = seg.idxmin()
            hog_troughs.append((str(trough), round(float(seg.min()), 2)))
    bm["hog_troughs"] = hog_troughs

    # --- 本轮 vs 历史：能繁母猪/猪价/猪粮比三视角 ---
    sow = pos.get("sow_last")
    pgr = pos.get("current_pig_grain_ratio")
    bm["sow_trough_compare"] = [
        ("2019 谷", "3080", "非瘟冲击（-40%）"),
        ("2024 谷", "4078", "温和去化（-7.1%）"),
        ("2026-06", f"{sow:.0f}" if sow else "—", "加速去化中（进行时）"),
    ]
    bm["pgr_note"] = (
        f"当前猪粮比 {pgr:.2f}" if pgr is not None else ""
    ) + "（<5:1 触发一级预警，6:1 盈亏平衡），为历史性低位"
    return bm


def chart_fx():
    """人民币兑美元中间价关键点位（脚本拉取受限，采用央行公布关键点）。"""
    fig = go.Figure()
    dates = [p[0] for p in FX_POINTS]
    vals = [p[1] for p in FX_POINTS]
    notes = [p[2] for p in FX_POINTS]
    fig.add_trace(go.Scatter(
        x=dates, y=vals, mode="lines+markers+text",
        line=dict(color=COLORS["blue"], width=2.5), marker=dict(size=10),
        text=[f"{v:.4f}<br><span style='font-size:11px'>{n}</span>" for v, n in zip(vals, notes)],
        textposition="top center", textfont=dict(size=11),
    ))
    fig.update_layout(
        title="人民币兑美元中间价（关键时点）— 2025 年 +0.8%，2026 年至今 +3.4%",
        height=340, margin=dict(l=40, r=20, t=50, b=40),
        yaxis=dict(title="USD/CNY 中间价", range=[6.7, 7.1]),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_fx")


def chart_import_pork():
    """猪肉进口量对比（海关总署口径：猪肉，不含杂碎）。"""
    imp = IMPORT_PORK
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["2025 上半年", "2026 上半年"], y=[imp["h1_2025"], imp["h1_2026"]],
        name="上半年累计",
        text=[f"{imp['h1_2025']:.1f} 万吨", f"{imp['h1_2026']:.1f} 万吨（{imp['h1_yoy']:+.1f}%）"],
        textposition="outside", marker_color=[COLORS["gray"], COLORS["red"]],
    ))
    fig.add_trace(go.Bar(
        x=["2025 年 6 月", "2026 年 6 月"], y=[imp["m6_2025"], imp["m6_2026"]],
        name="单月",
        text=[f"{imp['m6_2025']:.1f}", f"{imp['m6_2026']:.1f}（{imp['m6_yoy']:+.1f}%）"],
        textposition="outside", marker_color=[COLORS["gray"], COLORS["red"]],
        xaxis="x2", yaxis="y2",
    ))
    fig.update_layout(
        title="中国猪肉进口量（万吨）— 2026 上半年同比 -28.8%",
        height=360, margin=dict(l=40, r=20, t=50, b=40),
        barmode="group", showlegend=False,
        xaxis2=dict(domain=[0.55, 1.0], anchor="y2"),
        yaxis2=dict(domain=[0.0, 1.0], anchor="x2", title="单月（万吨）"),
        xaxis=dict(domain=[0.0, 0.45], title="上半年累计（万吨）"),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_import")


# ---------------------------------------------------------------- 报告
def analyze_cycle_position(pos, pig):
    """生成猪周期位置的文字判断（基于 2026-05 修订后的新调控基准）。"""
    lines = []
    if "current_hog_price" in pos:
        p = pos["current_hog_price"]
        yoy = pos.get("hog_price_yoy")
        m3 = pos.get("hog_price_3m_ago")
        mom = (p / m3 - 1) * 100 if m3 else None
        lines.append(
            f"当前全国生猪均价约 <b>{p:.2f} 元/公斤</b>（2026 年 7 月月度均值）"
            f"{f'，同比 <b>{yoy:+.1f}%</b>' if yoy is not None else ''}"
            f"{f'，较 3 个月前（{m3:.2f} 元）<b>回升 {mom:+.1f}%</b>' if mom is not None else ''}。")
    if "current_pig_grain_ratio" in pos:
        gr = pos["current_pig_grain_ratio"]
        status = "深度亏损区" if gr < 5 else ("亏损区" if gr < 6 else ("微利区" if gr < 7.5 else "盈利区"))
        lines.append(f"猪粮比 <b>{gr:.2f}</b>（2026 年 6 月），处于<b>{status}</b>"
                     f"（盈亏平衡约 6:1；5:1 以下触发一级预警）。"
                     f"历史上猪粮比低于 4 的月份极少，本轮为<b>有记录以来最深亏损区</b>。")
    if "current_corn" in pos:
        corn_yoy = pos.get("corn_yoy")
        soymeal_yoy = pos.get("soymeal_yoy")
        corn_note = f"（同比 {corn_yoy:+.1f}%）" if corn_yoy is not None else ""
        sm_note = f"（同比 {soymeal_yoy:+.1f}%）" if soymeal_yoy is not None else ""
        feed_dir = "回落" if (corn_yoy or 0) < 0 else "上行"
        lines.append(f"玉米价格 {pos['current_corn']:.0f} 元/吨{corn_note}，"
                     f"豆粕价格 {pos['current_soymeal']:.0f} 元/吨{sm_note}，"
                     f"饲料成本整体{feed_dir}。")
    if "sow_last" in pos:
        sow = pos["sow_last"]
        dt = pos["sow_last_date"]
        normal = pos.get("sow_normal", SOW_NORMAL)
        ratio = sow / normal * 100
        if 92 <= ratio <= 103:
            zone = "绿色（正常波动）区间"
        elif 88 <= ratio < 92 or 103 < ratio <= 106:
            zone = "黄色（大幅波动）预警区间"
        else:
            zone = "红色（过度波动）区间"
        lines.append(
            f"能繁母猪存栏最新为 <b>{sow:.0f} 万头</b>（{dt}，国家统计局季末数据）。"
            f"现行正常保有量为 <b>{normal} 万头</b>（2026-05《生猪产能综合调控实施方案（2026年修订）》"
            f"由 3900 下调），当前存栏为正常保有量的 <b>{ratio:.1f}%</b>，处于{zone}上沿。")
        lines.append(
            f"去化速度：2026Q2 末环比 Q1 末（{SOW_Q1_2026:.0f} 万头）下降 <b>{SOW_Q1_2026 - sow:.0f} 万头 / "
            f"{abs((sow / SOW_Q1_2026 - 1) * 100):.1f}%</b>，同比 <b>-6.5%</b>。"
            f"连续四季度环比变化 -0.2% / -1.8% / -1.4% / -3.2%，<b>去化明显加速</b>——"
            f"全行业深度亏损（单头亏损 200~350 元）叠加政策强推（\"减母猪、控二育、降体重\"三箭齐发）。")
    return lines


def build_html_report(data, pig, pos, restored, section_status):
    """组装 HTML 报告。"""
    # 各图表 HTML
    charts = {
        "gdp_pmi": chart_gdp_pmi(data.get("gdp"), data.get("pmi")) if data.get("gdp") is not None or data.get("pmi") is not None else "",
        "cpi_ppi": chart_cpi_ppi(data.get("cpi"), data.get("ppi")) if data.get("cpi") is not None or data.get("ppi") is not None else "",
        "money": chart_money(data.get("lpr"), data.get("m2")) if data.get("lpr") is not None or data.get("m2") is not None else "",
        "shibor": chart_shibor(data.get("shibor")) if data.get("shibor") is not None else "",
        "hog": chart_hog_price(pig) if pig.get("hog_weekly") is not None else "",
        "feed": chart_feed_cost(pig.get("drivers")) if pig.get("drivers") is not None else "",
        "sow": chart_sow_capacity(pig.get("capacity")) if pig.get("capacity") is not None else "",
        "consumption": chart_consumption(data.get("consumption")) if data.get("consumption") is not None else "",
        "fx": chart_fx(),
        "import": chart_import_pork(),
    }

    # 历史周期定量对比
    bm = compute_cycle_benchmarks(pos, pig)
    bench_rows = ""
    for stage, start, end, amp, dur in bm["sow_cycles"]:
        bench_rows += f"<tr><td>{stage}</td><td>{start}</td><td>{end}</td><td>{amp}</td><td>{dur}</td></tr>"
    bench_sow_table = (
        "<table><tr><th>周期阶段</th><th>起点</th><th>终点</th><th>幅度</th><th>时长/特征</th></tr>"
        f"{bench_rows}</table>"
    )
    trough_text = "、".join(f"{d} 月 {v} 元/kg" for d, v in bm.get("hog_troughs", []))

    # 最新指标卡片
    def card_value(df, col, suffix="", digits=2, unit=""):
        v = latest(df, col)
        if v is None:
            return "<span class='na'>暂无</span>"
        return f"<b>{v:,.{digits}f}{suffix}</b>{unit}"

    latest_gdp = latest(data.get("gdp"), "GDP同比_%")
    latest_pmi = latest(data.get("pmi"), "制造业PMI")
    latest_cpi = latest(data.get("cpi"), "CPI同比_%")
    latest_lpr1 = latest(data.get("lpr"), "LPR1Y_%")
    latest_m2 = latest(data.get("m2"), "M2同比_%")
    latest_hog = pos.get("current_hog_price")
    latest_pgr = pos.get("current_pig_grain_ratio")
    latest_corn = pos.get("current_corn")
    latest_soymeal = pos.get("current_soymeal")
    latest_cons = latest(data.get("consumption"), "社零同比_%")
    latest_sow = pos.get("sow_last")
    latest_sow_date = pos.get("sow_last_date", "")

    # 周期位置文字
    cycle_lines = analyze_cycle_position(pos, pig)

    # 数据源状态
    status_rows = ""
    for name, ok in section_status.items():
        cls = "ok" if ok else "warn"
        status_rows += f"<tr><td>{name}</td><td class='{cls}'>{'✓' if ok else '⚠'}</td></tr>"

    restored_note = ""
    if restored:
        restored_note = (f"<div class='note'>猪周期数据源（soozhu/yangzhu/nxin）在本机网络被 SSL 阻断，"
                         f"已从 git 历史恢复上一轮缓存数据：{', '.join(restored)}。</div>")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>宏观经济评述 — 牧原股份 (002714.SZ)</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0; background: #fff; color: #1a1a1a; font-size: 15px; line-height: 1.7; }}
  .header {{ border-bottom: 1px solid #e0e0e0; padding: 36px 40px 28px; }}
  .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; letter-spacing: 0.5px; }}
  .header .sub {{ color: #999; margin-top: 8px; font-size: 13px; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 32px 24px 80px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1px; margin: 0 0 32px; border: 1px solid #e8e8e8; }}
  .card {{ background: #fafafa; padding: 16px 18px; }}
  .card .label {{ font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
  .card b {{ font-size: 20px; font-weight: 500; color: #1a1a1a; }}
  .card .unit {{ font-size: 11px; color: #aaa; margin-left: 2px; }}
  .section {{ padding: 0; margin: 40px 0; }}
  .section h2 {{ font-size: 16px; font-weight: 600; padding-bottom: 8px; border-bottom: 1px solid #e0e0e0; margin: 0 0 16px; }}
  .section h3 {{ font-size: 14px; font-weight: 600; color: #555; margin: 18px 0 8px; }}
  .section p, .section li {{ font-size: 14px; line-height: 1.8; color: #444; }}
  .tag {{ display: inline-block; font-size: 10px; padding: 1px 6px; margin-left: 6px; vertical-align: middle; letter-spacing: 0.5px; }}
  .tag.important {{ color: #c0392b; }}
  .tag.info {{ color: #888; }}
  .note {{ background: #fafafa; border-left: 2px solid #ddd; padding: 10px 14px; font-size: 12px; color: #777; margin: 12px 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 12px 0; }}
  th, td {{ border-bottom: 1px solid #eee; padding: 8px 10px; text-align: left; }}
  th {{ font-weight: 500; color: #999; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .ok {{ color: #27ae60; }} .warn {{ color: #999; }}
  .summary-box {{ border-left: 2px solid #c0392b; padding: 12px 18px; margin: 16px 0; }}
  .summary-box h3 {{ color: #1a1a1a; font-weight: 600; }}
  .risk {{ color: #c0392b; }}
  .na {{ color: #ccc; }}
  .source {{ font-size: 11px; color: #bbb; margin-top: 4px; }}
  .source a {{ color: #999; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 32px 0; }}
</style>
</head>
<body>
<div class="header">
  <h1>宏观经济评述 — 牧原股份 (002714.SZ)</h1>
  <div class="sub">证券分析 · 第 1 步 · 报告日期 {TODAY_STR} · 数据截至 2026 年 7 月末 · v2 修订（新增 2026Q2 存栏、周期对比、汇率与进口）</div>
</div>
<div class="container">

  <div class="cards">
    <div class="card"><div class="label">GDP 同比（最新季）</div>{card_value(data.get('gdp'), 'GDP同比_%')}<span class="unit">%</span></div>
    <div class="card"><div class="label">制造业 PMI</div>{card_value(data.get('pmi'), '制造业PMI')}<span class="unit"></span></div>
    <div class="card"><div class="label">CPI 同比</div>{card_value(data.get('cpi'), 'CPI同比_%')}<span class="unit">%</span></div>
    <div class="card"><div class="label">LPR 1Y</div>{card_value(data.get('lpr'), 'LPR1Y_%')}<span class="unit">%</span></div>
    <div class="card"><div class="label">M2 同比</div>{card_value(data.get('m2'), 'M2同比_%')}<span class="unit">%</span></div>
    <div class="card"><div class="label">生猪均价</div>{f"<b>{latest_hog:.2f}</b>" if latest_hog else '<span class="na">暂无</span>'}<span class="unit">元/kg</span></div>
    <div class="card"><div class="label">猪粮比</div>{f"<b>{latest_pgr:.2f}</b>" if latest_pgr else '<span class="na">暂无</span>'}<span class="unit"></span></div>
    <div class="card"><div class="label">玉米 / 豆粕</div>{f"<b>{latest_corn:.0f}</b> / {latest_soymeal:.0f}" if latest_corn and latest_soymeal else '<span class="na">暂无</span>'}<span class="unit">元/吨</span></div>
    <div class="card"><div class="label">能繁母猪</div>{f"<b>{latest_sow:.0f}</b>" if latest_sow else '<span class="na">暂无</span>'}<span class="unit">万头（{latest_sow_date}）</span></div>
  </div>

  <div class="section">
    <h2>1. 概述与核心结论</h2>
    <p>牧原股份属于<b>周期型公司</b>，其盈利核心是「猪价 − 成本」的价差。猪价由全国生猪供需决定，受以下宏观变量驱动：</p>
    <p class="source">本报告数据来源：宏观指标 — 国家统计局 / 中国人民银行（通过 akshare 东方财富、金十数据接口拉取）；猪周期 — 行情宝/搜猪网/玄田数据（缓存自 git 历史）；汇率 — 央行中间价；进口 — 海关总署；能繁母猪 — 国家统计局+农业农村部。详见各节标注与附录。</p>
    <ul>
      <li><b>供给端（核心）</b>：能繁母猪存栏是领先指标，决定 10 个月后的出栏量与猪价</li>
      <li><b>成本端</b>：玉米、豆粕价格决定饲料成本（占完全成本 60%+）</li>
      <li><b>需求端</b>：GDP 增长与居民收入决定猪肉消费总量的长期趋势</li>
      <li><b>融资端</b>：利率环境决定牧原（资产负债率约 60%）的财务费用负担</li>
    </ul>
    {restored_note}
    <div class="summary-box">
      <h3>核心结论（v2 修订）</h3>
      <p><b>① 产能去化加速但拐点未确认</b>：能繁母猪 2026Q2 末 <b>3780 万头</b>（同比 -6.5%、环比 -3.2%），为现行正常保有量（<b>3750 万头</b>，2026-05 修订）的 100.8%，重回绿色区间上沿；<b>② 猪价 7 月现首个回升信号</b>（6 月 9.57 → 7 月 10.84 元，环比 +13.3%），但仍处历史最深亏损区（猪粮比 3.99）；<b>③ 成本端（饲料 + 汇率）与融资端均处有利环境</b>，牧原成本优势放大；<b>④ 宏观判断：短空长多</b>——周期拐点时点需 2026Q4 前持续验证。</p>
    </div>
  </div>

  <div class="section">
    <h2>2. 经济增长与需求环境</h2>
    {charts['gdp_pmi']}
    <div class="source">来源：国家统计局（季度 GDP 核算），中国物流与采购联合会/国家统计局（PMI）。通过 akshare 东方财富接口实时拉取。</div>
    <h3>对牧原的含义</h3>
    <ul>
      <li>猪肉消费与经济增长正相关但弹性较低（必需消费品）。GDP 增速的边际变化对猪价的直接影响有限，主要通过餐饮/集团消费渠道传导</li>
      <li>PMI 反映制造业景气，间接影响外出就餐与团餐需求，从而影响猪肉总需求</li>
    </ul>
  </div>

  <div class="section">
    <h2>3. 通胀环境</h2>
    {charts['cpi_ppi']}
    <div class="source">来源：国家统计局（CPI 居民消费价格、PPI 工业生产者出厂价格）。通过 akshare 东方财富接口实时拉取。</div>
    <h3>对牧原的含义</h3>
    <ul>
      <li>猪价是 CPI 猪肉分项的核心组成。猪价周期既被 CPI 反映，也反过来推动 CPI 波动——本轮猪周期下行是过去两年 CPI 低位的重要拖累</li>
      <li>PPI 低位 → 养殖投入品（饲料、兽药、建材）价格压力小，对成本端友好</li>
    </ul>
  </div>

  <div class="section">
    <h2>4. 货币与流动性</h2>
    {charts['money']}
    <div class="source">来源：中国人民银行（LPR 贷款市场报价利率、M2 货币供应量），全国银行间同业拆借中心（SHIBOR）。通过 akshare 东方财富/金十数据接口拉取。</div>
    {charts['shibor']}
    <h3>对牧原的含义</h3>
    <ul>
      <li>牧原是<b>重资产高杠杆</b>经营（固定资产 + 生物资产庞大，资产负债率约 60%），财务费用对利率高度敏感。宽松货币环境（LPR 下行）直接降低利息负担</li>
      <li>低利率环境也支持行业产能出清后的再扩张融资</li>
      <li>M2/M1 剪刀差反映资金活化程度，与实体需求景气度相关</li>
    </ul>
  </div>

  <div class="section">
    <h2>5. 猪周期供给 — 核心变量 <span class="tag important">最重要</span></h2>
    {charts['hog']}
    <div class="source">来源①：生猪价格周度历史——行情宝全国成交均价（缓存数据），通过搜猪网/玄田数据接口抓取，因本机 SSL 阻断已从 git 历史恢复。来源②：能繁母猪存栏——国家统计局季度末数据 + 农业农村部月度环比推算。2026Q1/Q2 数据为手工补充（经官方媒体公告核实）。</div>
    {charts['sow'] if charts['sow'] else ''}
    <h3>周期位置判断（现行基准：正常保有量 3750 万头）</h3>
    <ul>
      {"".join(f"<li>{l}</li>" for l in cycle_lines)}
    </ul>

    <h3>历史猪周期定量对比</h3>
    <p><b>能繁母猪峰谷（万头）</b></p>
    {bench_sow_table}
    <p><b>猪价历史谷底（月度均值）</b>：{trough_text}。本轮谷底（2026-04，9.25 元/kg）<b>低于 2018 年周期谷底（10.21 元/kg），为本轮有记录以来最深底部</b>；2022 年周期谷底为 12.23 元/kg。全行业单头亏损 200~350 元。本轮能繁去化幅度（-6.5%）虽远小于 2013~2019 轮（-40%），但官方通过<b>三次下调正常保有量</b>（4100 → 3900 → 3750）压缩"合理产能"定义，以行政 + 市场双重力量推进出清。</p>

    <div class="summary-box">
      <h3>⚠ 关键矛盾：为何"去化到位"而猪价长期不涨？</h3>
      <ol>
        <li><b>基准已变</b>：正常保有量由 4100 万头三度下调至 3750 万头——官方认为生产效率提升（单位母猪出栏更多），同等存栏意味着更多供给。以旧基准（4100）看，3990 万头似"去化到位"；以新基准（3750）看，2025 年末的 3990 万头仍超正常保有量 6.4%，<b>供给并未真正出清</b>。</li>
        <li><b>时滞</b>：猪价由约 10 个月前的能繁母猪存栏决定。2026 年的出栏对应 2025 年 4000 万头以上的高位存栏，供给仍多；2026 年加速去化的效果要到 <b>2026Q4~2027 年</b>才传导至价格。</li>
        <li><b>需求疲弱</b>：CPI 同比仅 ~1.0%、社零走弱，猪肉消费无增量支撑（见第 3、8 节）。</li>
        <li><b>政策主动压产能</b>：2026 年 6 月下旬政策加码"减母猪、控二育、降体重"三箭齐发，引导行业主动收缩。</li>
      </ol>
      <p><b>但 7 月出现首个积极信号</b>：生猪均价由 6 月 9.57 元回升至 7 月 <b>10.84 元（环比 +13.3%）</b>，对应 Q2 去化加速（-3.2%）+ 季节性旺季 + 政策收缩。去化正从"量"向"价"传导，<b>但单月反弹尚不足以确认周期拐点，需在 2026Q4 前持续观察</b>。</p>
      <p>对牧原的含义：<b>行业性亏损期对高成本产能形成出清压力，牧原作为行业成本最低的龙头（完全成本约 12-13 元/公斤）在亏损期具备更强抗风险能力</b>，且能在对手退出时逆势扩产；若 2026Q4 猪价确认回升，牧原将率先受益于量价齐升。</p>
    </div>
  </div>

  <div class="section">
    <h2>6. 饲料成本</h2>
    {charts['feed']}
    <div class="source">来源：玉米/豆粕月度价格——猪周期驱动因子缓存数据（搜猪网/玄田数据），因本机 SSL 阻断已从 git 历史恢复。数据截至 2026-07。</div>
    <h3>对牧原的含义</h3>
    <ul>
      <li>玉米、豆粕占饲料成本约 80%，饲料占完全成本约 60%，即原料价格每变动 10% 影响完全成本约 5%</li>
      <li>当前玉米、豆粕价格处于历史低位区间，<b>成本端处于有利环境</b>，有利于牧原在猪价低迷期缩小亏损、或在高价期放大利润</li>
    </ul>
  </div>

  <div class="section">
    <h2>7. 汇率与猪肉进口 <span class="tag info">新增</span></h2>
    {charts['fx']}
    <div class="source">来源：中国人民银行授权中国外汇交易中心公布的人民币汇率中间价。三点均为官方公告的公开数据。</div>
    <h3>汇率对牧原的含义</h3>
    <ul>
      <li><b>汇率 → 饲料成本传导</b>：豆粕原料大豆约 85% 依赖进口、以美元计价。人民币升值直接降低进口大豆的人民币成本，对饲料成本端构成<b>顺风</b></li>
      <li>人民币兑美元中间价 2025 年升值 0.8%，2026 年至今升值约 <b>3.4%</b>（7.0288 → 6.7894），7 月单月 +215 基点——若延续，玉米豆粕成本压力进一步缓解（当前玉米/豆粕已处低位，见第 6 节）</li>
      <li>牧原收入 100% 内销，无出口汇率折算风险；汇率主要经由饲料成本间接影响盈利</li>
    </ul>
    {charts['import']}
    <div class="source">来源：海关总署（2026-07-22 发布 2026 上半年进出口数据），经生意社/新浪财经转载。</div>
    <h3>进口对猪价的影响</h3>
    <ul>
      <li>2026 上半年猪肉进口 38 万吨（同比 <b>-28.8%</b>），6 月 7 万吨（-23.4%）；含杂碎口径上半年 98 万吨（-14.4%）</li>
      <li>进口量占全国猪肉产量（约 5500 万吨/年）不足 1.5%，<b>边际影响有限</b>；进口锐减主要反映国内猪价低迷、进口套利窗口关闭——从另一侧面印证<b>国内供给充裕</b></li>
      <li>进口下降对国内猪价构成轻微边际支撑，不改变周期方向</li>
    </ul>
  </div>

  <div class="section">
    <h2>8. 消费与收入环境</h2>
    {charts['consumption']}
    <div class="source">来源：国家统计局（社会消费品零售总额月度数据）。通过 akshare 东方财富接口实时拉取。每年 2 月数据因春节合并发布而缺失。</div>
    <h3>对牧原的含义</h3>
    <ul>
      <li>社会消费品零售总额反映整体消费景气，猪肉消费总量相对刚性，但结构上受居民收入预期影响（高价抑制消费、低价刺激消费）</li>
    </ul>
  </div>

  <div class="section">
    <h2>9. 综合宏观判断：对牧原的影响</h2>
    <p class="source">综合以上各节数据。GDP/CPI/PMI/LPR/M2/SHIBOR/社零来自国家统计局与央行公开数据（akshare 拉取）；猪周期数据来自行情宝/搜猪网缓存；汇率来自央行中间价公告；进口来自海关总署。</p>
    <table>
      <tr><th>宏观变量</th><th>当前状态</th><th>对牧原的影响</th><th>方向</th></tr>
      <tr><td>经济增长</td><td>{'GDP同比 ' + f'{latest_gdp:.1f}%' if latest_gdp is not None else '—'}</td><td>需求平稳，无显著增量</td><td class='warn'>中性</td></tr>
      <tr><td>通胀</td><td>{'CPI同比 ' + f'{latest_cpi:.1f}%' if latest_cpi is not None else '—'}</td><td>猪肉价格承压 CPI，反向制约猪价反弹</td><td class='risk'>利空</td></tr>
      <tr><td>利率环境</td><td>{'LPR 1Y ' + f'{latest_lpr1:.1f}%' if latest_lpr1 is not None else '—'}</td><td>融资成本低，利好高杠杆重资产企业</td><td style='color:#27ae60'>利好</td></tr>
      <tr><td>货币供应</td><td>{'M2同比 ' + f'{latest_m2:.1f}%' if latest_m2 is not None else '—'}</td><td>流动性宽松支持产能调整</td><td style='color:#27ae60'>利好</td></tr>
      <tr><td>猪周期供给</td><td>{f'能繁母猪 {latest_sow:.0f} 万头（{latest_sow_date}）' if latest_sow is not None else '—'}、{'猪粮比 ' + f'{latest_pgr:.2f}' if latest_pgr is not None else '—'}、{'7 月猪价 ' + f'{latest_hog:.2f}（环比+13%）' if latest_hog is not None else '—'}</td><td>去化加速中、7 月现早期回升信号；拐点待确认</td><td class='warn'>短空长多</td></tr>
      <tr><td>饲料成本</td><td>{f'玉米 {latest_corn:.0f} / 豆粕 {latest_soymeal:.0f} 元/吨' if latest_corn and latest_soymeal else '—'}</td><td>成本低位，扩大成本优势</td><td style='color:#27ae60'>利好</td></tr>
      <tr><td>汇率</td><td>中间价 6.7894（2026 年内 +3.4%）</td><td>人民币升值降低大豆进口成本</td><td style='color:#27ae60'>利好</td></tr>
      <tr><td>猪肉进口</td><td>2026H1 38 万吨（-28.8%）</td><td>进口锐减，边际支撑国内猪价</td><td style='color:#27ae60'>利好</td></tr>
      <tr><td>消费</td><td>{'社零同比 ' + f'{latest_cons:.1f}%' if latest_cons is not None else '—'}</td><td>消费弱复苏，猪肉需求刚性</td><td class='warn'>中性</td></tr>
    </table>
    <p style='font-size:13px;color:#7f8c8d'>总体：<b>成本端（饲料 + 汇率）与融资端均处有利环境，需求端平淡，核心变量是猪周期供给</b>——去化加速但拐点未确认，宏观判断为"短空长多"。</p>
  </div>

  <div class="section">
    <h2>附录：数据源状态</h2>
    <table>
      <tr><th>数据</th><th>状态</th></tr>
      {status_rows}
    </table>
    <p style='font-size:12px;color:#95a5a6'>
      数据说明：宏观数据（东财/金十）为脚本实时拉取；猪周期数据（搜猪网、行情宝、玄田数据）在本机网络被 SSL 拦截，来自上一轮流水线缓存（git 历史恢复），截至 2026-07 月末。
      能繁母猪 2026Q1/Q2 官方数据（3904 / 3780 万头）、正常保有量（3750 万头，2026-05 修订）、汇率关键点位（央行中间价）、猪肉进口（海关总署）为手工补充的公开数据，来源：国家统计局、农业农村部、中国人民银行、海关总署及官方媒体公告。
    </p>
  </div>

</div>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------- 主流程
def main():
    MACRO_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 0. 恢复缓存猪周期数据
    print("== 恢复猪周期缓存数据 ==")
    restored = restore_cached_pig_data()
    if restored:
        print(f"  已恢复: {restored}")

    # 1. 拉取宏观数据
    data = fetch_all_macro()

    # 2. 加载猪周期缓存
    pig = load_cached_pig_data()
    pos = build_cycle_position(pig.get("drivers"), pig.get("capacity"))

    # 3. 数据源状态
    section_status = {
        "GDP": data.get("gdp") is not None,
        "PMI": data.get("pmi") is not None,
        "CPI": data.get("cpi") is not None,
        "PPI": data.get("ppi") is not None,
        "LPR": data.get("lpr") is not None,
        "M2": data.get("m2") is not None,
        "SHIBOR": data.get("shibor") is not None,
        "社零": data.get("consumption") is not None,
        "生猪价格(缓存)": pig.get("hog_weekly") is not None,
        "猪周期驱动因子(缓存)": pig.get("drivers") is not None,
        "全国产能(缓存)": pig.get("capacity") is not None,
        "能繁母猪(手工补充2026Q2)": True,
        "汇率(手工补充关键点)": True,
        "猪肉进口(手工补充)": True,
    }

    # 4. 保存数据清单
    manifest = {
        "company": "牧原股份",
        "code": "002714.SZ",
        "report_date": TODAY_STR,
        "version": "v2",
        "sections": section_status,
        "restored_from_git": restored,
        "hog_price_meta": pig.get("meta", {}),
        "supplements": {
            "sow_2026q1": SOW_Q1_2026, "sow_2026q2": SOW_Q2_2026,
            "sow_normal_current": SOW_NORMAL,
            "sow_normal_history": [f"{k}: {v}万头" for k, v in SOW_NORMAL_HISTORY],
            "fx_points": [f"{d}: {v}" for d, v, _ in FX_POINTS],
            "import_pork_2026h1": f"{IMPORT_PORK['h1_2026']}万吨 ({IMPORT_PORK['h1_yoy']:+.1f}%)",
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 5. 生成报告
    print("== 生成报告 ==")
    html = build_html_report(data, pig, pos, restored, section_status)
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"  报告已生成: {REPORT_PATH}")
    print(f"  数据清单: {MANIFEST_PATH}")

    # 6. 控制台摘要
    print("\n== 关键指标摘要 ==")
    if data.get("gdp") is not None:
        print(f"  GDP同比: {latest(data['gdp'], 'GDP同比_%'):.1f}%")
    if data.get("pmi") is not None:
        print(f"  制造业PMI: {latest(data['pmi'], '制造业PMI'):.1f}")
    if data.get("cpi") is not None:
        print(f"  CPI同比: {latest(data['cpi'], 'CPI同比_%'):.1f}%")
    if data.get("lpr") is not None:
        print(f"  LPR1Y: {latest(data['lpr'], 'LPR1Y_%'):.2f}%")
    if data.get("m2") is not None:
        print(f"  M2同比: {latest(data['m2'], 'M2同比_%'):.1f}%")
    if pos.get("current_hog_price"):
        print(f"  生猪均价: {pos['current_hog_price']:.2f} 元/kg")
    if pos.get("current_pig_grain_ratio"):
        print(f"  猪粮比: {pos['current_pig_grain_ratio']:.2f}")
    if pos.get("current_corn"):
        print(f"  玉米: {pos['current_corn']:.0f} 元/吨 | 豆粕: {pos['current_soymeal']:.0f} 元/吨")
    if pos.get("sow_last"):
        print(f"  能繁母猪: {pos['sow_last']:.0f} 万头 ({pos['sow_last_date']}) | 正常保有量: {pos.get('sow_normal')} 万头")
    if pos.get("sow_history") is not None:
        sow_series = pos["sow_history"].dropna(subset=["能繁母猪_万头"])
        print(f"  能繁母猪序列点数: {len(sow_series)}（含补充 {len(SOW_SUPPLEMENT)} 点）")


if __name__ == "__main__":
    sys.exit(main())
