# -*- coding: utf-8 -*-
"""
牧原股份公司分析 — 牧原股份 (SZ.002714)
证券分析八步流程 · 第3步：公司分析

数据来源：
  - 牧原股份历年年报（2017-2025）
  - 各券商研报（2026年7-8月）
  - 中国猪业高层交流论坛 TOP20 排名
  - 公司投资者交流纪要
"""

import json
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "公司分析报告.html"
MANIFEST_PATH = REPORTS_DIR / "公司分析数据清单.json"
TODAY_STR = datetime.now().strftime("%Y-%m-%d")

# ==================== 公司硬数据 ====================

# --- 基本信息 ---
COMPANY_INFO = {
    "name": "牧原食品股份有限公司",
    "code": "002714.SZ",
    "listed": "2014-01-28（深交所）",
    "hk_listed": "2026-02-19（港交所）",
    "headquarters": "河南省南阳市",
    "employees": "约 13.3 万（2025 年末）",
    "chairman": "曹治年（2026.06 接任）",
    "president": "高曈（2026.06 接任）",
    "founder": "秦英林（终身荣誉董事长）",
    "business": "生猪养殖、屠宰加工、饲料生产、种猪育种",
}

# --- 发展历程 ---
MILESTONES = [
    (1992, "秦英林、钱瑛夫妇回乡创业，从 22 头猪起步"),
    (2000, "注册成立牧原养殖有限公司"),
    (2014, "深交所上市，募资约 8.8 亿元"),
    (2019, "非洲猪瘟冲击行业，牧原凭借生物安全优势逆势扩张"),
    (2020, "出栏量达 1,812 万头，跃居中国第一；净利润 275 亿元"),
    (2021, "出栏 4,026 万头，同比翻倍；猪价暴跌，行业进入下行周期"),
    (2022, "出栏 6,120 万头，跃居全球第一；提出「每头猪 600 元降本」目标"),
    (2023, "全行业深度亏损；牧原净亏 43 亿元，为上市以来首亏"),
    (2024, "出栏 7,160 万头，连续四年全球第一；盈利大幅回升至 179 亿"),
    (2025, "出栏 7798 万头；屠宰业务首次年度盈利；港股上市获批"),
    (2026, "港股上市（A+H）；管理层交接；越南首场投产"),
]

# --- 出栏量与市占率 ---
HOG_SALES = [
    (2017, 724, 1.0),
    (2018, 1101, 1.6),
    (2019, 1025, 1.9),
    (2020, 1812, 3.4),
    (2021, 4026, 6.0),
    (2022, 6120, 8.7),
    (2023, 6382, 8.8),
    (2024, 7160, 10.2),
    (2025, 7798, 10.8),
    ("2026H1", 3862, None),
]

# --- 营业收入与利润 ---
REVENUE_PROFIT = [
    # year, revenue(亿), net_profit(亿), hog_price(元/kg), cost(元/kg)
    (2017, 100.4, 23.66, 14.8, 12.0),
    (2018, 133.9, 5.20, 12.5, 12.0),
    (2019, 202.2, 61.14, 22.0, 13.0),
    (2020, 562.8, 274.51, 32.0, 14.0),
    (2021, 788.9, 69.04, 17.0, 15.5),
    (2022, 1248.3, 132.66, 17.5, 15.7),
    (2023, 1108.6, -42.63, 15.0, 15.0),
    (2024, 1379.5, 178.81, 16.5, 14.0),
    (2025, 1441.4, 154.87, 14.4, 12.0),
]

# --- 收入结构（2025，含内部抵消）---
REVENUE_MIX_2025 = [
    ("生猪养殖（外销）", 950, 66),
    ("屠宰肉食", 452, 31),
    ("饲料/其他（外销）", 39, 3),
    # 养殖→屠宰内部交易约 452 亿，合并抵消后总营收 1,441 亿
]

# --- 成本趋势 ---
COST_TREND = [
    (2018, 12.0),
    (2019, 13.0),
    (2020, 14.0),
    (2021, 15.5),
    (2022, 15.7),
    (2023, 15.0),
    (2024, 14.0),
    (2025, 12.0),
    ("2026H1", 11.6),
]

# --- 可比公司关键指标 ---
PEER_COMPARISON = [
    # name, 2025出栏(万头), 2025营收(亿), 2025净利(亿), 完全成本(元/kg), 模式, ROE(%)
    ("牧原股份", 7798, 1441.4, 154.9, 11.3, "自繁自养", 20.6),
    ("温氏股份", 4048, 1052.0, 108.3, 12.2, "公司+农户", 17.7),
    ("新希望", 1755, 1285.0, 32.1, 12.7, "自繁自养+农户", 6.9),
    ("正邦科技", 854, 278.0, 8.5, 13.3, "自繁自养", 5.1),
    ("天邦食品", 666, 168.0, 2.8, 13.4, "自繁自养", 2.3),
    ("神农集团", 320, 98.0, 6.2, 12.5, "自繁自养", 12.8),
    ("巨星农牧", 280, 72.0, 4.5, 11.8, "自繁自养", 11.5),
]

# --- 产能数据 ---
CAPACITY_DATA = [
    # year, 能繁(万头), 产能(万头/年), PSY, 固定资产(亿)
    (2018, 68, 1500, 24.0, 135),
    (2019, 128, 2800, 24.5, 189),
    (2020, 262, 5500, 24.0, 585),
    (2021, 283, 7000, 25.0, 890),
    (2022, 281, 7500, 26.0, 1005),
    (2023, 313, 8000, 26.5, 1086),
    (2024, 351, 8500, 26.7, 1006),
    (2025, 323, 9000, 28.3, 1006),
    ("2026Q1", 313, 9000, None, None),
]

