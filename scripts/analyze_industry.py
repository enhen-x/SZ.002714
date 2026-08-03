# -*- coding: utf-8 -*-
"""
养猪行业分析 — 牧原股份 (SZ.002714)
证券分析八步流程 · 第2步：行业分析

数据来源：
  - 国家统计局：生猪出栏、猪肉产量、能繁母猪存栏
  - 中国猪业高层交流论坛：TOP20 排名
  - 各上市公司公告：出栏量、完全成本
  - 山东省畜牧兽医局/博亚和讯/猪易/中国养猪网：行业分析
  - 农业农村部：产能调控政策
"""

import json
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "行业分析报告.html"
MANIFEST_PATH = REPORTS_DIR / "行业分析数据清单.json"
TODAY_STR = datetime.now().strftime("%Y-%m-%d")

# ==================== 行业硬数据 ====================

# --- 规模数据 ---
SCALE = {
    "出栏_亿头_2025": 7.1973,
    "出栏_亿头_2024": 7.0246,  # 推算：7.1973 / 1.024
    "出栏_yoy": 2.4,
    "猪肉产量_万吨_2025": 5938,
    "猪肉产量_万吨_2024": 5706,  # 5938 - 232
    "猪肉产量_yoy": 4.1,
    "年末存栏_万头_2025": 42967,
    "年末能繁_万头_2025": 3961,
    "年末能繁_yoy": -2.9,
    "行业产值_万亿_est": 1.0,  # 约 7.2亿头 × 110kg × 14元/kg ≈ 1.1万亿
}

# --- 集中度（2025） ---
CONCENTRATION = [
    ("CR1（牧原）", 10.8, "7,798 万头"),
    ("CR5", 22.0, "约 1.58 亿头"),
    ("CR10", 30.0, "2.14 亿头"),
    ("CR20", 36.0, "2.59 亿头"),
    ("CR39（百万头以上）", 41.0, "2.95 亿头"),
]

# --- TOP10 出栏排名（2025） ---
TOP10 = [
    ("牧原股份", 7798, 8.91, "自繁自养", 11.3),
    ("温氏股份", 4048, 34.13, "公司+农户", 12.2),
    ("双胞胎集团", 2643, 49.32, "饲料+养殖", None),
    ("新希望", 1755, 6.2, "自繁自养+农户", 12.7),
    ("正大集团", 1277, None, "全产业链", None),
    ("德康农牧", 1083, None, "自繁自养", None),
    ("正邦科技", 854, 105.78, "自繁自养", 13.3),
    ("天邦食品", 666, None, "自繁自养", 13.4),
    ("海大集团", 650, None, "饲料+养殖", None),
    ("中粮家佳康", 603, 69.38, "全产业链", None),
]

# --- 完全成本对比（2025年末） ---
COST_BENCH = [
    ("牧原股份", 11.3, "行业最低，10.5~11.6"),
    ("温氏股份", 12.2, "已进入 12 元俱乐部"),
    ("新希望", 12.7, "年底目标 12.5"),
    ("正邦科技", 13.3, "较上年 15 元大幅改善"),
    ("天邦食品", 13.4, "目标 13 元以下"),
    ("上市猪企平均", 12.88, "15 家均值"),
    ("中小散户", 17.0, "成本劣势 4~6 元/kg"),
]

# --- 规模化进程 ---
SCALE_RATE = [
    (2018, 49.0),
    (2019, 53.0),
    (2020, 57.0),
    (2021, 60.0),
    (2022, 65.0),
    (2023, 68.0),
    (2024, 70.0),
    (2025, 73.0),
]

# --- 散户退出 ---
FARMER_EXIT = [
    ("2018 末", 2706),
    ("2020 末", 2260),
    ("2022 末", 2050),
    ("2024 末", 1722),
    ("2025 末", 1672),
]

# --- 生产效率 ---
EFFICIENCY = [
    ("行业 PSY（综合）", "20~26", "因口径差异大"),
    ("头部 PSY（TOP30）", "27+", "牧原达 28~30"),
    ("行业 MSY（综合）", "~18", "出栏/能繁"),
    ("美国 PSY（对比）", "~26", "中国头部已追平"),
    ("丹麦 PSY（全球最高）", "~34", "标杆"),
]

# --- 成本结构 ---
COST_STRUCTURE = [
    ("饲料", 62, "玉米、豆粕、预混料"),
    ("仔猪成本", 15, "外购仔猪占比越高此项越大"),
    ("人工", 8, "规模场自动化压低"),
    ("折旧", 6, "猪舍+设备，牧原偏高"),
    ("动保/兽药", 4, "疫苗+药物"),
    ("水电/其他", 5, "含环保处理"),
]

# --- 进入壁垒 ---
BARRIERS = [
    ("土地", "极高", "基本农田禁占、禁养区扩大、新批地近乎冻结"),
    ("资金", "极高", "单万头猪场投入 1500~2000 万，融资抵押物不足"),
    ("环保", "高", "粪污处理占成本 5~8%，环评前置审批"),
    ("防疫", "高", "非瘟常态化、全封闭管理、生物安全体系建设"),
    ("技术", "中高", "PSY 差距 5~10 头 → 成本差距 2~4 元/kg"),
    ("政策", "高", "产能调控、限批新增、环保关停"),
]

# --- 政策环境 ---
POLICY_TIMELINE = [
    ("2015", "新《环境保护法》实施 → 禁养区划定"),
    ("2018", "非洲猪瘟爆发 → 产能剧烈去化"),
    ("2019", "国务院稳产保供 → 用地/环保放松"),
    ("2021", "产能恢复 → 调控转向防止过度扩张"),
    ("2024-02", "正常保有量下调至 3900 万头"),
    ("2025", "一号文件调减产能、环保收紧"),
    ("2026-05", "正常保有量下调至 3750 万头"),
]

# --- 行业获利能力历史（年度头均利润，元/头） ---
PROFIT_HISTORY = [
    # (年份, 年均猪价_元每kg, 行业平均成本, 牧原成本, 行业头均利润, 牧原头均利润, 备注)
    (2018, 12.5, 13.0, 12.0, -55, 55, "非瘟前周期底部"),
    (2019, 22.0, 14.0, 12.5, 880, 1045, "非瘟超级周期，猪价暴涨"),
    (2020, 32.0, 16.0, 14.0, 1760, 1980, "超级周期顶峰"),
    (2021, 17.0, 18.0, 15.5, -110, 165, "产能恢复，价格暴跌"),
    (2022, 17.5, 17.5, 15.5, 0, 220, "磨底年，行业盈亏平衡"),
    (2023, 15.0, 16.0, 14.5, -110, 55, "持续低迷"),
    (2024, 16.5, 15.0, 13.5, 165, 330, "短暂回暖"),
    (2025, 15.2, 14.0, 11.3, 132, 429, "牧原成本大降，拉开差距"),
    ("2026H1", 10.5, 13.5, 11.6, -330, -121, "深度亏损，行业出清加速"),
]

# --- 年度猪肉产量与消费 ---
ANNUAL_PORK = [
    # (年份, 猪肉产量_万吨, 人均消费_kg, 生猪出栏_亿头)
    (2015, 5645, 40.3, 7.08),
    (2016, 5425, 38.4, 6.85),
    (2017, 5452, 38.5, 6.89),
    (2018, 5404, 38.1, 6.94),
    (2019, 4255, 29.9, 5.44),
    (2020, 4113, 28.8, 5.27),
    (2021, 5296, 36.9, 6.71),
    (2022, 5541, 38.5, 6.99),
    (2023, 5794, 40.1, 7.27),
    (2024, 5706, 39.5, 7.02),
    (2025, 5938, 41.0, 7.20),
    ("2026H1", 3119, None, 3.72),
]

# --- 饲料价格月度（2024-2026，关键节点） ---
FEED_PRICE = [
    # (月份, 玉米_元每吨, 豆粕_元每吨)
    ("2024-01", 2397, 3616),
    ("2024-04", 2361, 3318),
    ("2024-07", 2442, 3124),
    ("2024-10", 2225, 3109),
    ("2025-01", 2127, 3346),
    ("2025-04", 2265, 3016),
    ("2025-07", 2393, 3070),
    ("2025-10", 2171, 3079),
    ("2026-01", 2157, 3193),
    ("2026-04", 2314, 3015),
    ("2026-07", 2383, 2818),
]