# --- 研发投入 ---
RD_SPENDING = [
    (2018, 0.91),
    (2019, 1.12),
    (2020, 4.12),
    (2021, 8.08),
    (2022, 11.42),
    (2023, 16.58),
    (2024, 17.47),
    (2025, 16.48),
]

# --- 竞争优势评分 ---
COMPETITIVE_SCORE = [
    ("成本优势", 10, "行业最低完全成本，比第二名温氏低 0.9 元/kg，比散户低约 6 元/kg"),
    ("规模效应", 10, "出栏量全球第一，占全国 10.8%，是第二名 1.9 倍"),
    ("技术/育种", 9, "自主二元轮回育种体系、智能养殖装备 330 万套、AI 大模型部署"),
    ("全产业链整合", 9, "饲料→育种→养殖→屠宰全链条，屠宰 2025 首年盈利"),
    ("品牌价值", 5, "B2B 大宗商品，品牌溢价空间有限；屠宰品牌「牧原肉食」建设中"),
    ("数智化水平", 9, "30+ 种智能装备、AI 大模型部署 1000+ 猪场，行业绝对领先"),
    ("监管壁垒", 8, "环保+土地+防疫三重壁垒保护存量龙头，新进入者极难获批"),
    ("育种优势", 9, "独立二元轮回育种体系，种猪规模全球第一，无需外购曾祖代"),
]

# --- 管理层 ---
MANAGEMENT = [
    ("曹治年", "董事长", "49岁", "1998年加入，秦英林妻表弟，资深养殖管理专家，负责稳住核心基本盘"),
    ("高曈", "总裁/财务负责人", "32岁", "欧洲高等商学院硕士，2019年校招加入，统筹现金流与数字化"),
    ("秦牧原", "董事/屠宰业务负责人", "31岁", "秦英林之子，全权负责屠宰肉食板块"),
    ("李彦朋", "养猪生产首席运营官", "38岁", "1988年生，校招加入，负责全国养殖体系运营"),
    ("王春艳", "首席人力资源官", "32岁", "1994年生，校招加入，负责人力与组织建设"),
    ("秦英林", "终身荣誉董事长/养猪研究院院长", "61岁", "创始人，退居二线专注育种与智能养殖底层技术研发"),
]

# --- 主要风险 ---
RISKS = [
    ("猪价周期风险", "极高", "猪价低迷持续时间超预期。2026H1 均价 10.4 元/kg 低于成本，行业深度亏损。去产能速度决定周期反转时间"),
    ("大规模疫病风险", "高", "集中养殖模式下，非洲猪瘟、蓝耳病等一旦暴发可能导致区域性大规模损失"),
    ("饲料成本波动", "高", "玉米/豆粕价格上涨将推高养殖成本。大豆进口依赖度 85%，受国际价格和汇率影响"),
    ("管理层交接风险", "中", "2026年6月秦英林退休，二代团队全面接手经营。新团队磨合期处于周期低谷，考验执行力"),
    ("海外扩张风险", "中", "越南等东南亚市场政治/政策/文化差异，首个海外项目刚起步"),
    ("政策监管风险", "中", "环保政策持续收紧、产能调控目标不断下调，制约扩张空间"),
    ("债务与流动性风险", "低", "资产负债率 50.7%，有息负债 606 亿，但经营现金流稳健、港股募资补充了流动性"),
    ("ESG/碳排放风险", "低", "养殖业甲烷排放受关注，但国内碳市场尚未纳入畜牧业"),
]


# ==================== 图表函数 ====================

def chart_revenue_profit():
    """营业收入与净利润趋势。"""
    yrs = [str(r[0]) for r in REVENUE_PROFIT]
    rev = [r[1] for r in REVENUE_PROFIT]
    net = [r[2] for r in REVENUE_PROFIT]
    colors_net = ["#c0392b" if v < 0 else "#27ae60" for v in net]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=yrs, y=rev, name="营业收入（亿元）",
        marker=dict(color="#3498db", opacity=0.85),
        text=[f"{v:.0f}" for v in rev], textposition="outside",
        textfont=dict(size=10, color="#3498db"),
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=yrs, y=net, name="归母净利润（亿元）",
        mode="lines+markers",
        line=dict(color="#c0392b", width=3),
        marker=dict(size=10, color=colors_net),
    ), secondary_y=True)

    fig.update_layout(
        title="牧原股份营业收入与归母净利润（2017-2025）",
        height=420, margin=dict(l=50, r=50, t=60, b=40),
        hovermode="x unified", bargap=0.35,
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    )
    fig.update_yaxes(title="营业收入（亿元）", secondary_y=False, range=[0, max(rev) * 1.25])
    fig.update_yaxes(title="归母净利润（亿元）", secondary_y=True)
    fig.update_xaxes(tickangle=30)

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_rev_profit")