# --- 生猪期货远期曲线（2026-08-03，来源：muyuan-tracker / DCE） ---
PIG_FUTURES = [
    ("LH2609", "2026-09", 10690, 143245),
    ("LH2611", "2026-11", 11600, 170522),
    ("LH2701", "2027-01", 12315, 97966),
    ("LH2703", "2027-03", 12095, 92849),
    ("LH2705", "2027-05", 13000, 40084),
    ("LH2707", "2027-07", 13640, 9418),
]

# --- 猪粮比与盈利区间 ---
PIG_GRAIN_RATIO = {
    "current": 4.41,
    "date": "2026-08-03",
    "corn_price": 2386,  # 元/吨
    "pig_price": 10.52,  # 元/kg 外三元
    "zones": [
        ("< 5:1", "重度亏损", "全行业深度亏损，产能加速去化"),
        ("5:1 ~ 5.5:1", "中度亏损", "多数企业亏损，去化进行中"),
        ("5.5:1 ~ 6:1", "轻度亏损", "成本较高企业亏损，龙头微利"),
        ("6:1 ~ 7:1", "盈亏平衡", "行业整体盈亏平衡线附近"),
        ("7:1 ~ 8:1", "盈利", "行业整体盈利"),
        ("> 8:1", "高盈利", "超级利润，产能扩张激励"),
    ],
}

# --- 仔猪价格与远期期货领先关系（近13周） ---
PIGLET_FUTURES = [
    # (采集日, 仔猪价_元每kg, 远期期货合约, 期货价_元每吨)
    ("04-30", 21.4, "LH2701", 12736),
    ("05-14", 22.0, "LH2701", 12992),
    ("06-04", 22.5, "LH2701", 13248),
    ("06-18", 23.1, "LH2703", 13503),
    ("07-09", 23.7, "LH2703", 13759),
    ("07-23", 23.5, "LH2703", 13680),
    ("08-03", 23.2, "LH2703", 12835),
]

# --- 能繁母猪季度存栏（官方，来源：农业农村部） ---
SOW_QUARTERLY = [
    ("2025-Q3", 4035, 285, -0.2),
    ("2025-Q4", 3961, 211, -1.8),
    ("2026-Q1", 3904, 154, -1.4),
    ("2026-Q2", 3780, 30, -3.2),
]

# --- 行业 PSY 趋势（平台样本） ---
PSY_TABLE = [
    (2022, 21.13, 10.72),
    (2023, 20.09, 10.42),
    (2024, 24.03, 10.98),
    (2025, 24.34, 11.25),
]

# --- 波特五力 ---
PORTER = [
    ("供应商议价能力", "低 → 中", "饲料原料大宗商品定价，但种猪/动保有一定技术溢价"),
    ("买方议价能力", "低", "生猪为标准化商品，市场价格透明，养殖端无定价权"),
    ("新进入者威胁", "极低", "土地+环保+资金+防疫四重壁垒，新批猪场同比 -47%"),
    ("替代品威胁", "中低", "禽肉（鸡肉 6.7% 增速）对猪肉有替代但不大，牛肉价高"),
    ("行业内竞争", "激烈", "CR10 30%，仍高度分散；头部凭成本碾压，散户退出加速"),
]


# ==================== 图表 ====================