def chart_hog_sales():
    """出栏量与市占率趋势。"""
    yrs = [str(h[0]) for h in HOG_SALES]
    sales = [h[1] for h in HOG_SALES]
    share = [h[2] for h in HOG_SALES]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=yrs, y=sales, name="出栏量（万头）",
        marker=dict(color="#2c3e50", opacity=0.85),
        text=[f"{s:,}" for s in sales], textposition="outside",
        textfont=dict(size=10, color="#2c3e50"),
    ), secondary_y=False)

    # 市占率线（仅全年度有数据）
    full_yrs = [str(h[0]) for h in HOG_SALES if h[2] is not None]
    full_share = [h[2] for h in HOG_SALES if h[2] is not None]

    fig.add_trace(go.Scatter(
        x=full_yrs, y=full_share, name="全国市占率（%）",
        mode="lines+markers",
        line=dict(color="#e74c3c", width=3, dash="dot"),
        marker=dict(size=10, color="#e74c3c"),
        text=[f"{s:.1f}%" for s in full_share], textposition="top center",
    ), secondary_y=True)

    fig.update_layout(
        title="牧原股份生猪出栏量与全国市占率（2017-2026H1）",
        height=400, margin=dict(l=50, r=50, t=60, b=40),
        hovermode="x unified", bargap=0.35,
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    )
    fig.update_yaxes(title="出栏量（万头）", secondary_y=False, range=[0, max(sales) * 1.25])
    fig.update_yaxes(title="全国市占率（%）", secondary_y=True, range=[0, 14])
    fig.update_xaxes(tickangle=30)

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_hog_sales")


def chart_cost_trend():
    """完全成本趋势 + 猪价对比（正确盈亏填充）。"""
    yrs = [str(r[0]) for r in REVENUE_PROFIT]
    cost = [r[4] for r in REVENUE_PROFIT]
    price = [r[3] for r in REVENUE_PROFIT]

    yrs2 = yrs + ["2026H1"]
    cost2 = cost + [11.6]
    price2 = price + [10.4]

    # 盈亏边界数组
    loss_top = [c if c > p else None for p, c in zip(price2, cost2)]   # 亏损区间上界
    profit_top = [p if p > c else None for p, c in zip(price2, cost2)]  # 盈利区间上界

    fig = go.Figure()

    # 可见的价格线和成本线
    fig.add_trace(go.Scatter(
        x=yrs2, y=price2, name="商品猪均价",
        mode="lines+markers",
        line=dict(color="#e74c3c", width=2.5),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=yrs2, y=cost2, name="牧原完全成本",
        mode="lines+markers",
        line=dict(color="#2c3e50", width=2.5),
        marker=dict(size=8),
    ))

    # 亏损区间填充（成本 > 猪价）：下界=猪价线，上界=成本线(NaN where 盈利)
    fig.add_trace(go.Scatter(
        x=yrs2, y=price2, name="亏损基底线",
        mode="lines", line=dict(width=0), showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=yrs2, y=loss_top, name="亏损区间",
        fill='tonexty', fillcolor='rgba(231,76,60,0.18)',
        mode="lines", line=dict(width=0), showlegend=True,
    ))

    # 盈利区间填充（猪价 > 成本）：下界=成本线，上界=猪价线(NaN where 亏损)
    fig.add_trace(go.Scatter(
        x=yrs2, y=cost2, name="盈利基底线",
        mode="lines", line=dict(width=0), showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=yrs2, y=profit_top, name="盈利区间",
        fill='tonexty', fillcolor='rgba(39,174,96,0.15)',
        mode="lines", line=dict(width=0), showlegend=True,
    ))

    # 散户成本参考线
    fig.add_hline(y=16.0, line_dash="dot", line_color="#999",
                  annotation_text="行业散户成本 ~16 元", annotation_position="right",
                  annotation_font=dict(size=10, color="#999"))

    fig.update_layout(
        title="牧原完全成本 vs 生猪均价（2017-2026H1）",
        height=380, margin=dict(l=50, r=50, t=60, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    )
    fig.update_yaxes(title="元/kg", range=[8, 35])
    fig.update_xaxes(tickangle=30)

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_cost_trend")


def chart_peer_compare():
    """可比公司：出栏规模 + 成本对比（双轴）。"""
    peers_top5 = [p[0] for p in PEER_COMPARISON[:5]]
    sales_top5 = [p[1] for p in PEER_COMPARISON[:5]]
    cost_top5 = [p[4] for p in PEER_COMPARISON[:5]]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        y=peers_top5[::-1], x=sales_top5[::-1], name="出栏量（万头）",
        orientation='h',
        marker=dict(color="#3498db", opacity=0.7),
        text=[f"{v:,} 万头" for v in sales_top5[::-1]],
        textposition="outside", textfont=dict(size=10),
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        y=peers_top5[::-1], x=cost_top5[::-1],
        name="完全成本（元/kg）",
        mode="markers+text",
        marker=dict(size=18, color="#e74c3c", symbol="diamond"),
        text=[f" {c} 元" for c in cost_top5[::-1]],
        textposition="middle right", textfont=dict(size=10, color="#c0392b"),
    ), secondary_y=True)

    fig.update_layout(
        title="可比公司出栏规模与完全成本（2025）",
        height=320, margin=dict(l=90, r=90, t=50, b=30),
        hovermode="y unified",
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center"),
    )
    fig.update_layout(
        xaxis=dict(title="出栏量（万头）"),
        xaxis2=dict(title="完全成本（元/kg）", range=[10, 14.5], overlaying="x"),
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_peer")


def chart_capacity():
    """产能扩张趋势。"""
    cap_yrs = [str(c[0]) for c in CAPACITY_DATA if isinstance(c[0], int)]
    sows = [c[1] for c in CAPACITY_DATA if isinstance(c[0], int)]
    psy = [c[3] for c in CAPACITY_DATA if isinstance(c[0], int)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=cap_yrs, y=sows, name="能繁母猪存栏（万头）",
        marker=dict(color="#8e44ad", opacity=0.8),
        text=[f"{s:,}" for s in sows], textposition="outside",
        textfont=dict(size=10, color="#8e44ad"),
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=cap_yrs, y=psy, name="PSY（头/母猪/年）",
        mode="lines+markers",
        line=dict(color="#e67e22", width=3),
        marker=dict(size=8, color="#e67e22"),
        text=[f"{p:.1f}" for p in psy], textposition="top center",
    ), secondary_y=True)

    fig.update_layout(
        title="牧原股份能繁母猪存栏与生产效率（2018-2025）",
        height=380, margin=dict(l=50, r=50, t=60, b=40),
        hovermode="x unified", bargap=0.35,
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    )
    fig.update_yaxes(title="能繁母猪（万头）", secondary_y=False, range=[0, max(sows) * 1.5])
    fig.update_yaxes(title="PSY", secondary_y=True, range=[20, 32])
    fig.update_xaxes(tickangle=30)

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_capacity")


def chart_rd_spending():
    """研发投入趋势。"""
    yrs = [str(r[0]) for r in RD_SPENDING]
    vals = [r[1] for r in RD_SPENDING]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=yrs, y=vals, name="研发费用（亿元）",
        marker=dict(color="#1abc9c", opacity=0.85),
        text=[f"{v:.1f}" for v in vals], textposition="outside",
        textfont=dict(size=11, color="#1abc9c"),
    ))

    fig.add_hline(y=16.48, line_dash="dot", line_color="#999",
                  annotation_text="2025年研发投入 16.48亿", annotation_position="right",
                  annotation_font=dict(size=10, color="#999"))

    fig.update_layout(
        title="牧原股份研发费用（2018-2025）",
        height=320, margin=dict(l=50, r=50, t=50, b=40),
        bargap=0.35,
    )
    fig.update_yaxes(title="亿元", range=[0, max(vals) * 1.3])
    fig.update_xaxes(tickangle=30)

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_rd")


def chart_competitive_radar():
    """竞争优势雷达图。"""
    categories = [c[0] for c in COMPETITIVE_SCORE]
    values = [c[1] for c in COMPETITIVE_SCORE]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(52,152,219,0.25)',
        line=dict(color="#3498db", width=2),
        name="牧原股份",
    ))

    # 行业平均参考线（估）
    avg = [5, 4, 4, 4, 4, 3, 5, 3]
    fig.add_trace(go.Scatterpolar(
        r=avg + [avg[0]],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(149,165,166,0.15)',
        line=dict(color="#95a5a6", width=1.5, dash="dot"),
        name="行业平均（估）",
    ))

    fig.update_layout(
        title="牧原股份竞争优势雷达图",
        height=420, margin=dict(l=30, r=30, t=60, b=30),
        polar=dict(
            radialaxis=dict(range=[0, 10], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=10)),
        ),
        legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center"),
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_radar")


# ==================== 分析文本构建 ====================

def build_competitive_table():
    rows = ""
    for name, score, desc in COMPETITIVE_SCORE:
        bar = "█" * score + "░" * (10 - score)
        rows += f"<tr><td>{name}</td><td>{bar} {score}/10</td><td style='font-size:12px'>{desc}</td></tr>"
    return rows


def build_peer_table():
    rows = ""
    for p in PEER_COMPARISON:
        cls = "style='background:#f0f9f0'" if p[0] == "牧原股份" else ""
        rows += f"<tr {cls}><td>{p[0]}</td><td>{p[1]:,}</td><td>{p[2]:.0f}</td><td>{p[3]:.1f}</td><td>{p[4]}</td><td>{p[5]}</td><td>{p[6]:.1f}%</td></tr>"
    return rows


def build_risk_table():
    rows = ""
    for name, level, desc in RISKS:
        cls = "risk" if level in ("极高", "高") else ""
        rows += f"<tr><td>{name}</td><td class='{cls}'>{level}</td><td style='font-size:12px'>{desc}</td></tr>"
    return rows


def build_milestones_html():
    lines = ""
    for yr, evt in MILESTONES:
        lines += f"<tr><td style='white-space:nowrap'>{yr}</td><td>{evt}</td></tr>"
    return lines


def build_mgmt_html():
    rows = ""
    for name, title, age, desc in MANAGEMENT:
        rows += f"<tr><td>{name}</td><td>{title}</td><td>{age}</td><td style='font-size:12px'>{desc}</td></tr>"
    return rows


# ==================== 报告生成 ====================