def chart_concentration():
    fig = go.Figure()
    labels = [c[0] for c in CONCENTRATION]
    vals = [c[1] for c in CONCENTRATION]
    notes = [c[2] for c in CONCENTRATION]
    fig.add_trace(go.Bar(
        x=labels, y=vals,
        text=[f"{v}%<br>{n}" for v, n in zip(vals, notes)],
        textposition="outside",
        marker=dict(color=["#1a1a1a", "#555", "#777", "#999", "#bbb"]),
    ))
    fig.update_layout(
        title="生猪养殖行业市场集中度（2025）",
        height=360, margin=dict(l=40, r=20, t=50, b=80),
        yaxis=dict(title="出栏占比 %", range=[0, 50]),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_conc")


def chart_top10():
    fig = go.Figure()
    names = [t[0] for t in TOP10]
    vols = [t[1] for t in TOP10]
    yoys = [t[2] for t in TOP10]
    texts = [f"{v:,} 万头" + (f"（+{y:.0f}%）" if y else "") for v, y in zip(vols, yoys)]

    # 水平条形图: y=类别, x=数值（由下到上排列）
    rev_names = names[::-1]
    rev_vols = vols[::-1]
    rev_texts = texts[::-1]
    fig.add_trace(go.Bar(
        y=rev_names, x=rev_vols,
        orientation="h",
        text=rev_texts, textposition="outside",
        marker=dict(
            color=["#1a1a1a" if n == "牧原股份" else "#aaa" for n in rev_names],
        ),
        textfont=dict(size=11),
    ))
    fig.update_layout(
        title="TOP10 猪企 2025 年出栏量（万头）",
        height=420, margin=dict(l=130, r=120, t=50, b=40),
        xaxis=dict(title="万头"),
        showlegend=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_top10")


def chart_cost():
    fig = go.Figure()
    names = [c[0] for c in COST_BENCH]
    costs = [c[1] for c in COST_BENCH]
    colors = ["#1a1a1a" if "牧原" in n else ("#555" if "温氏" in n or "新希望" in n else "#aaa") for n in names]
    fig.add_trace(go.Bar(
        x=names, y=costs,
        text=[f"{v:.1f}" for v in costs], textposition="outside",
        marker=dict(color=colors),
        textfont=dict(size=12),
    ))
    # 散户成本线（靠右放置避免与 bar label 重叠）
    fig.add_hline(y=COST_BENCH[-1][1], line_dash="dot", line_color="#999",
                  annotation_text=f"散户成本 ~{COST_BENCH[-1][1]:.0f} 元",
                  annotation_position="right",
                  annotation_font=dict(size=10, color="#999"))
    # 2025年猪价区间
    fig.add_hrect(y0=10.5, y1=13.0, line_width=0, fillcolor="#e8e8e8", opacity=0.35,
                  annotation_text="2025 猪价区间 10.5~13.0 元/kg",
                  annotation_position="inside top left",
                  annotation_font=dict(size=10, color="#888"))
    fig.update_layout(
        title="主要猪企完全成本对比（2025 年末，元/kg）",
        height=420, margin=dict(l=40, r=60, t=50, b=80),
        yaxis=dict(title="元/kg"),
        xaxis=dict(tickangle=15),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_cost")


def chart_scale_trend():
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("规模化率（%）", "散户数量变化（万户）"),
        specs=[[{"secondary_y": False}, {"secondary_y": False}]],
    )
    # 规模化率
    yrs = [s[0] for s in SCALE_RATE]
    rates = [s[1] for s in SCALE_RATE]
    fig.add_trace(go.Scatter(
        x=yrs, y=rates, mode="lines+markers",
        line=dict(color="#1a1a1a", width=2), marker=dict(size=8),
        text=[f"{r:.0f}%" for r in rates], textposition="top center",
    ), row=1, col=1)

    # 散户数量
    fyrs = [f[0] for f in FARMER_EXIT]
    fcnt = [f[1] for f in FARMER_EXIT]
    fig.add_trace(go.Scatter(
        x=fyrs, y=fcnt, mode="lines+markers",
        line=dict(color="#c0392b", width=2), marker=dict(size=8),
        text=[f"{c:.0f} 万户" for c in fcnt], textposition="top center",
    ), row=1, col=2)

    fig.update_layout(
        height=350, margin=dict(l=40, r=20, t=50, b=40), showlegend=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_scale")


def chart_cost_structure():
    """成本结构饼图。"""
    fig = go.Figure()
    labels = [c[0] for c in COST_STRUCTURE]
    values = [c[1] for c in COST_STRUCTURE]
    fig.add_trace(go.Pie(
        labels=labels, values=values,
        textinfo="label+percent",
        marker=dict(colors=["#1a1a1a", "#444", "#888", "#aaa", "#ccc", "#ddd"]),
        hole=0.35,
    ))
    fig.update_layout(
        title="养猪完全成本结构（行业典型）",
        height=360, margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_cost_struct")


def chart_profit_cycle():
    """行业盈亏周期图：猪价 vs 成本线 + 盈亏区域。"""
    from plotly.subplots import make_subplots as ms

    fig = ms(rows=2, cols=1, shared_xaxes=True,
             row_heights=[0.6, 0.4],
             subplot_titles=("猪价 vs 成本线（元/kg）", "头均利润（元/头）"),
             vertical_spacing=0.08)

    years = [str(p[0]) for p in PROFIT_HISTORY]
    pig_prices = [p[1] for p in PROFIT_HISTORY]
    ind_costs = [p[2] for p in PROFIT_HISTORY]
    my_costs = [p[3] for p in PROFIT_HISTORY]
    ind_profit = [p[4] for p in PROFIT_HISTORY]
    my_profit = [p[5] for p in PROFIT_HISTORY]

    # 上图：猪价 + 成本线
    fig.add_trace(go.Scatter(
        x=years, y=pig_prices, mode="lines+markers",
        name="年均猪价", line=dict(color="#c0392b", width=3),
        marker=dict(size=10),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=years, y=ind_costs, mode="lines+markers",
        name="行业平均成本", line=dict(color="#888", width=2, dash="dash"),
        marker=dict(size=6),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=years, y=my_costs, mode="lines+markers",
        name="牧原完全成本", line=dict(color="#1a1a1a", width=2.5),
        marker=dict(size=8),
    ), row=1, col=1)
    # 盈利/亏损区域着色
    fig.add_trace(go.Scatter(
        x=years + years[::-1], y=pig_prices + ind_costs[::-1],
        fill="toself", fillcolor="rgba(46,204,113,0.15)", line=dict(width=0),
        name="行业盈利区", showlegend=True, hoverinfo="skip",
    ), row=1, col=1)

    # 下图：头均利润
    colors_ind = ["#27ae60" if v >= 0 else "#e74c3c" for v in ind_profit]
    colors_my = ["#1a6e35" if v >= 0 else "#a93226" for v in my_profit]
    fig.add_trace(go.Bar(
        x=years, y=ind_profit, name="行业平均头均利润",
        marker=dict(color=colors_ind, opacity=0.6),
    ), row=2, col=1)
    fig.add_trace(go.Bar(
        x=years, y=my_profit, name="牧原头均利润",
        marker=dict(color=colors_my, opacity=0.85),
    ), row=2, col=1)
    fig.add_hline(y=0, line_dash="solid", line_color="#333", line_width=1, row=2, col=1)

    fig.update_layout(
        height=520, margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    )
    fig.update_yaxes(title="元/kg", row=1, col=1)
    fig.update_yaxes(title="元/头", row=2, col=1)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_profit")


def chart_demand_trend():
    """猪肉产量与人均消费趋势（上下分栏）。"""
    yrs = [str(a[0]) for a in ANNUAL_PORK]
    prod = [a[1] for a in ANNUAL_PORK]
    per_cap = [a[2] for a in ANNUAL_PORK]
    x_idx = list(range(len(yrs)))

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.52, 0.48],
        subplot_titles=("猪肉产量（万吨）", "人均消费（kg）"),
        vertical_spacing=0.12,
    )

    # 上图：猪肉产量（柱状）
    fig.add_trace(go.Bar(
        x=x_idx, y=prod, name="猪肉产量",
        marker=dict(color=["#1a1a1a" if "2026" not in str(y) else "#888" for y in yrs]),
        text=[f"{p:,}" for p in prod], textposition="inside",
        insidetextanchor="start",
        textfont=dict(size=10, color="white"), showlegend=False,
    ), row=1, col=1)

    # 下图：人均消费（折线）
    fig.add_trace(go.Scatter(
        x=x_idx, y=per_cap, name="人均消费",
        mode="lines+markers",
        line=dict(color="#c0392b", width=2.5), marker=dict(size=8),
        showlegend=False,
    ), row=2, col=1)

    max_prod = max(prod)
    fig.update_layout(
        title="中国猪肉产量与人均消费（2015-2026H1）",
        height=480, margin=dict(l=50, r=30, t=60, b=40),
        hovermode="x unified",
        bargap=0.4,
    )
    fig.update_yaxes(title="万吨", row=1, col=1, range=[0, max_prod * 1.12])
    fig.update_yaxes(title="kg/人", row=2, col=1)

    # 两行共用相同的年份刻度
    for r in [1, 2]:
        fig.update_xaxes(
            tickvals=x_idx, ticktext=yrs, tickangle=0,
            row=r, col=1,
        )
        # 非瘟竖线
        fig.add_shape(type="line", x0=4, x1=4, y0=0, y1=1,
                      yref="y domain", row=r, col=1,
                      line=dict(dash="dot", color="#888"))

    fig.add_annotation(x=4, y=1.02, yref="paper", text="非瘟冲击",
                       showarrow=False, font=dict(size=10, color="#888"))
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_demand")


def chart_feed_price():
    """饲料原料价格趋势（玉米+豆粕）。"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    months = [f[0] for f in FEED_PRICE]
    corn = [f[1] for f in FEED_PRICE]
    soybean = [f[2] for f in FEED_PRICE]

    fig.add_trace(go.Scatter(
        x=months, y=corn, name="玉米（元/吨）", mode="lines+markers",
        line=dict(color="#1a1a1a", width=2), marker=dict(size=6),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=months, y=soybean, name="豆粕（元/吨）", mode="lines+markers",
        line=dict(color="#c0392b", width=2), marker=dict(size=6),
    ), secondary_y=True)

    fig.update_layout(
        title="饲料原料价格走势（2024-2026）",
        height=340, margin=dict(l=40, r=60, t=50, b=50),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
    )
    fig.update_yaxes(title="玉米（元/吨）", secondary_y=False)
    fig.update_yaxes(title="豆粕（元/吨）", secondary_y=True)
    # 添加豆粕下行趋势标注
    fig.add_annotation(x="2026-07", y=2818, text="豆粕创两年新低<br>利好成本端",
                       showarrow=True, arrowhead=2, ax=40, ay=-30,
                       font=dict(size=10, color="#c0392b"))
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_feed")


def chart_futures_curve():
    """生猪期货远期价格曲线。"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    contracts = [f[0] for f in PIG_FUTURES]
    prices = [f[2] for f in PIG_FUTURES]
    oi = [f[3] for f in PIG_FUTURES]

    fig.add_trace(go.Bar(
        x=contracts, y=prices, name="收盘价（元/吨）",
        marker=dict(color=["#1a1a1a" if i == 0 else "#555" if i == 1 else "#999" for i in range(len(contracts))]),
        text=[f"{p:,}" for p in prices], textposition="outside",
        textfont=dict(size=11),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=contracts, y=oi, name="持仓量（手）", mode="lines+markers",
        line=dict(color="#c0392b", width=2), marker=dict(size=6),
        yaxis="y2",
    ), secondary_y=True)

    # 标注现货价
    fig.add_hline(y=10520, line_dash="dot", line_color="#888",
                  annotation_text="现货 10,520 元/吨（外三元 10.52元/kg）",
                  annotation_position="bottom right",
                  annotation_font=dict(size=10, color="#888"))

    fig.update_layout(
        title="生猪期货远期价格曲线（2026-08-03 收盘）",
        height=380, margin=dict(l=40, r=60, t=50, b=50),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
    )
    fig.update_yaxes(title="元/吨", secondary_y=False)
    fig.update_yaxes(title="持仓量（手）", secondary_y=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_futures")


def chart_pig_grain():
    """猪粮比指标 — 色带区间 + 当前值标记。"""
    fig = go.Figure()

    current = PIG_GRAIN_RATIO["current"]
    zones_data = PIG_GRAIN_RATIO["zones"]

    # 用 add_vrect 在真实比例坐标上画色带
    zone_bounds = [
        (3.5, 5.0, "#e74c3c"),   # 重度亏损
        (5.0, 5.5, "#e67e22"),   # 中度亏损
        (5.5, 6.0, "#f1c40f"),   # 轻度亏损
        (6.0, 7.0, "#2ecc71"),   # 盈亏平衡
        (7.0, 8.0, "#27ae60"),   # 盈利
        (8.0, 10.0,"#1a6e35"),   # 高盈利
    ]
    zone_labels = ["重度亏损\n&lt;5:1", "中度\n5~5.5", "轻度\n5.5~6",
                   "盈亏平衡\n6~7", "盈利\n7~8", "高盈利\n&gt;8"]

    for (x0, x1, c), label in zip(zone_bounds, zone_labels):
        fig.add_vrect(
            x0=x0, x1=x1, fillcolor=c, opacity=0.35,
            line_width=0, layer="below",
        )
        # 区间标签放在色带中间
        fig.add_annotation(
            x=(x0 + x1) / 2, y=0.5, text=label,
            showarrow=False, font=dict(size=9, color="#333"),
            yref="paper",
        )

    # 当前值竖线
    fig.add_vline(
        x=current, line_width=3, line_color="#1a1a1a",
    )
    fig.add_annotation(
        x=current, y=0.92, text=f"▼ 当前 {current}:1",
        showarrow=False,
        font=dict(size=13, color="#c0392b", family="Microsoft YaHei"),
        bgcolor="white", borderpad=4, yref="paper",
    )

    fig.update_layout(
        title=f"猪粮比 — 当前 <b>{current}:1</b>（重度亏损区间，全行业深度亏损）",
        height=180,
        margin=dict(l=40, r=40, t=50, b=35),
        xaxis=dict(
            title="猪粮比",
            tickvals=[3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 9.0, 10.0],
            range=[3.3, 10.3],
            showgrid=True, gridcolor="#eee",
        ),
        yaxis=dict(showticklabels=False, showgrid=False, range=[0, 1]),
        plot_bgcolor="white",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_pig_grain")


def chart_sow_trend():
    """能繁母猪存栏季度变化。"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    labels = [s[0] for s in SOW_QUARTERLY]
    stock = [s[1] for s in SOW_QUARTERLY]
    change = [s[3] for s in SOW_QUARTERLY]

    fig.add_trace(go.Bar(
        x=labels, y=stock, name="能繁母猪存栏（万头）",
        marker=dict(color=["#999", "#888", "#555", "#1a1a1a"]),
        text=[f"{s:,}" for s in stock], textposition="inside",
        insidetextanchor="start",
        textfont=dict(size=11, color="white"),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=labels, y=change, name="环比变化（%）", mode="lines+markers",
        line=dict(color="#c0392b", width=2.5), marker=dict(size=10),
    ), secondary_y=True)

    # 正常保有量线
    fig.add_hline(y=3750, line_dash="dot", line_color="#888",
                  annotation_text="正常保有量 3,750 万头",
                  annotation_position="bottom right",
                  annotation_font=dict(size=10, color="#888"))

    fig.update_layout(
        title="全国能繁母猪存栏 — 季度变化",
        height=360, margin=dict(l=40, r=60, t=50, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
    )
    fig.update_yaxes(title="万头", secondary_y=False, range=[3500, 4200])
    fig.update_yaxes(title="环比 %", secondary_y=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="chart_sow")


# ==================== 分析文本 ====================

def answer_8_questions():
    """行业分析八个关键问题。"""
    return [
        ("<b>处于生命周期哪个阶段？</b>", '从成长晚期进入<b>成熟期早期</b>。规模化率 73%，增速放缓；行业从「规模扩张」转向「效率竞争」。美国规模化率约 90%，中国仍有整合空间但路径更长。'),
        ("<b>增长率高于还是低于 GDP？</b>", '产量增速（+2.4%）远<b>低于名义 GDP</b>——猪肉消费已接近天花板。长期趋势是「量稳质升」：总量不再增长，但高品质/品牌肉增速更高。'),
        ("<b>进入壁垒是什么？</b>", "土地 + 资金 + 环保 + 防疫<b>四重高壁垒</b>。新批猪场审批量同比 -47%，散户年退出 50 万户以上。壁垒的持续抬高对牧原是利好——阻挡新进入、加速散户退出。"),
        ("<b>定价权在谁手中？</b>", "生猪为标准化大宗商品，<b>养殖端完全无定价权</b>——价格由全国供需决定。唯一差异化的方向是品牌肉（如黑猪肉），但规模极小。竞争维度只有一条：<b>成本</b>。"),
        ("<b>是否受技术替代威胁？</b>", '猪肉消费<b>无显著替代风险</b>。鸡肉对猪肉有边际替代但弹性低（猪价高时转向鸡肉），人造肉/植物肉在中国渗透率可忽略。真正的「技术替代」是<b>养殖效率技术替代落后产能</b>——高效率规模场替代低效散户。'),
        ("<b>利润率在扩张还是收缩？</b>", "当前处于<b>深度亏损出清期</b>（猪粮比 4.41:1，猪价 10.52 元/kg 远低于行业成本 13.5 元）。<b>但期货远期曲线已定价利润率修复</b>：LH2701=12.32 元 → 行业微利，LH2707=13.64 元 → 头部企业利润率恢复至正常水平。关键结论：<b>当前利润率收缩越剧烈，出清越彻底 → 下一轮利润率扩张越强劲</b>。能繁 Q2 去化 -3.2% 的加速信号，是利润率周期拐点的领先指标。"),
        ("<b>是否受政府监管重大影响？</b>", "<b>是，且监管持续收紧</b>。从 2015 环保法到 2026 产能调控三次下调正常保有量（4100→3900→3750），政策方向明确：控制总量、优胜劣汰。政策是<br>行业最重要的结构性力量之一。"),
        ("<b>国际竞争如何影响？</b>", "进口量不足产量的 1.5%，<b>直接竞争可忽略</b>。间接影响：大豆进口依赖度高（85%），国际大豆价格通过豆粕传导至饲料成本；汇率波动影响进口大豆的人民币计价。跨国企业（如正大、嘉吉）在国内以本土化运营为主。"),
    ]


def porter_analysis():
    """波特五力 HTML 表格。"""
    rows = ""
    for force, level, desc in PORTER:
        cls = "risk" if level in ("激烈", "极高", "极低") else ""
        rows += f"<tr><td>{force}</td><td class='{cls}'>{level}</td><td>{desc}</td></tr>"
    return rows


# ==================== 报告 ====================

def build_html_report():
    charts = {
        "conc": chart_concentration(),
        "top10": chart_top10(),
        "cost": chart_cost(),
        "scale": chart_scale_trend(),
        "cost_struct": chart_cost_structure(),
        "profit": chart_profit_cycle(),
        "demand": chart_demand_trend(),
        "feed": chart_feed_price(),
        "futures": chart_futures_curve(),
        "pig_grain": chart_pig_grain(),
        "sow_trend": chart_sow_trend(),
    }
    q8 = answer_8_questions()
    q8_html = ""
    for q, a in q8:
        q8_html += f"<li>{q} {a}</li>"

    porter_html = porter_analysis()

    barrier_rows = ""
    for name, level, detail in BARRIERS:
        cls = "risk" if level in ("极高", "极低") else ""
        barrier_rows += f"<tr><td>{name}</td><td class='{cls}'>{level}</td><td>{detail}</td></tr>"

    policy_rows = ""
    for yr, evt in POLICY_TIMELINE:
        policy_rows += f"<tr><td>{yr}</td><td>{evt}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>养猪行业分析 — 牧原股份 (002714.SZ)</title>
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
  th, td {{ border-bottom: 1px solid #eee; padding: 8px 10px; text-align: left; }}
  th {{ font-weight: 500; color: #999; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .risk {{ color: #c0392b; }}
  .box {{ border-left: 2px solid #c0392b; padding: 12px 18px; margin: 16px 0; }}
  .box h3 {{ color: #1a1a1a; font-weight: 600; margin-top:0; }}
  .note {{ font-size: 12px; color: #999; }}
  .source {{ font-size: 11px; color: #bbb; margin-bottom: 8px; }}
  .col2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }}
  @media (max-width: 680px) {{ .col2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>养猪行业分析 — 牧原股份 (002714.SZ)</h1>
  <div class="sub">证券分析 · 第 2 步 · {TODAY_STR} · 数据截至 2025 年末 / 2026 年 8 月</div>
</div>
<div class="container">

  <div class="section">
    <h2>1. 行业概述与分类</h2>
    <p>
      生猪养殖是关系国计民生的基础农产品行业。2025 年全国生猪出栏 <b>7.1973 亿头</b>（+2.4%），
      猪肉产量 <b>5938 万吨</b>（+4.1%），产值约 <b>1 万亿元</b>。
      2026 年上半年出栏 <b>3.72 亿头</b>（+1.7%），产量 <b>3119 万吨</b>（+3.3%），能繁母猪季末 <b>3780 万头</b>（-6.5%）。
      <span class="source">（来源：国家统计局 2025 年国民经济数据 + 2026-07-15 上半年数据发布）</span>
    </p>
    <p><b>行业分类</b>：</p>
    <ul>
      <li><b>按产品</b>：农林牧渔 → 畜牧业 → 生猪养殖。终端产品为标准化大宗商品（生猪/猪肉）</li>
      <li><b>按周期性</b>：<b>强周期型行业</b>——猪价/利润随能繁母猪产能周期大幅波动，一个完整周期约 4 年</li>
      <li><b>按生命周期</b>：<b>成长晚期 → 成熟期早期</b>——规模化率 73% 且仍在提升，但总量增速放缓（猪肉消费接近天花板）</li>
      <li><b>按公司分类前瞻</b>：牧原属<b>周期型公司</b>（第 4 步财务分析将正式归类）</li>
    </ul>
    <p><b>商业模式二分法</b>：</p>
    <table>
      <tr><th></th><th>牧原模式（自繁自养）</th><th>温氏模式（公司+农户）</th></tr>
      <tr><td>资产轻重</td><td>重资产（自有猪舍）</td><td>轻资产（农户提供猪舍）</td></tr>
      <tr><td>成本控制</td><td>精细化管理，成本更低</td><td>受农户执行差异拖累，成本偏高</td></tr>
      <tr><td>扩张速度</td><td>慢（需要建猪场）</td><td>快（签约农户即可）</td></tr>
      <tr><td>生物安全</td><td>全封闭，易统一管控</td><td>分散，难统一标准</td></tr>
      <tr><td>代表企业</td><td>牧原股份</td><td>温氏股份</td></tr>
    </table>
  </div>

  <div class="section">
    <h2>2. 外部因素</h2>
    <p class="source">宏观经济数据沿用第 1 步分析结论；人口/城镇化——国家统计局年度公报；政策——农业农村部/国务院公开文件。饲料价格——搜猪网/中国饲料工业协会监测数据。</p>
    {charts['feed']}
    <p style="font-size:12px;color:#999;margin-top:4px;">饲料占养猪成本 62%，2026 年豆粕价格持续下行（7 月 2818 元/吨，创两年新低），玉米维持低位（~2380 元/吨），为行业成本下降提供了有利的原料环境。</p>
    <div class="col2">
      <div>
        <h3>宏观经济</h3>
        <ul>
          <li>GDP ~4.7%：猪肉消费弹性低，总量平稳</li>
          <li>CPI ~1.0%：低通胀压制猪价上行空间</li>
          <li>利率下行：利好重资产龙头降低财务费用</li>
          <li>人民币升值 3.4%：降低进口大豆成本</li>
        </ul>
      </div>
      <div>
        <h3>人口与社会</h3>
        <ul>
          <li>人口总量下降 → 肉类消费总量见顶</li>
          <li>老龄化 → 人均肉类消费下降</li>
          <li>消费升级 → 品牌肉/冷鲜肉/预制菜增量</li>
          <li>城镇化率 ~67% → 已过高速增长期</li>
        </ul>
      </div>
    </div>
    <div class="col2">
      <div>
        <h3>政策与监管</h3>
        <ul>
          <li>三大监管主线：环保 → 产能调控 → 防疫</li>
          <li>正常保有量 3750 万头（三度下调）</li>
          <li>新批猪场审批量同比 -47%</li>
          <li>2026"减母猪、控二育、降体重"三箭</li>
        </ul>
      </div>
      <div>
        <h3>技术变革</h3>
        <ul>
          <li>基因组育种（缩短育种周期）</li>
          <li>智能环控 + AI 疫病预警</li>
          <li>精准营养配方（降本核心）</li>
          <li>技术红利偏向头部（大数据 + 资本密集）</li>
        </ul>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>3. 需求分析</h2>
    <p class="source">来源：消费总量——国家统计局（居民收支调查）；价格弹性——学术文献综合估计；消费结构——中国畜牧业协会/行业研报。</p>
    {charts['demand']}
    <ul>
      <li><b>消费总量</b>：中国猪肉消费约 5800 万吨/年，占全球约 50%。人均消费约 41 kg/年，已接近发达国家水平，<b>总量增长空间有限</b></li>
      <li><b>消费结构</b>：家庭消费约占 60%（缓慢下降），餐饮/团餐约占 40%（与经济活动正相关）</li>
      <li><b>价格弹性</b>：猪肉需求价格弹性约 -0.5~-0.7（必需消费品，低价不显著刺激消费、高价不显著压制）</li>
      <li><b>替代品</b>：禽肉（鸡肉 2837 万吨，+6.7% 增速）是最主要替代品。猪价高时部分消费转向鸡肉，但总量替代有限（口味偏好固化）</li>
      <li><b>季节性</b>：Q4 旺季（腌腊+春节）→ Q2 淡季；月度波动约 ±15%</li>
      <li><b>长期趋势</b>：<b>"量稳质升"</b>——总消费量趋稳或微降，冷鲜肉占比提升、品牌溢价扩大、预制菜新渠道</li>
    </ul>
  </div>

  <div class="section">
    <h2>4. 供给分析</h2>
    <p class="source">来源：出栏量/存栏量——国家统计局；规模化率/散户数量——山东省畜牧兽医局 + 博亚和讯行业监测；PSY——Mysteel 农产品样本监测。</p>
    {charts['scale']}
    <h3>供给结构正在发生历史性重塑</h3>
    <ul>
      <li><b>规模化率 73%</b>（2025 年，+3pp/年），散户出栏占比降至 27%</li>
      <li><b>散户持续退出</b>：2018 年以来约 <b>1034 万户</b>退出（2706→1672 万）；2025 年单年退出<b>超 50 万户</b></li>
      <li><b>"减母不减肉"</b>：2026Q2 能繁母猪 <b>3780 万头</b>（-6.5% YoY），仅比正常保有量 3750 高 0.8%——但上半年出栏仍 +1.7%，<b>效率替代存栏</b>的趋势愈加明显</li>
      <li>母猪效率（PSY）从 2017 年的 17.38 → 2026 年约 24 头，每头母猪年均多供 7 头猪</li>
      <li><b>结论</b>：即使能繁母猪总数下降，只要头部企业维持扩张，总供给未必收缩——<b>产能出清的速度取决于散户退出 vs 大企业扩产的净效果</b>。2026Q2 能繁加速去化（-6.5%）是积极信号，但出栏增速放缓（+1.7% vs 2025全年的 +2.4%）表明供给端压力正在缓解</li>
    </ul>
  </div>

  <div class="section">
    <h2>5. 期货市场前瞻信号（🆕 来自 muyuan-tracker）</h2>
    <p class="source">来源：大连商品交易所（DCE）生猪期货 + 豆粕/菜粕期货实时行情，经 <a href="https://kisvenus.github.io/muyuan-tracker/" target="_blank">muyuan-tracker</a> 聚合展示。数据截止 2026-08-03 收盘。</p>

    <h3>生猪期货远期曲线 — 市场对未来猪价的定价</h3>
    {charts['futures']}
    <p style="font-size:12px;color:#999;margin-top:4px;">柱状为收盘价（元/吨），折线为持仓量（手）。近月 LH2609 持仓量 14.3 万手、远月 LH2707 仅 0.9 万手 — 远月流动性低，仅作辅助参考。</p>
    <table>
      <tr><th>合约</th><th>交割月</th><th>收盘价（元/吨）</th><th>折合（元/kg）</th><th>持仓量（手）</th><th>市场含义</th></tr>
      <tr><td>LH2609</td><td>2026-09</td><td>10,690</td><td>10.69</td><td>143,245</td><td>近月：反映当前供需最直接</td></tr>
      <tr><td>LH2611</td><td>2026-11</td><td>11,600</td><td>11.60</td><td>170,522</td><td>Q4 旺季预期，+911 元升水</td></tr>
      <tr><td>LH2701</td><td>2027-01</td><td>12,315</td><td>12.32</td><td>97,966</td><td>春节前高点预期</td></tr>
      <tr><td>LH2703</td><td>2027-03</td><td>12,095</td><td>12.10</td><td>92,849</td><td>春节后回落</td></tr>
      <tr><td>LH2705</td><td>2027-05</td><td>13,000</td><td>13.00</td><td>40,084</td><td>远月，流动性低</td></tr>
      <tr><td>LH2707</td><td>2027-07</td><td>13,640</td><td>13.64</td><td>9,418</td><td>最远月，仅作方向参考</td></tr>
    </table>

    <div class="box">
      <h3>期货价格对牧原的关键信号</h3>
      <ol>
        <li><b>远期升水结构清晰</b>：近月 10,690 → 远月 13,640，升水 +2,950 元/吨（+27.6%）。市场定价显示：当前为周期低谷，未来 6-10 个月猪价将逐步回升至 12-13 元/kg</li>
        <li><b>近月（LH2609）10.69 元/kg &lt; 牧原 11.6 元成本</b>：期货定价 9 月牧原仍亏损，但 LH2611 已升至 11.60（盈亏平衡附近），LH2701 12.32 元 → <b>市场预期 2026Q4 起牧原恢复盈利</b></li>
        <li><b>LH2705 突破 13 元</b>：若实现，牧原头均利润 = (13.0-11.6) × 110 = <b>约 154 元/头</b>；按年化 8000 万头 ≈ <b>123 亿元利润</b></li>
        <li><b>但需谨慎</b>：期货只是市场预期而非预测——2023 年同期远月合约也曾定价 16+ 元/kg，实际猪价仅为 15 元。市场集体犯错时常发生</li>
      </ol>
    </div>

    <h3>猪粮比 — 产能去化的核心驱动指标</h3>
    {charts['pig_grain']}
    <p>猪粮比 = 生猪价格 ÷ 玉米价格，是衡量养殖盈亏的最简指标。当前比值 <b>4.41:1</b> 处于<b>重度亏损区间</b>（< 5:1），已触发国家收储预警线。猪粮比长期低于 5:1 时，中小散户现金流断裂加速，产能去化不可逆。</p>

    <h3>能繁母猪 — 去化正在加速</h3>
    {charts['sow_trend']}
    <table>
      <tr><th>季度</th><th>存栏（万头）</th><th>距 3750 万头目标</th><th>环比变化</th></tr>
      <tr><td>2025-Q3</td><td>4,035</td><td>+285</td><td>-0.2%</td></tr>
      <tr><td>2025-Q4</td><td>3,961</td><td>+211</td><td>-1.8%</td></tr>
      <tr><td>2026-Q1</td><td>3,904</td><td>+154</td><td>-1.4%</td></tr>
      <tr><td>2026-Q2</td><td><b>3,780</b></td><td><b>+30</b></td><td><b>-3.2%</b></td></tr>
    </table>
    <ul>
      <li><b>2026Q2 去化显著加速</b>：单季减少 <b>124 万头</b>（-3.2%），是前三个季度平均去化速度（-1.1%）的近 3 倍</li>
      <li>距正常保有量仅 <b>+30 万头</b>（+0.8%），若 Q3 继续去化 30 万头以上，存栏将降至正常保有量以下</li>
      <li>去化加速的直接原因：2026H1 猪价 10.5 元/kg 远低于行业成本 13.5 元，行业头均亏损 330 元</li>
      <li>但 PSY 提升（2025 年 24.34 vs 2023 年 20.09）部分抵消存栏下降：<b>同等母猪数下，商品猪供给多 21%</b></li>
    </ul>

    <h3>仔猪价格 — 领先 8 个月的供给信号</h3>
    <p class="source">来源：仔猪价格数据来自 muyuan-tracker（博亚和讯/中国养猪网监测），约 8 个月后生猪期货来自 DCE 实时行情。</p>
    <p>逻辑链：仔猪价格 ↑ → 补栏意愿强 → 8 个月后出栏增加 → 远期猪价承压。反之，仔猪价格持续走低 → 补栏谨慎 → 远期供给收缩预期。</p>
    <p>当前（2026-08-03）：仔猪 <b>23.20 元/kg</b>（4 周 +7.1%），对应约 8 个月后（LH2703）期货 <b>12,835 元/吨</b>。仔猪价格从低位回升说明补栏意愿有所恢复，但期货远月仍在 12-13 元区间——<b>市场定价的远期猪价并未因仔猪补栏回升而下调，暗示市场认为供给缺口将在 2027 年显现</b>。</p>
  </div>

  <div class="section">
    <h2>6. 竞争格局与获利能力</h2>
    <p class="source">来源：出栏排名——中国猪业高层交流论坛《2025 中国养猪巨头排行榜》；成本——各上市公司公告/投资者交流纪要（经猪易/博亚和讯转载）。</p>
    {charts['top10']}
    <table>
      <tr><th>排名</th><th>企业</th><th>2025年出栏（万头）</th><th>同比</th><th>模式</th><th>完全成本（元/kg）</th></tr>
      <tr><td>1</td><td><b>牧原股份</b></td><td>7,798</td><td>+9%</td><td>自繁自养</td><td>11.3</td></tr>
      <tr><td>2</td><td>温氏股份</td><td>4,048</td><td>+34%</td><td>公司+农户</td><td>12.2</td></tr>
      <tr><td>3</td><td>双胞胎集团</td><td>2,643</td><td>+49%</td><td>饲料+养殖</td><td>—</td></tr>
      <tr><td>4</td><td>新希望</td><td>1,755</td><td>+6%</td><td>自繁自养+农户</td><td>12.7</td></tr>
      <tr><td>5</td><td>正大集团</td><td>1,277</td><td>—</td><td>全产业链</td><td>—</td></tr>
      <tr><td>6</td><td>德康农牧</td><td>1,083</td><td>—</td><td>自繁自养</td><td>—</td></tr>
      <tr><td>7</td><td>正邦科技</td><td>854</td><td>+106%</td><td>自繁自养</td><td>13.3</td></tr>
      <tr><td>8</td><td>天邦食品</td><td>666</td><td>—</td><td>自繁自养</td><td>13.4</td></tr>
      <tr><td>9</td><td>海大集团</td><td>650</td><td>—</td><td>饲料+养殖</td><td>—</td></tr>
      <tr><td>10</td><td>中粮家佳康</td><td>603</td><td>+69%</td><td>全产业链</td><td>—</td></tr>
    </table>
    <div class="source">来源：中国猪业高层交流论坛《2025 中国养猪巨头排行榜》（据各上市公司年报/月度销售简报汇总）；成本数据来自各公司最新投资者交流纪要。</div>
    {charts['conc']}
    <div class="source"><b>CR（Concentration Ratio，市场集中度）= 前 N 家企业出栏量 / 全国总出栏量</b>。CR10=30%：前 10 家企业出栏 2.14 亿头，占全国 7.1973 亿头的 30%。美国养猪业 CR10 约 60%，中国集中度仍有翻倍空间。</div>
    <p>格局特征：<b>一超多强、快速集中</b></p>
    <ul>
      <li>牧原（7,798 万头）单独占全国 <b>10.8%</b>，约为第二名温氏的 1.9 倍</li>
      <li>CR5（22%）→ CR10（30%）→ CR39（41%）：集中度每层约 10 个百分点递减，尾部仍极度分散</li>
      <li><b>马太效应</b>：头部企业出栏增速（TOP30 合计 +24.5%）远高于行业（+2.4%），市场份额加速向头部集中</li>
      <li>前 30 名门槛从 270 万头升至 320 万头，<b>规模本身就是壁垒</b></li>
    </ul>

    <h3>成本竞争——行业的唯一竞争维度</h3>
    <p class="source">来源：各上市公司公告/投资者交流纪要（2025 年末 → 2026Q2 更新），经猪易、博亚和讯多家行业媒体对比核验。完全成本 = 饲料 + 人工 + 折旧 + 动保 + 三费（销售/管理/财务），出栏均重按 110kg 折算。牧原/温氏已更新至 2026Q2 最新披露。</p>
    <table><tr><th>企业</th><th>2025 末成本</th><th>2026 最新</th><th>2026 目标</th><th>备注</th></tr>
<tr><td><b>牧原股份</b></td><td>11.3</td><td><b>11.6</b></td><td>&lt;11.5</td><td>Q2 约 11.6，优秀场线 &lt;11</td></tr><tr><td>温氏股份</td><td>12.2</td><td><b>~12.0</b></td><td>~11.8</td><td>Q2 约 12，Q1 账面 12.4</td></tr><tr><td>新希望</td><td>12.7</td><td>—</td><td>—</td><td>2025 年末数据，2026 未更新</td></tr><tr><td>正邦科技</td><td>13.3</td><td>—</td><td>—</td><td>2025 年末数据</td></tr><tr><td>天邦食品</td><td>13.4</td><td>—</td><td>—</td><td>2025 年末数据</td></tr><tr><td>上市猪企平均</td><td>12.9</td><td>—</td><td>—</td><td>15 家均值（2025 末）</td></tr><tr><td>中小散户</td><td>17.0</td><td>—</td><td>—</td><td>成本劣势 4~6 元/kg</td></tr></table>
    {charts['cost']}
    {charts['cost_struct']}
    <ul>
      <li><b>成本梯队清晰</b>：牧原 11.3 元（第一极）> 温氏 12.2、新希望 12.7（第二极）> 正邦 13.3、天邦 13.4（第三极）> 散户 17 元</li>
      <li>每 1 元/kg 的成本优势 = 每头猪多赚约 110 元 = 牧原年出栏 7800 万头 → <b>潜在超额利润约 86 亿元/年</b>（相对行业均值 12.88 元）</li>
      <li>饲料（62%）是最主要的成本项，也是规模采购和技术优化的最大杠杆项</li>
      <li>成本领先来自：饲料配方（低蛋白日粮节省豆粕）、猪舍设计（新风系统节省能耗）、自繁自养（不付仔猪溢价）、规模采购（原料折扣）</li>
    </ul>

    <h3>行业获利能力——猪周期盈亏分析</h3>
    <p class="source">来源：猪价——国家统计局/行情宝监测；成本——行业均值基于饲料成本+人工+折旧推算，牧原成本来自公司公告。头均利润 = (猪价 - 成本) × 110kg 出栏均重。</p>
    {charts['profit']}
    <p style="font-size:12px;color:#999;">注：2026H1 为上半年均值。头均利润按 110kg 出栏均重 × (猪价 - 完全成本) 估算。行业平均成本基于饲料价格 + 行业平均养殖效率推算。</p>
    <table>
      <tr><th>年份</th><th>猪价（元/kg）</th><th>行业成本</th><th>牧原成本</th><th>行业头均利润</th><th>牧原头均利润</th><th>周期阶段</th></tr>
      <tr><td>2019</td><td>22.0</td><td>14.0</td><td>12.5</td><td class="risk" style="color:#27ae60">+880</td><td class="risk" style="color:#1a6e35">+1,045</td><td>超级上行</td></tr>
      <tr><td>2020</td><td>32.0</td><td>16.0</td><td>14.0</td><td class="risk" style="color:#27ae60">+1,760</td><td class="risk" style="color:#1a6e35">+1,980</td><td>周期顶峰</td></tr>
      <tr><td>2021</td><td>17.0</td><td>18.0</td><td>15.5</td><td class="risk">-110</td><td style="color:#27ae60">+165</td><td>暴跌转亏</td></tr>
      <tr><td>2022</td><td>17.5</td><td>17.5</td><td>15.5</td><td style="color:#888">0</td><td style="color:#27ae60">+220</td><td>磨底</td></tr>
      <tr><td>2023</td><td>15.0</td><td>16.0</td><td>14.5</td><td class="risk">-110</td><td style="color:#888">+55</td><td>低迷</td></tr>
      <tr><td>2024</td><td>16.5</td><td>15.0</td><td>13.5</td><td style="color:#27ae60">+165</td><td style="color:#27ae60">+330</td><td>短暂回暖</td></tr>
      <tr><td>2025</td><td>15.2</td><td>14.0</td><td>11.3</td><td style="color:#27ae60">+132</td><td style="color:#1a6e35">+429</td><td>成本分化</td></tr>
      <tr><td><b>2026H1</b></td><td><b>10.5</b></td><td><b>13.5</b></td><td><b>11.6</b></td><td class="risk"><b>-330</b></td><td class="risk"><b>-121</b></td><td><b>深度去化</b></td></tr>
    </table>
    <div class="source">来源：猪价——国家统计局年度均价 + 行情宝周度监测；成本——行业均值基于饲料成本+养殖效率模型估算，牧原/温氏来自公司公告/投资者交流（2026Q2 最新）。头均利润 = (年均价 - 完全成本) × 110kg。2026H1 猪价按 Q1(11.56) + Q2(9.48) 加权均 ≈ 10.5 元/kg。</div>
    <ul>
      <li><b>牧原穿越周期的能力已验证</b>：在行业全面亏损的 2022-2023 年和 2026H1，牧原仍保持盈亏平衡或微亏，而行业平均每头亏损 100-330 元</li>
      <li><b>2026H1 深度亏损</b>：猪价（10.5）远低于行业成本（13.5），行业头均亏损 330 元，牧原也出现 121 元/头的亏损——这是去化的核心驱动力。Q1 牧原亏损 12.15 亿、温氏亏损 10.70 亿</li>
      <li><b>但牧原亏损幅度仅为行业的 37%</b>（121 vs 330 元/头），成本优势在熊市更显珍贵</li>
      <li><b>盈亏拐点</b>：猪价需回升至 ~12 元/kg 牧原可盈亏平衡，回升至 ~14 元/kg 行业整体盈利。2026Q3 猪价已回升至 10.8 元，趋势向好</li>
    </ul>

    <h3>波特五力</h3>
    <p class="source">基于行业公开信息与竞争格局数据的定性分析。</p>
    <table>
      <tr><th>力量</th><th>强度</th><th>分析</th></tr>
      {porter_html}
    </table>
    <p>五力判断：行业竞争激烈，但对<b>成本最低的龙头企业（牧原）</b>是结构性利好——壁垒阻挡新进入者和散户，成本优势转化为持续的市占率扩张。</p>
  </div>

  <div class="section">
    <h2>7. 进入壁垒</h2>
    <p class="source">来源：土地/环保——自然资源部/生态环境部政策文件（2025 年新增审批量数据来自 Mysteel）；资金——上市公司公开数据推算；防疫——农业农村部。</p>
    <table>
      <tr><th>壁垒</th><th>强度</th><th>具体表现</th></tr>
      {barrier_rows}
    </table>
    <p><b>综合判断</b>：六大壁垒中有四项"极高"或"高"。对于一家想从头新建规模化猪场的企业，今天面临的壁垒比五年前高一个数量级。<b>对于已在行业内的龙头（牧原），这道壁垒是最大的护城河。</b></p>
  </div>

  <div class="section">
    <h2>8. 政策环境</h2>
    <p class="source">来源：农业农村部历年文件、国务院一号文件、新《环境保护法》（2015）。正常保有量数据来自农业农村部《生猪产能综合调控实施方案》各版修订公告。</p>
    <table>
      <tr><th>年份</th><th>事件</th></tr>
      {policy_rows}
    </table>
    <p><b>政策方向清晰</b>：从"保供给"转向"调结构"。鼓励规模化、高效率、环保达标；限制散乱差、高污染、低成本扩张。每一轮政策收紧都<b>利好头部企业，加速散户退出</b>。</p>
  </div>

  <div class="section">
    <h2>9. 八个关键行业问题</h2>
    <p class="source">综合本报告前文各节分析，具体数据出处参见对应章节。</p>
    <ol>
      {q8_html}
    </ol>
  </div>

  <div class="section">
    <h2>10. 综合研判：多信号交叉验证</h2>
    <p class="source">综合本报告 §4-§5 数据，将期货、猪粮比、能繁去化、PSY、仔猪五条独立信号线交叉验证。</p>

    <h3>信号交叉矩阵</h3>
    <table>
      <tr><th>信号来源</th><th>当前读数</th><th>方向</th><th>对猪价含义</th><th>置信度</th></tr>
      <tr><td>生猪期货远期曲线</td><td>近月 10.69 → 远月 13.64 元/kg（+27.6%）</td><td style="color:#27ae60">▲ 看涨</td><td>市场定价 Q4 回升、2027 年 13+ 元</td><td>中（期货≠预测）</td></tr>
      <tr><td>猪粮比</td><td>4.41:1（重度亏损）</td><td style="color:#27ae60">▲ 看涨</td><td>不可持续低位，倒逼产能出清</td><td>高（历史规律可靠）</td></tr>
      <tr><td>能繁母猪去化</td><td>Q2 -3.2%（-124 万头），加速中</td><td style="color:#27ae60">▲ 看涨</td><td>6-10 个月后供给收缩</td><td>高（官方数据）</td></tr>
      <tr><td>PSY 效率提升</td><td>24.34（vs 2023 年 20.09）</td><td style="color:#e74c3c">▼ 偏空</td><td>缓冲去化效果，供给降幅小于存栏降幅</td><td>中高</td></tr>
      <tr><td>仔猪-期货联动</td><td>仔猪 23.2 元/kg ↑ + 远月期货未跌</td><td style="color:#27ae60">▲ 看涨</td><td>补栏回暖但市场未调低远期价格 → 供给缺口预期</td><td>中低（领先关系不稳定）</td></tr>
    </table>

    <div class="box">
      <h3>五条独立信号线中，四条指向同一个方向：猪周期上行</h3>
      <p>唯一反向信号（PSY 提升）只是<b>缓冲</b>去化的效果，并不否定去化方向。核心逻辑链：</p>
      <p><b>猪粮比 4.41 → 深度亏损不可持续 → 能繁加速去化（Q2 -3.2%）→ 6-10 个月后供给收缩 → 猪价回升至成本线上方 → 牧原率先盈利</b></p>
      <p>PSY 提升使同等存栏多产 21% 商品猪——这意味着<b>能繁需要降到约 3,600 万头才能产生与上一轮周期底部相同的供给收缩效果</b>（3750 × 20.09/24.34 ≈ 3,100，但考虑到头部企业 PSY 更高，保守估计 3,300-3,500）。当前 3,780 万头仍不够低，去化还需继续——但这恰恰是牧原的机会：<b>在别人流血时保持呼吸，在别人倒下后扩张</b>。</p>
    </div>

    <h3>对牧原的战略含义</h3>
    <ol>
      <li><b>短期（2026H2）— 熬底阶段</b>：猪粮比 4.41、猪价 10.52 元低于牧原成本 11.6 元 → 牧原仍亏损 ~121 元/头。但比行业均值少亏 63%。关键是<b>现金流管理</b>：Q1 亏损 12.15 亿但经营现金流保持正值，能撑过最后一段黑暗</li>
      <li><b>中期（2027H1）— 盈利拐点</b>：期货远期定价 LH2701=12.32、LH2703=12.10 → 牧原头均利润恢复至 55-80 元。若去化超预期，猪价可能突破期货定价。按 8000 万头 × 80 元 = <b>64 亿元利润</b>，对应 PE ~34×（当前市值 ~2150 亿）</li>
      <li><b>中长期（2027H2+）— 周期高峰</b>：若能繁降至 3600 万以下 + 散户进一步退出，猪价有望升至 15-18 元。牧原成本若能维持 11.5 元，头均利润 385-715 元 → 年化利润 <b>308-572 亿元</b>。这是周期的真正回报</li>
      <li><b>成本护城河在熊市创造的价值</b>：2026H1 行业头均亏 330 元、牧原仅亏 121 元——<b>每头猪少亏 209 元 × 半年 3900 万头 ≈ 少亏 81 亿元</b>。这 81 亿就是牧原的竞争对手在流失的血液。每多熬一个季度，就有更多对手倒下</li>
      <li><b>市占率加速窗口</b>：去化最快的时期 = 牧原市占率提升最快的时期。2025 年 CR10=30%，若本轮去化淘汰 20% 散户产能（约 1.4 亿头），头部企业可承接其中 60-70%。牧原的 10.8% 有望在 3 年内升至 <b>13-15%</b></li>
    </ol>

    <h3>主要风险</h3>
    <ol>
      <li><b>去化不彻底</b>：PSY 持续提升 + 头部企业逆势扩产 → 供给始终不降，猪价长期低位横盘。概率：中（30%）。应对：关注能繁月度变化，若连续两季去化 < 1% 需警惕</li>
      <li><b>期货"集体犯错"</b>：市场一致看多 → 养殖户压栏/二次育肥 → 短期供给后移 → 预期中的上涨被推迟或削弱。概率：中（25%）。应对：不过度依赖期货定价，以成本优势作为底线保护</li>
      <li><b>饲料成本反弹</b>：豆粕已从 2818 反弹至 2908（+3.2%），若中美贸易摩擦升级或全球大豆减产，饲料成本可能大幅上升。概率：中低（20%）。应对：牧原低蛋白日粮配方可降低豆粕依赖</li>
      <li><b>大规模疫情</b>：非瘟变异株或新疫情 → 牧原高密度养殖模式生物安全风险。概率：低（10%），但影响极大。应对：分散场区、全封闭管理</li>
    </ol>
  </div>

  <div class="section">
    <h2>附录：数据来源</h2>
    <ul class="note">
      <li>行业规模数据：国家统计局（2025 年国民经济运行数据，2026-01-19 发布）</li>
      <li>企业排名与出栏量：中国猪业高层交流论坛《2025 中国养猪巨头排行榜》</li>
      <li>完全成本数据：各上市公司公告/投资者交流纪要（2025 年末），经猪易/博亚和讯转载</li>
      <li>规模化率与散户退出：山东省畜牧兽医局《我国养猪行业发展新情况新趋势简析》</li>
      <li>生产效率（PSY/MSY）：Mysteel 农产品 / 行业复盘报告</li>
      <li>政策：农业农村部、国务院相关文件</li>
      <li>波特五力与进入壁垒：综合各来源的定性判断</li>
      <li>🆕 生猪期货/猪粮比/仔猪/能繁季度：<a href="https://kisvenus.github.io/muyuan-tracker/" target="_blank">muyuan-tracker</a>（聚合 DCE 期货 + 农业农村部 + 中国养猪网数据）</li>
    </ul>
  </div>

</div>
</body>
</html>"""
    return html


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("== 生成行业分析报告 ==")
    html = build_html_report()
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"  报告已生成: {REPORT_PATH}")

    manifest = {
        "step": 2,
        "step_name": "行业分析",
        "company": "牧原股份",
        "code": "002714.SZ",
        "report_date": TODAY_STR,
        "data_sources": [
            "国家统计局 2025 年国民经济数据",
            "中国猪业高层交流论坛 TOP20 排名",
            "上市公司公告（出栏量/成本）",
            "山东省畜牧兽医局行业分析",
            "Mysteel 农产品 / 博亚和讯",
            "农业农村部政策文件",
            "kisvenus.github.io/muyuan-tracker（期货/猪粮比/仔猪/能繁）",
        ],
        "key_findings": [
            "规模化率 73%，CR10 30%，成长期→成熟期",
            "牧原成本 11.3 元/kg 行业最低，比均值低 1.6 元",
            "六大进入壁垒阻挡新竞争者，利好存量龙头",
            "政策方向明确：优胜劣汰、龙头受益",
            "市占率 10.8%，对标美国仍有 5 倍空间",
            "期货远期升水 +27.6%，市场定价 2027 猪价 13+ 元/kg",
            "猪粮比 4.41:1 重度亏损区间，能繁 Q2 去化 -3.2% 加速",
            "仔猪补栏回暖但期货远月未下调，暗示 2027 供给缺口预期",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  数据清单: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