def build_html_report():
    charts = {
        "rev_profit": chart_revenue_profit(),
        "hog_sales": chart_hog_sales(),
        "cost_trend": chart_cost_trend(),
        "peer": chart_peer_compare(),
        "capacity": chart_capacity(),
        "rd": chart_rd_spending(),
        "radar": chart_competitive_radar(),
    }

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>公司分析 — 牧原股份 (002714.SZ)</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0; background: #fff; color: #1a1a1a; font-size: 15px; line-height: 1.7; }}
  .header {{ border-bottom: 1px solid #e0e0e0; padding: 36px 40px 28px; }}
  .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
  .header .sub {{ color: #999; margin-top: 8px; font-size: 13px; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 32px 24px 80px; }}
  .section {{ padding: 0; margin: 40px 0; }}
  .section h2 {{ font-size: 16px; font-weight: 600; padding-bottom: 8px; border-bottom: 1px solid #e0e0e0; margin: 0 0 16px; }}
  .section h3 {{ font-size: 14px; font-weight: 600; color: #555; margin: 18px 0 8px; }}
  .section p, .section li {{ font-size: 14px; line-height: 1.8; color: #444; }}
  .tag {{ display: inline-block; font-size: 10px; padding: 1px 6px; margin-left: 6px; vertical-align: middle; letter-spacing: 0.5px; color: #888; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 12px 0; }}
  th, td {{ border-bottom: 1px solid #eee; padding: 8px 10px; text-align: left; vertical-align: top; }}
  th {{ font-weight: 500; color: #999; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .risk {{ color: #c0392b; font-weight: 600; }}
  .box {{ border-left: 2px solid #3498db; padding: 12px 18px; margin: 16px 0; }}
  .box-red {{ border-left: 2px solid #c0392b; padding: 12px 18px; margin: 16px 0; }}
  .box-green {{ border-left: 2px solid #27ae60; padding: 12px 18px; margin: 16px 0; }}
  .box h3 {{ color: #1a1a1a; font-weight: 600; margin-top:0; }}
  .note {{ font-size: 12px; color: #999; }}
  .source {{ font-size: 11px; color: #bbb; margin-bottom: 8px; }}
  .score-bar {{ font-family: monospace; font-size: 12px; }}
  .col2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }}
  .highlight {{ color: #c0392b; font-weight: 600; }}
  @media (max-width: 680px) {{ .col2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>公司分析 — 牧原股份 (002714.SZ)</h1>
  <div class="sub">证券分析 · 第 3 步 · {TODAY_STR} · 数据截至 2026 年 8 月</div>
</div>
<div class="container">

  <!-- 1. 公司概述 -->
  <div class="section">
    <h2>1. 公司概述与业务描述</h2>
    <p class="source">来源：公司年报、招股说明书、券商研报</p>

    <div class="col2">
      <div>
        <table>
          <tr><th colspan="2">基本信息</th></tr>
          <tr><td>公司名称</td><td>牧原食品股份有限公司</td></tr>
          <tr><td>股票代码</td><td>002714.SZ（A股）/ 未公布（H股）</td></tr>
          <tr><td>上市日期</td><td>2014-01-28（深）/ 2026-02-19（港）</td></tr>
          <tr><td>总部</td><td>河南省南阳市</td></tr>
          <tr><td>员工人数</td><td>约 13.3 万（2025 年末）</td></tr>
          <tr><td>董事长</td><td>曹治年（2026.06 接任）</td></tr>
          <tr><td>总裁</td><td>高曈（2026.06 接任）</td></tr>
          <tr><td>创始人</td><td>秦英林（终身荣誉董事长）</td></tr>
        </table>
      </div>
      <div>
        <h3>商业模式</h3>
        <p><b>自繁自养、重资产、全产业链一体化</b></p>
        <p>覆盖 <b>饲料加工 → 种猪育种 → 生猪养殖 → 屠宰加工 → 肉食销售</b> 全链条。<b>养殖和种猪规模全球第一</b>，饲料和屠宰均进入全球前三。2025 年出栏生猪 <b>7,798 万头</b>，连续四年全球第一。</p>
        <p>区别行业主流的"公司+农户"轻资产模式，牧原坚持<b>全程自养</b>，在生物安全、品质控制和成本管理上具备独特优势。</p>
      </div>
    </div>

    <h3>发展历程</h3>
    <table>
      <tr><th>年份</th><th>里程碑事件</th></tr>
      {build_milestones_html()}
    </table>
  </div>

  <!-- 2. 产品与市场 -->
  <div class="section">
    <h2>2. 产品与市场</h2>
    <p class="source">来源：公司年报、猪业高层论坛、国家统计局</p>

    <h3>收入构成（2025 年）</h3>
    <p>2025 年总营收 <b>1,441 亿元</b>（+4.5%）。按外部收入口径：</p>
    <ul>
      <li><b>生猪养殖（外销）</b>：~950 亿元（66%）。2025 年出栏 7,798 万头中约 36% 自宰、64% 外销</li>
      <li><b>屠宰肉食</b>：452 亿元（31%）。<b>首次实现年度盈利</b>。屠宰 2,866 万头，产能利用率 98.8%</li>
      <li><b>饲料/其他（外销）</b>：~39 亿元（3%），覆盖自有养殖需求为主</li>
    </ul>
    <p class="note">注：养殖与屠宰间存在内部交易（养殖→屠宰约 452 亿元），合并报表抵消后总营收 1,441 亿元。</p>

    <h3>市场规模与市占率</h3>
    <p>2025 年全国生猪出栏 7.20 亿头，牧原市占率 <b>10.8%</b>（同比 +0.6pct）。对照美国 CR10 ≈ 60%，牧原对标 Smithfield 在美国巅峰期的 ~16% 份额，仍有显著提升空间。</p>

    {charts["hog_sales"]}

    <h3>客户集中度</h3>
    <p>生猪为大宗标准化产品，下游客户为屠宰场/肉联厂/批发商，<b>客户集中度极低</b>，不存在对单一客户的依赖。屠宰肉食业务客户拓展至商超、餐饮连锁、食品加工企业，客群分散度进一步提升。</p>

    {charts["rev_profit"]}
  </div>

  <!-- 3. 生产与分销 -->
  <div class="section">
    <h2>3. 生产与成本结构</h2>
    <p class="source">来源：公司投资者交流纪要（2025-2026）、年报</p>

    <h3>产能概况</h3>
    <p>截至 2025 年末，养殖产能约 <b>9,000 万头/年</b>，能繁母猪 323 万头（主动调减中）。2026 年资本开支控制在 100 亿元以内，停建 124 个在建猪场（涉及 1,200 万头规模），未来国内扩张节奏明显放缓，资本开支更多转向屠宰和海外。</p>

    <h3>养殖效率指标</h3>
    <table>
      <tr><th>指标</th><th>2020</th><th>2022</th><th>2024</th><th>2025</th><th>行业均值</th></tr>
      <tr><td>PSY（头/母猪/年）</td><td>24.0</td><td>26.0</td><td>26.7</td><td>28.3</td><td>~21</td></tr>
      <tr><td>MSY（头/母猪/年）</td><td>~22</td><td>~24</td><td>~25</td><td>~26</td><td>~18</td></tr>
      <tr><td>料肉比</td><td>2.9</td><td>2.8</td><td>2.72</td><td>2.65</td><td>~2.9</td></tr>
      <tr><td>全程成活率</td><td>~85%</td><td>~88%</td><td>~90%</td><td>~91%</td><td>~85%</td></tr>
      <tr><td>人均年出栏（头/人）</td><td>~150</td><td>~250</td><td>~400</td><td>~550</td><td>~200</td></tr>
    </table>
    <p class="note">来源：公司投资者交流纪要；行业均值为 Mysteel / 公开研报估算值。牧原在 PSY、料肉比、成活率、人均效率等核心指标全面领先行业。</p>

    {charts["capacity"]}

    <h3>成本结构与竞争优势</h3>
    <p>完全成本构成（约 12 元/kg）：</p>
    <ul>
      <li><b>饲料成本</b> ~60%：玉米、豆粕为主要原料。牧原通过自主饲料配方和精准饲喂系统，饲料转化效率行业领先</li>
      <li><b>人工成本</b> ~10%：智能装备（330 万套）替代人工，人均饲养效率持续提升</li>
      <li><b>折旧</b> ~10%：重资产模式的固定成本，但在产能利用率高时摊薄显著</li>
      <li><b>动保/疫苗</b> ~5%：自主育种和生物安全体系降低兽药依赖</li>
      <li><b>其他</b> ~15%：水电、运输、期间费用等</li>
    </ul>

    {charts["cost_trend"]}

    <div class="box-green">
      <h3>成本护城河：行业最低，且仍在加宽</h3>
      <p>牧原 2025 年完全成本 <b>12.0 元/kg</b>，2026H1 进一步降至 <b>11.6 元/kg</b>，比行业第二温氏低 0.9 元/kg，比上市猪企均值（12.9 元/kg）低 1.3 元/kg，比散户（~16 元/kg）低约 4-5 元/kg。</p>
      <p>最优秀场线成本已突破 <b>10.5 元/kg</b>，证明 11 元以下具备可复制性。公司 2022 年提出"每头猪 600 元降本"目标，截至 2026 年 5 月已完成 323 元。</p>
    </div>
  </div>

  <!-- 4. 竞争分析 -->
  <div class="section">
    <h2>4. 竞争分析与可比对比</h2>
    <p class="source">来源：各公司年报、猪易网、猪业高层论坛</p>

    <h3>主要竞争对手对比</h3>
    <table>
      <tr><th>企业</th><th>2025出栏（万头）</th><th>2025营收（亿）</th><th>2025净利（亿）</th><th>完全成本（元/kg）</th><th>模式</th><th>ROE</th></tr>
      {build_peer_table()}
    </table>
    <p class="note">注：非上市企业（双胞胎、正大、德康等）成本数据未公开。"—"表示未获取到可比数据。</p>

    {charts["peer"]}

    <div class="box">
      <h3>关键对比发现</h3>
      <ul>
        <li><b>规模断层</b>：牧原出栏量 = 第二名温氏 × 1.9，= 第 3-5 名之和。规模差距不是渐进的，而是代际的</li>
        <li><b>成本断层</b>：牧原 11.3 元/kg 是唯一进入 11 元区间的企业。每 1 元/kg 的成本差距 = 每头猪 110 元的利润差异 = 年化 86 亿元（按 7,798 万头计）</li>
        <li><b>模式差异</b>：温氏"公司+农户"模式扩张快但成本控制弱于自繁自养；牧原重资产模式的壁垒更高但资本需求也更大</li>
        <li><b>ROE 优势</b>：牧原 20.6% 的 ROE 显著高于同业——成本领先直接转化为资本回报领先</li>
      </ul>
    </div>

    <h3>波特五力（牧原视角）</h3>
    <table>
      <tr><th>力量</th><th>强度</th><th>对牧原的影响</th></tr>
      <tr><td>行业内竞争</td><td class="risk">激烈</td><td>价格战本质是成本战——牧原成本最低，是价格战的"最后幸存者"</td></tr>
      <tr><td>新进入者威胁</td><td>低</td><td>土地+环保+防疫+资本四重壁垒极高，新进入者几无可能</td></tr>
      <tr><td>替代品威胁</td><td>低</td><td>鸡肉边际替代有限，人造肉在中国渗透率可忽略</td></tr>
      <tr><td>供应商议价力</td><td>中</td><td>饲料原料（玉米/豆粕）为大宗商品，牧原规模大但无定价权；种猪自主育种不受制于人</td></tr>
      <tr><td>买方议价力</td><td>中</td><td>生猪为标准化商品，买家随时可换供应商——唯一的"议价"方式是比别人成本更低</td></tr>
    </table>
  </div>

  <!-- 5. 管理层与治理 -->
  <div class="section">
    <h2>5. 管理层与公司治理</h2>
    <p class="source">来源：公司公告（2026.06.01 换届公告）、新京报、财联社、界面新闻</p>

    <h3>换届：秦英林时代→二代团队经营</h3>
    <p>2026 年 6 月 1 日，创始人秦英林（61 岁）辞去董事长及总裁职务，转任<b>终身荣誉董事长</b>兼<b>牧原养猪研究院院长</b>，不再参与经营决策。此次交接并非临时决定——公司自 2021 年起即构建"双核领导人"梯队。</p>

    <h3>现任核心管理层</h3>
    <table>
      <tr><th>姓名</th><th>职务</th><th>年龄</th><th>背景与职责</th></tr>
      {build_mgmt_html()}
    </table>

    <div class="box-red">
      <h3>管理层风险提示</h3>
      <ul>
        <li><b>交接时点敏感</b>：新任团队接手即面临猪周期深度亏损（2026H1 预亏 57-67 亿），考验定力和执行力</li>
        <li><b>治理模式转型</b>：从"创始人集权"向团队决策转变，磨合期存在不确定性</li>
        <li><b>二代核心年轻</b>：高曈（32 岁）、秦牧原（31 岁）等二代高管虽经过内部培养，但独立应对大周期的经验尚待验证</li>
        <li><b>积极信号</b>：2026 年 6 月推出高管增持（4-5 亿 A 股）+ H 股回购（3-5 亿港元），表明管理层对当前估值的信心</li>
      </ul>
    </div>

    <h3>激励与利益一致性</h3>
    <ul>
      <li>创始人秦英林持股约 38%（2025年末），个人利益与公司深度绑定</li>
      <li>秦英林 2026 年 1 月解除全部股权质押，消除市场对质押风险的担忧</li>
      <li>2025 年现金分红 74 亿元（股利支付率 48%），对股东回报重视</li>
    </ul>

    <h3>股权结构（2025 年末）</h3>
    <table>
      <tr><th>股东</th><th>持股比例</th><th>说明</th></tr>
      <tr><td>秦英林</td><td>~38%</td><td>创始人、终身荣誉董事长，2026.01 全部解质押</td></tr>
      <tr><td>牧原实业集团</td><td>~13%</td><td>员工持股平台/控股公司，秦英林夫妇控制</td></tr>
      <tr><td>钱瑛</td><td>~2%</td><td>联合创始人（秦英林配偶）</td></tr>
      <tr><td>H股公众股东</td><td>~10%</td><td>2026.02 港股上市新增</td></tr>
      <tr><td>A股其他股东</td><td>~37%</td><td>含机构投资者、北向资金等</td></tr>
    </table>
    <p class="note">秦英林家族通过直接持股+牧原实业合计控制约 53% 表决权，公司控制权高度集中。2026 年 1 月秦英林解除全部股权质押，消除质押平仓风险。</p>
  </div>

  <!-- 6. 公司战略 -->
  <div class="section">
    <h2>6. 公司战略与竞争优势</h2>
    <p class="source">来源：公司年报、投资者交流、券商研报</p>

    <h3>战略一：极致降本</h3>
    <p>秦英林定调："向内求、向技术进发"。<b>每头猪 600 元降本目标</b>（2022 年提出），截至 2026 年 5 月已完成 323 元，仍有 277 元空间。路径：</p>
    <ul>
      <li>基因育种：独立二元轮回育种体系，培育生长快+抗病强的品系</li>
      <li>精准营养：饲料配方动态优化，豆粕减量替代方案</li>
      <li>智能养殖：自主研发 30 余种智能装备，每日 22 亿条养殖数据</li>
    </ul>

    {charts["rd"]}

    <h3>战略二：数智化转型</h3>
    <p>2026 年 6 月与阿里云签署战略合作，共建全球首个<b>生猪养殖大模型</b>。"牧原 AI 小牧"覆盖兽医诊断、饲料配方、育种选配等六大智能体，已在 1,000+ 猪场应用。目标从"经验养猪"转向"数据养猪"。</p>

    <h3>战略三：屠宰第二增长曲线</h3>
    <p>屠宰业务 2025 年首次年度盈利（收入 452 亿），2026H1 持续盈利（屠宰 1,723 万头，+51%）。下一步：
    提升自宰比例（2025 年仅 36.75%）→ 拓展商超/餐饮/食品加工客户 → 推进定制化高附加值产品（分割肉、预制菜）。屠宰业务能<b>平滑猪价周期波动</b>：猪价低时屠宰利润扩大，形成天然对冲。</p>

    <h3>战略四：全球化</h3>
    <p>2026 年港股上市，募资 60% 用于海外。越南首个合作智能化猪场已投产，探索菲律宾等东南亚市场。海外战略目的：① 分散国内猪周期风险；② 输出智能化养殖技术；③ 开拓新增长极。</p>

    {charts["radar"]}

    <div class="box">
      <h3>核心护城河总结</h3>
      <p>牧原的护城河不是单一维度，而是 <b>"规模 + 成本 + 技术 + 产业链"四维正向飞轮</b>：</p>
      <p>更大的规模 → 更多数据 → 更好的育种/饲料配方 → 更低的成本 → 更强的盈利能力 → 更多研发投入 → 更先进的技术 → 更低的成本 →……</p>
      <p>这个飞轮一旦启动，竞争对手难以在任何单一维度上切断。温氏可以复制"公司+农户"模式、新希望可以做大饲料规模，但没有一家同时具备牧原四维叠加的竞争优势。</p>
    </div>
  </div>

  <!-- 7. 风险因素 -->
  <div class="section">
    <h2>7. 风险因素</h2>
    <table>
      <tr><th>风险</th><th>等级</th><th>说明</th></tr>
      {build_risk_table()}
    </table>
  </div>

  <!-- 8. 公司分类确认 -->
  <div class="section">
    <h2>8. 公司分类确认</h2>

    <table>
      <tr><th>分类维度</th><th>判断</th><th>依据</th></tr>
      <tr><td>公司类型</td><td class="highlight">周期型公司</td><td>利润随猪价周期剧烈波动：2020 净利 275 亿 → 2023 亏损 43 亿 → 2024 盈利 179 亿 → 2026H1 亏损 57-67 亿</td></tr>
      <tr><td>行业地位</td><td>行业成本领袖</td><td>全球出栏第一、成本最低、规模远超第二名</td></tr>
      <tr><td>成长阶段</td><td>从高速成长转入稳健</td><td>出栏增速从 30-50% 降至 0-4%，主动放缓扩张、聚焦降本增效</td></tr>
      <tr><td>经营杠杆</td><td>高</td><td>重资产模式（固定资产 ~1006 亿），固定成本占比高，利润对价格极度敏感：猪价 ±1 元/kg → 利润 ±86 亿元</td></tr>
      <tr><td>财务健康</td><td>稳健</td><td>资产负债率 50.7%，经营现金流为净利润 1.94 倍，现金储备 143 亿</td></tr>
    </table>

    <div class="box-red">
      <h3>周期型公司分析要点（来自框架）</h3>
      <ul>
        <li>❌ <b>不用当年利润</b>作为预测起点——2026H1 的巨额亏损不代表正常盈利能力</li>
        <li>✅ 计算整个周期的<b>平均年盈利能力</b>（含 1-2 个坏年份和 3-4 个好年份）</li>
        <li>✅ 评估<b>债务偿还能力</b>——能否在整个周期偿还债务？</li>
        <li>✅ 现金储备是否足以度过衰退期？</li>
      </ul>
    </div>
  </div>

  <!-- 9. 公司质量总评 -->
  <div class="section">
    <h2>9. 公司质量评估总结</h2>

    <table>
      <tr><th>维度</th><th>评分</th><th>要点</th></tr>
      <tr><td>业务模式</td><td>9/10</td><td>自繁自养全产业链，重资产壁垒深厚。唯一弱点是重资产在周期低谷的折旧负担</td></tr>
      <tr><td>竞争地位</td><td>10/10</td><td>出栏量与成本双料冠军，领先第二名代际差距</td></tr>
      <tr><td>成本护城河</td><td>10/10</td><td>行业最低成本且仍在下降，与散户差距 4-6 元/kg，足以穿越任何周期低谷</td></tr>
      <tr><td>管理层质量</td><td>7/10</td><td>创始人刚退居二线，新团队有待周期验证；但梯队建设有规划，非仓促交接</td></tr>
      <tr><td>成长性</td><td>6/10</td><td>国内量增空间有限（产能已过剩），未来成长更多依赖屠宰、品牌肉和海外</td></tr>
      <tr><td>财务安全</td><td>8/10</td><td>负债率下降中，经营现金流充裕，港股上市补充弹药</td></tr>
      <tr><td>股东回报</td><td>7/10</td><td>2025 年分红率 48%，股息率约 1.5%；回购增持积极</td></tr>
      <tr><td><b>综合评分</b></td><td><b>7.5/10</b></td><td><b>高质量周期型龙头</b>——行业最佳公司，但管理层刚交接+成长性受限+行业周期本质决定盈利剧烈波动</td></tr>
    </table>

    <div class="box">
      <h3>投资含义</h3>
      <p>牧原股份是养猪行业中最优质的公司——成本最低、规模最大、技术最领先。但它所处的行业是高度周期性的，<b>公司的质量无法消除行业的周期</b>。在猪价低迷时，即使最好 的公司也会亏损（2026H1 预亏 57-67 亿）。</p>
      <p><b>核心投资逻辑</b>：在猪周期低谷（如当下 2026H1）以低估值买入行业最优公司，等待周期反转。牧原凭借成本优势，将在每一轮周期低谷中进一步扩大市占率——对手在"失血"，牧原在"微亏或盈亏平衡"，出清越彻底，下轮上行牧原的利润弹性越大。</p>
    </div>
  </div>

  <div class="section">
    <h2>附录：数据来源</h2>
    <ul class="note">
      <li>公司财务数据：牧原股份历年年报（2017-2025），akshare 东方财富接口拉取</li>
      <li>出栏量/成本/产能：公司年报 + 投资者交流纪要（2025-2026）</li>
      <li>管理层信息：公司公告（2026.06.01 换届公告）、新京报、财联社、界面新闻</li>
      <li>可比公司数据：各上市公司年报、猪易网、中国猪业高层交流论坛</li>
      <li>行业背景数据：行业分析报告（第 2 步）</li>
      <li>券商研报参考：中航证券、方正证券、华泰证券等 2026 年 3-7 月研报</li>
    </ul>
  </div>

</div>
</body>
</html>"""
    return html


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("== 生成公司分析报告 ==")
    html = build_html_report()
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"  报告已生成: {REPORT_PATH}")

    manifest = {
        "step": 3,
        "step_name": "公司分析",
        "company": "牧原股份",
        "code": "002714.SZ",
        "report_date": TODAY_STR,
        "data_sources": [
            "牧原股份历年年报（2017-2025）",
            "公司投资者交流纪要（2025-2026）",
            "猪业高层论坛 TOP20 排名",
            "猪易网上市猪企成本对比",
            "券商研报（中航/方正/华泰，2026年3-7月）",
            "管理层换届公告（2026.06.01）",
            "akshare 东方财富财务数据接口",
        ],
        "charts": [
            "chart_rev_profit — 营收与净利润趋势",
            "chart_hog_sales — 出栏量与市占率",
            "chart_cost_trend — 成本vs猪价",
            "chart_peer — 可比公司规模与成本",
            "chart_capacity — 产能与PSY",
            "chart_rd — 研发投入",
            "chart_radar — 竞争优势雷达图",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  数据清单已生成: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
