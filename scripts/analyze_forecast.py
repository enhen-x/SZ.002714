# -*- coding: utf-8 -*-
"""
牧原股份财务预测 — 牧原股份 (SZ.002714)
证券分析八步流程 · 第5步：财务预测

预测框架：
  1. 销售收入预测（出栏量 × 均价）
  2. 三种情景（上行/基准/下行），基准含 1~2 年下行
  3. 预测利润表至 EBIT → EPS
  4. 敏感性分析（猪价 ±1 元对利润的影响）

方法论：Hooke 财务预测七步骤 + 三种情景分析
数据来源：公司年报、生猪期货、国家统计局、前期分析步骤
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "财务预测报告.html"
TODAY_STR = datetime.now().strftime("%Y-%m-%d")

# ==================== 颜色常量（与前序报告一致） ====================
C = {
    "blue": "#3498db",
    "red": "#c0392b",
    "green": "#27ae60",
    "orange": "#e67e22",
    "purple": "#8e44ad",
    "dark": "#2c3e50",
    "gray": "#7f8c8d",
    "teal": "#1abc9c",
    "midblue": "#2980b9",
    "darkgreen": "#1e8449",
}

PLOTLY_TEMPLATE = "plotly_white"

# ==================== 历史数据加载 ====================

def safe_float(val, default=None):
    if val is None or (isinstance(val, float) and pd.isna(val)) or val == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def load_csv(filename):
    path = DATA_DIR / filename
    if not path.exists():
        print(f"[WARN] 文件不存在: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    return df

def get_annual_rows(df, date_col="REPORT_DATE"):
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["_year"] = df["_date"].dt.year
    annual = df[df["_date"].dt.month == 12].copy()
    annual = annual.sort_values("_date").drop_duplicates(subset=["_year"], keep="last")
    annual = annual.sort_values("_year")
    return annual

# 加载财务数据（复用 analyze_finance 的数据加载逻辑）
df_income = load_csv("利润表_按报告期.csv")
df_balance = load_csv("资产负债表_按报告期.csv")
df_cashflow = load_csv("现金流量表_按报告期.csv")
df_indicator = load_csv("主要财务指标_按报告期.csv")

annual_income = get_annual_rows(df_income)
annual_balance = get_annual_rows(df_balance)
annual_cashflow = get_annual_rows(df_cashflow)
annual_indicator = get_annual_rows(df_indicator)

years_income = annual_income["_year"].tolist()
years_balance = annual_balance["_year"].tolist()
years_cashflow = annual_cashflow["_year"].tolist()
common_years = sorted(set(years_income) & set(years_balance) & set(years_cashflow))

def row_for_year(df_annual, year):
    rows = df_annual[df_annual["_year"] == year]
    return None if rows.empty else rows.iloc[0]

# 构建 FIN dict（仅最近年份，用于基线）
FIN = {}
for yr in common_years:
    inc = row_for_year(annual_income, yr)
    bal = row_for_year(annual_balance, yr)
    cf = row_for_year(annual_cashflow, yr)
    ind = row_for_year(annual_indicator, yr)
    if inc is None or bal is None or cf is None:
        continue
    d = {
        "revenue": safe_float(inc.get("TOTAL_OPERATE_INCOME"), 0) / 1e8,
        "operate_cost": safe_float(inc.get("OPERATE_COST"), 0) / 1e8,
        "sale_exp": safe_float(inc.get("SALE_EXPENSE"), 0) / 1e8,
        "manage_exp": safe_float(inc.get("MANAGE_EXPENSE"), 0) / 1e8,
        "rd_exp": safe_float(inc.get("RESEARCH_EXPENSE"), 0) / 1e8,
        "fin_exp": safe_float(inc.get("FINANCE_EXPENSE"), 0) / 1e8,
        "interest_exp": safe_float(inc.get("FE_INTEREST_EXPENSE"), 0) / 1e8,
        "op_profit": safe_float(inc.get("OPERATE_PROFIT"), 0) / 1e8,
        "total_profit": safe_float(inc.get("TOTAL_PROFIT"), 0) / 1e8,
        "net_profit": safe_float(inc.get("NETPROFIT"), 0) / 1e8,
        "parent_profit": safe_float(inc.get("PARENT_NETPROFIT"), 0) / 1e8,
        "eps": safe_float(inc.get("BASIC_EPS"), 0),
        "total_assets": safe_float(bal.get("TOTAL_ASSETS"), 0) / 1e8,
        "total_liab": safe_float(bal.get("TOTAL_LIABILITIES"), 0) / 1e8,
        "total_equity": safe_float(bal.get("TOTAL_EQUITY"), 0) / 1e8,
        "short_loan": safe_float(bal.get("SHORT_LOAN"), 0) / 1e8,
        "long_loan": safe_float(bal.get("LONG_LOAN"), 0) / 1e8,
        "notes_payable": safe_float(bal.get("NOTE_PAYABLE"), 0) / 1e8,
        "ocf": safe_float(cf.get("NETCASH_OPERATE"), 0) / 1e8,
        "capex": safe_float(cf.get("CONSTRUCT_LONG_ASSET"), 0) / 1e8,
        "roe": safe_float(ind.get("ROEJQ"), 0) if ind is not None else None,
    }
    rev = d["revenue"]
    if rev > 0:
        d["gross_margin_calc"] = (rev - d["operate_cost"]) / rev * 100
        d["sale_rate"] = d["sale_exp"] / rev * 100
        d["manage_rate"] = d["manage_exp"] / rev * 100
        d["rd_rate"] = d["rd_exp"] / rev * 100
    else:
        for k in ["gross_margin_calc","sale_rate","manage_rate","rd_rate"]:
            d[k] = 0
    d["interest_debt"] = d["short_loan"] + d["long_loan"] + d.get("notes_payable", 0)
    FIN[yr] = d

SORTED_YEARS = sorted(FIN.keys())
LATEST = max(SORTED_YEARS)
print(f"历史数据: {SORTED_YEARS[0]}-{SORTED_YEARS[-1]} ({len(SORTED_YEARS)} 年)")

# ==================== 公司硬数据（从独立 CSV 加载） ====================

def _load_company_csv(filename, key_col, val_col):
    """加载公司数据 CSV，返回 dict。"""
    df = load_csv(filename)
    result = {}
    for _, row in df.iterrows():
        k = row.get(key_col, "")
        v = safe_float(row.get(val_col))
        if k and v is not None:
            # 处理年份键
            try:
                k = int(k)
            except (ValueError, TypeError):
                pass  # 保留字符串键（如 "2026H1"）
            result[k] = v
    return result

# 出栏量（万头）
HOG_SALES = _load_company_csv("牧原_出栏量.csv", "年份", "出栏量_万头")
HOG_2026H1 = HOG_SALES.pop("2026H1", 3862)  # 弹出字符串键，单独存储

# 完全成本 元/kg
COST_TREND = _load_company_csv("牧原_完全成本.csv", "年份", "完全成本_元每公斤")
COST_2026H1 = COST_TREND.pop("2026H1", 11.6)

# 产能数据（从 CSV 加载）
df_cap = load_csv("牧原_产能数据.csv")
CAPACITY = 9000  # 默认
SOW_2025 = 323   # 默认
for _, row in df_cap.iterrows():
    yr = row.get("年份", "")
    try:
        yr = int(yr)
    except (ValueError, TypeError):
        continue
    cap = safe_float(row.get("产能_万头每年"))
    sow = safe_float(row.get("能繁母猪_万头"))
    if yr == 2025:
        if cap: CAPACITY = int(cap)
        if sow: SOW_2025 = int(sow)

print(f"出栏量数据: {len(HOG_SALES)} 年")
print(f"成本数据: {len(COST_TREND)} 年")

# 加载季度猪价数据
df_pig_q = load_csv("生猪价格_季度.csv")
df_pig_q["均价"] = df_pig_q["季度均价_元每公斤"].apply(lambda x: safe_float(x))
PIG_PRICE_Q = {}
for _, row in df_pig_q.iterrows():
    q = str(row.get("季度", ""))
    price = row.get("均价")
    if q and price is not None:
        PIG_PRICE_Q[q] = price

# 加载期货数据
df_futures = load_csv("生猪期货远期曲线.csv")
FUTURES = {}
for _, row in df_futures.iterrows():
    month = str(row.get("交割月份", ""))
    price = safe_float(row.get("期货价格_元每公斤"))
    if month and price:
        FUTURES[month] = price

print(f"猪价季度数据: {len(PIG_PRICE_Q)} 个季度")
print(f"期货远期曲线: {FUTURES}")

# ==================== 预测假设 ====================

# 出栏均重 kg/头
AVG_WEIGHT = 110

# 出栏量假设（万头）
HOG_FORECAST = {
    2025: 7798,  # 实际
    2026: 8100,  # H1 实际 3862 → 全年估 8100
    2027: 8300,  # +2.5%
    2028: 8500,  # +2.4%
}

# 三种情景猪价假设（年均价 元/kg）
PRICE_SCENARIOS = {
    "上行": {2025: 14.4, 2026: 11.0, 2027: 14.0, 2028: 15.5},
    "基准": {2025: 14.4, 2026: 10.5, 2027: 12.5, 2028: 13.5},
    "下行": {2025: 14.4, 2026: 10.0, 2027: 11.0, 2028: 11.5},
}

# 完全成本假设（元/kg）
COST_SCENARIOS = {
    "上行": {2025: 12.0, 2026: 11.5, 2027: 11.5, 2028: 11.3},
    "基准": {2025: 12.0, 2026: 11.5, 2027: 11.3, 2028: 11.0},
    "下行": {2025: 12.0, 2026: 11.8, 2027: 11.5, 2028: 11.3},
}

# 收入模型参数
# 历史验证：2025 年 1441亿 / (7798万头 × 110kg × 14.4元/kg / 1e4) = 1441/1235 = 1.167
# 屠宰溢价（猪肉售价高于活猪价）+ 饲料/其他外销贡献 ~16% 增量收入
REV_MULTIPLIER = 1.16  # 总营收 / 活猪毛收入（含屠宰溢价+其他业务）
NON_HOG_COST_RATE = 0.90  # 屠宰+其他业务综合成本率

# 费用率假设（近3年历史均值，保守）
COST_RATES = {
    "sale_rate": 0.23,     # 销售费用率 ~0.23%
    "manage_rate": 0.92,   # 管理费用率 ~0.92%
    "rd_rate": 1.15,       # 研发费用率 ~1.15%
}

# 融资假设
TOTAL_SHARES = 54.7  # 总股本（亿股，含H股摊薄后）
INTEREST_RATE = 0.035  # 平均融资利率（2025 年降息后）
TAX_RATE_LOW = 0.0   # 亏损/低利润年：前期亏损抵扣
TAX_RATE_HIGH = 0.05  # 高利润年：部分纳税（考虑亏损抵扣逐步耗尽）

# ==================== 预测模型 ====================

def project_income_statement(scenario, year, use_actual=False):
    """根据情景和年份，生成利润表预测。

    收入模型：总营收 = 活猪毛收入 × 收入乘数（含屠宰溢价+其他业务）
    成本模型：养殖成本 + 屠宰/其他业务成本
    """
    hog = HOG_FORECAST.get(year, 0)
    price = PRICE_SCENARIOS[scenario][year]
    cost_per_kg = COST_SCENARIOS[scenario][year]

    # 活猪毛收入（所有出栏 × 活猪均价）
    hog_rev_raw = hog * AVG_WEIGHT * price / 1e4  # 亿元
    # 总营收 = 活猪毛收入 × 收入乘数（屠宰溢价 ~16%）
    total_rev = hog_rev_raw * REV_MULTIPLIER

    # 养殖成本
    hog_cost = hog * AVG_WEIGHT * cost_per_kg / 1e4
    # 屠宰+其他业务增量成本（增量收入 × 综合成本率）
    non_hog_rev = total_rev - hog_rev_raw
    non_hog_cost = non_hog_rev * NON_HOG_COST_RATE
    total_cost = hog_cost + non_hog_cost

    # 毛利
    gross_profit = total_rev - total_cost

    # 期间费用
    sale_exp = total_rev * COST_RATES["sale_rate"] / 100
    manage_exp = total_rev * COST_RATES["manage_rate"] / 100
    rd_exp = total_rev * COST_RATES["rd_rate"] / 100

    # 财务费用估算（有息负债缓慢下降）
    base_debt = FIN[LATEST]["interest_debt"]  # 2025 实际
    debt_reduction = {2025: 0, 2026: 25, 2027: 55, 2028: 85}  # 累计偿债
    net_debt = max(base_debt - debt_reduction.get(year, 0), base_debt * 0.7)
    fin_exp = net_debt * INTEREST_RATE

    # 营业利润
    op_profit = gross_profit - sale_exp - manage_exp - rd_exp - fin_exp

    # 利息费用（用于 EBIT）
    interest_exp = net_debt * INTEREST_RATE

    # 利润总额（简化：无非经常性损益）
    total_profit = op_profit

    # 所得税（高利润年缴少量税，亏损年不缴）
    tax_rate = TAX_RATE_HIGH if total_profit > 100 else TAX_RATE_LOW
    income_tax = max(total_profit * tax_rate, 0)

    # 净利润
    net_profit = total_profit - income_tax

    # 归母净利润（少数股东损益极低）
    parent_profit = net_profit * 0.98

    # EPS
    eps = parent_profit / TOTAL_SHARES

    # EBIT
    ebit = total_profit + interest_exp

    return {
        "year": year, "scenario": scenario,
        "hog": hog, "price": price, "cost_per_kg": cost_per_kg,
        "total_rev": total_rev, "total_cost": total_cost,
        "gross_profit": gross_profit,
        "sale_exp": sale_exp, "manage_exp": manage_exp,
        "rd_exp": rd_exp, "fin_exp": fin_exp,
        "interest_exp": interest_exp,
        "op_profit": op_profit, "total_profit": total_profit,
        "income_tax": income_tax,
        "net_profit": net_profit, "parent_profit": parent_profit,
        "eps": eps, "ebit": ebit,
        "ebit_int_cover": ebit / interest_exp if interest_exp > 0 else 99,
        "gross_margin": gross_profit / total_rev * 100 if total_rev > 0 else 0,
        "net_margin": net_profit / total_rev * 100 if total_rev > 0 else 0,
    }

# 生成所有预测
FORECAST = {}
for sc in ["上行", "基准", "下行"]:
    FORECAST[sc] = {}
    for yr in [2025, 2026, 2027, 2028]:
        FORECAST[sc][yr] = project_income_statement(sc, yr)

# 2025 年用实际数据覆盖所有情景（保持与 Step 4 一致）
if 2025 in FIN:
    d = FIN[2025]
    for sc in ["上行", "基准", "下行"]:
        fc = FORECAST[sc][2025]
        fc["total_rev"] = d["revenue"]
        fc["total_cost"] = d["operate_cost"]
        fc["gross_profit"] = d["revenue"] - d["operate_cost"]
        fc["gross_margin"] = fc["gross_profit"] / d["revenue"] * 100
        fc["sale_exp"] = d["sale_exp"]
        fc["manage_exp"] = d["manage_exp"]
        fc["rd_exp"] = d["rd_exp"]
        fc["fin_exp"] = d["fin_exp"]
        fc["interest_exp"] = d["interest_exp"]
        fc["op_profit"] = d["op_profit"]
        fc["total_profit"] = d["total_profit"]
        fc["net_profit"] = d["net_profit"]
        fc["parent_profit"] = d["parent_profit"]
        fc["eps"] = d["eps"]
        fc["ebit"] = d["total_profit"] + d["interest_exp"]
        fc["net_margin"] = d["net_profit"] / d["revenue"] * 100
        fc["income_tax"] = 0
        fc["ebit_int_cover"] = fc["ebit"] / d["interest_exp"] if d["interest_exp"] > 0 else 99

# 打印概览
print("\n=== 预测概览（基准情景）===")
for yr in [2025, 2026, 2027, 2028]:
    fc = FORECAST["基准"][yr]
    print(f"  {yr}: 出栏{fc['hog']}万头 均价{fc['price']}元/kg 成本{fc['cost_per_kg']}元/kg "
          f"营收{fc['total_rev']:.0f}亿 归母{fc['parent_profit']:.0f}亿 EPS{fc['eps']:.2f}")

# ==================== Chart 1: 出栏量 + 猪价双轴 ====================

def ch1_rev_hog():
    """出栏量历史+预测 + 猪价假设"""
    hist_yrs = sorted(HOG_SALES.keys())
    hist_hog = [HOG_SALES[yr] for yr in hist_yrs]
    forecast_yrs = [2025, 2026, 2027, 2028]
    forecast_hog = [HOG_FORECAST[yr] for yr in forecast_yrs]
    base_price = [PRICE_SCENARIOS["基准"][yr] for yr in forecast_yrs]
    base_cost = [COST_SCENARIOS["基准"][yr] for yr in forecast_yrs]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 出栏量柱状图（历史不含2025，避免与预测重复）
    hist_yrs_before = [y for y in hist_yrs if y < 2025]
    hist_hog_before = [HOG_SALES[y] for y in hist_yrs_before]
    fig.add_trace(go.Bar(
        x=[str(y) for y in hist_yrs_before], y=hist_hog_before,
        name="出栏量 历史（万头）", marker_color=C["blue"], opacity=0.7,
        legendgroup="hog",
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=[str(y) + "E" for y in forecast_yrs], y=forecast_hog,
        name="出栏量 预测（万头）", marker_color=C["midblue"], opacity=0.9,
        legendgroup="hog",
    ), secondary_y=False)

    # 猪价/成本线
    fig.add_trace(go.Scatter(
        x=[str(y) + "E" for y in forecast_yrs], y=base_price,
        name="基准猪价（元/kg）", mode="lines+markers",
        line=dict(color=C["red"], width=3), marker=dict(size=8, symbol="circle"),
    ), secondary_y=True)
    fig.add_trace(go.Scatter(
        x=[str(y) + "E" for y in forecast_yrs], y=base_cost,
        name="基准完全成本（元/kg）", mode="lines+markers",
        line=dict(color=C["green"], width=2.5, dash="dash"), marker=dict(size=7, symbol="diamond"),
    ), secondary_y=True)

    fig.update_yaxes(title="出栏量（万头）", secondary_y=False, range=[0, max(forecast_hog) * 1.3])
    fig.update_yaxes(title="元/kg", secondary_y=True, range=[8, 18])
    fig.update_xaxes(tickangle=0)
    fig.update_layout(
        title=dict(text="出栏量与猪价预测（基准情景）", x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=440, hovermode="x unified", bargap=0.3,
        template=PLOTLY_TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="left", x=0, font=dict(size=10)),
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
        margin=dict(l=55, r=65, t=80, b=55),
    )
    return fig


# ==================== Chart 2: 三种情景猪价路径 ====================

def ch2_price_scenarios():
    """历史猪价 + 三种情景预测 + 完全成本线"""
    # 历史年度均价（全国均价，作为周期背景）
    hist_yrs = list(range(2015, 2026))
    hist_prices = []
    for yr in hist_yrs:
        q_prices = [PIG_PRICE_Q.get(f"{yr}Q{q}", None) for q in range(1, 5)]
        valid = [p for p in q_prices if p is not None]
        hist_prices.append(sum(valid) / len(valid) if valid else None)

    valid_data = [(y, p) for y, p in zip(hist_yrs, hist_prices) if p is not None]
    hist_yrs_v = [v[0] for v in valid_data]
    hist_prices_v = [v[1] for v in valid_data]

    # 预测从 2026E 开始（不含 2025，与历史线自然衔接）
    forecast_yrs = [2026, 2027, 2028]
    base_cost_vals = [COST_SCENARIOS["基准"][yr] for yr in forecast_yrs]

    # 最大值用于设置 Y 轴范围
    max_hist = max(hist_prices_v) if hist_prices_v else 22

    fig = go.Figure()

    # 历史年均猪价（全国均价）
    fig.add_trace(go.Scatter(
        x=[str(y) for y in hist_yrs_v], y=hist_prices_v,
        name="全国年均猪价（历史）", mode="lines+markers",
        line=dict(color=C["gray"], width=2), marker=dict(size=5),
        hovertemplate="%{x} 全国均价: %{y:.1f}元/kg<extra></extra>",
    ))

    # 垂直分隔线标记预测起点
    fig.add_vline(x=len(hist_yrs_v) - 0.5, line_dash="dot", line_color=C["gray"],
                  line_width=1, opacity=0.5,
                  annotation=dict(text="← 历史 | 预测 →", font=dict(size=9, color=C["gray"]),
                                  y=0.98, yanchor="top"))

    # 三种情景预测
    colors_s = {"上行": C["green"], "基准": C["midblue"], "下行": C["red"]}
    dashes_s = {"上行": "dot", "基准": None, "下行": "dot"}
    for sc in ["上行", "基准", "下行"]:
        sc_prices = [PRICE_SCENARIOS[sc][yr] for yr in forecast_yrs]
        # 连接 2025 实际值到 2026 预测
        x_vals = ["2025"] + [str(y) + "E" for y in forecast_yrs]
        y_vals = [PRICE_SCENARIOS[sc][2025]] + sc_prices
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            name=f"{sc}情景", mode="lines+markers",
            line=dict(color=colors_s[sc], width=2.5, dash=dashes_s[sc]),
            marker=dict(size=7),
            hovertemplate="%{x} " + sc + ": %{y:.1f}元/kg<extra></extra>",
        ))

    # 基准成本线（同样从 2025 连接）
    cost_x = ["2025"] + [str(y) + "E" for y in forecast_yrs]
    cost_y = [COST_SCENARIOS["基准"][2025]] + base_cost_vals
    fig.add_trace(go.Scatter(
        x=cost_x, y=cost_y,
        name="完全成本（基准）", mode="lines+markers",
        line=dict(color=C["dark"], width=2, dash="dashdot"),
        marker=dict(size=6, symbol="triangle-down"),
    ))

    # 盈亏平衡参考区（基于成本区间）
    min_cost = min(base_cost_vals)
    fig.add_hrect(y0=0, y1=min_cost, line_width=0, fillcolor="red", opacity=0.06,
                  annotation=dict(text="亏损区（猪价<成本）", font=dict(size=10, color=C["red"]),
                                  y=min_cost - 1))

    fig.update_yaxes(title="元/kg", range=[5, max(max_hist, 18) + 5])
    fig.update_xaxes(tickangle=0)
    fig.update_layout(
        title=dict(text="三种情景猪价路径 vs 历史猪价（全国均价）", x=0.02, y=0.98,
                   font=dict(size=15, color="#1a1a1a")),
        height=460, hovermode="x unified",
        template=PLOTLY_TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.16, xanchor="left", x=0, font=dict(size=10)),
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
        margin=dict(l=55, r=30, t=85, b=55),
    )
    return fig


# ==================== Chart 3: 利润表瀑布图（基准 2027E） ====================

def ch3_waterfall():
    """基准情景 2027E 利润表瀑布图"""
    fc = FORECAST["基准"][2027]

    items = ["营业收入", "营业成本", "毛利", "销售费用", "管理费用",
             "研发费用", "财务费用", "营业利润"]
    # 瀑布图用 measure: relative/absolute/total
    measures = ["absolute", "relative", "total", "relative", "relative",
                "relative", "relative", "total"]
    values = [
        fc["total_rev"],
        -fc["total_cost"],
        fc["gross_profit"],
        -fc["sale_exp"],
        -fc["manage_exp"],
        -fc["rd_exp"],
        -fc["fin_exp"],
        fc["op_profit"],
    ]
    texts = [f"{v:+.0f}亿" for v in values]

    fig = go.Figure(go.Waterfall(
        name="2027E 基准",
        orientation="v",
        measure=measures,
        x=items,
        y=values,
        text=texts,
        textposition="outside",
        connector=dict(line=dict(color=C["gray"], width=1)),
        decreasing=dict(marker=dict(color=C["red"])),
        increasing=dict(marker=dict(color=C["green"])),
        totals=dict(marker=dict(color=C["midblue"])),
    ))

    fig.update_yaxes(title="亿元")
    fig.update_xaxes(tickangle=30)
    fig.update_layout(
        title=dict(text="基准情景利润表瀑布图（2027E）", x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=460, hovermode="x",
        template=PLOTLY_TEMPLATE,
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
        margin=dict(l=55, r=30, t=80, b=55),
    )
    return fig


# ==================== Chart 4: 三种情景 EPS 对比 ====================

def ch4_eps():
    """三种情景 EPS 柱状图（仅预测年）"""
    forecast_yrs = [2026, 2027, 2028]
    scenarios = ["上行", "基准", "下行"]
    colors_s = {"上行": C["green"], "基准": C["midblue"], "下行": C["red"]}

    fig = go.Figure()
    for sc in scenarios:
        eps_vals = [FORECAST[sc][yr]["eps"] for yr in forecast_yrs]
        fig.add_trace(go.Bar(
            x=[f"{yr}E" for yr in forecast_yrs],
            y=eps_vals,
            name=f"{sc}情景",
            marker_color=colors_s[sc], opacity=0.85,
            text=[f"{v:.2f}" for v in eps_vals],
            textposition="outside",
            textfont=dict(size=11),
        ))

    # 2025 实际 EPS 参考线
    actual_eps = FORECAST["基准"][2025]["eps"]
    fig.add_hline(y=actual_eps, line_dash="dot", line_color=C["dark"], opacity=0.5,
                  annotation=dict(text=f"2025实际 EPS={actual_eps:.2f}",
                                  font=dict(size=10, color=C["dark"])))

    fig.add_hline(y=0, line_dash="solid", line_color=C["gray"], opacity=0.5)
    fig.update_yaxes(title="EPS（元）")
    fig.update_xaxes(tickangle=0)
    fig.update_layout(
        title=dict(text="三种情景每股收益（EPS）预测", x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=420, hovermode="x unified", bargap=0.3, bargroupgap=0.12,
        template=PLOTLY_TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="left", x=0, font=dict(size=10)),
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
        margin=dict(l=55, r=30, t=80, b=55),
    )
    return fig


# ==================== Chart 5: 敏感性分析热力图 ====================

def ch5_sensitivity():
    """猪价 vs 成本对 EPS 的敏感性（2027E 基准）"""
    fc_base = FORECAST["基准"][2027]
    hog_base = fc_base["hog"]
    price_base = fc_base["price"]
    cost_base = fc_base["cost_per_kg"]

    # 猪价范围：基准 ±3 元/kg，步长 0.5
    price_vals = [round(price_base + d, 1) for d in [x/2 for x in range(-6, 7)]]
    # 成本范围：基准 ±2 元/kg，步长 0.5
    cost_vals = [round(cost_base + d, 1) for d in [x/2 for x in range(-4, 5)]]

    z_eps = []
    for cost in cost_vals:
        row = []
        for price in price_vals:
            hog_rev_raw = hog_base * AVG_WEIGHT * price / 1e4
            rev = hog_rev_raw * REV_MULTIPLIER
            hog_cost = hog_base * AVG_WEIGHT * cost / 1e4
            non_hog_rev = rev - hog_rev_raw
            non_hog_cost = non_hog_rev * NON_HOG_COST_RATE
            total_cost = hog_cost + non_hog_cost
            gross = rev - total_cost
            sale = rev * COST_RATES["sale_rate"] / 100
            mgmt = rev * COST_RATES["manage_rate"] / 100
            rd = rev * COST_RATES["rd_rate"] / 100
            fin = fc_base["fin_exp"]
            op = gross - sale - mgmt - rd - fin
            tax = op * TAX_RATE_HIGH if op > 100 else 0
            net = (op - tax) * 0.98
            eps = net / TOTAL_SHARES
            row.append(round(eps, 2))
        z_eps.append(row)

    price_labels = [f"{p}元" for p in price_vals]
    cost_labels = [f"{c}元" for c in cost_vals]

    fig = go.Figure(data=go.Heatmap(
        z=z_eps,
        x=price_labels,
        y=cost_labels,
        colorscale=[
            [0.0, C["red"]],
            [0.35, "#f5b7b1"],
            [0.5, "#ffffff"],
            [0.65, "#a9dfbf"],
            [1.0, C["green"]],
        ],
        zmid=0,
        text=[[f"{v:.2f}" for v in row] for row in z_eps],
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title=dict(text="EPS（元）", side="right")),
        xgap=1, ygap=1,
    ))

    # 标注基准点
    base_idx_p = price_vals.index(price_base) if price_base in price_vals else 6
    base_idx_c = cost_vals.index(cost_base) if cost_base in cost_vals else 4

    fig.update_yaxes(title="完全成本（元/kg）")
    fig.update_xaxes(title="生猪均价（元/kg）", tickangle=45)
    fig.update_layout(
        title=dict(text="敏感性分析：猪价 × 成本 → EPS（2027E 基准）", x=0.02, y=0.98,
                   font=dict(size=15, color="#1a1a1a")),
        height=440, hovermode="x unified",
        template=PLOTLY_TEMPLATE,
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=11, color="#1a1a1a"),
        margin=dict(l=55, r=30, t=80, b=80),
    )
    return fig


# ==================== Chart 6: 情景对比指标表 ====================

def ch6_scenario_table():
    """三种情景关键指标对比（2027E）"""
    scenarios = ["上行", "基准", "下行"]
    metrics = [
        ("猪价（元/kg）", "price", ".1f"),
        ("完全成本（元/kg）", "cost_per_kg", ".1f"),
        ("出栏量（万头）", "hog", ".0f"),
        ("营业收入（亿）", "total_rev", ".0f"),
        ("营业成本（亿）", "total_cost", ".0f"),
        ("毛利（亿）", "gross_profit", ".0f"),
        ("营业利润（亿）", "op_profit", ".0f"),
        ("净利润（亿）", "net_profit", ".0f"),
        ("归母净利润（亿）", "parent_profit", ".0f"),
        ("EBIT（亿）", "ebit", ".0f"),
        ("EPS（元）", "eps", ".2f"),
        ("毛利率", "gross_margin", ".1f"),
        ("净利率", "net_margin", ".1f"),
    ]

    # 使用 Plotly table
    header = ["指标"] + [f"{s}情景" for s in scenarios]
    cells = [[m[0] for m in metrics]]
    for sc in scenarios:
        fc = FORECAST[sc][2027]
        cells.append([f"{fc[m[1]]:{m[2]}}" + ("%" if m[1] in ("gross_margin", "net_margin") else "")
                      for m in metrics])

    fig = go.Figure(data=[go.Table(
        header=dict(values=header, fill_color=C["dark"],
                    font=dict(color="white", size=13), align="center", height=36),
        cells=dict(values=cells, fill_color=[["white", "#f8f9fa", "#f8f9fa", "#f8f9fa"]],
                   font=dict(size=12, color="#1a1a1a"), align="center", height=30),
    )])

    fig.update_layout(
        title=dict(text="三种情景关键指标对比（2027E）", x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=520, margin=dict(l=30, r=30, t=80, b=30),
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
    )
    return fig


# ==================== 辅助函数 ====================

def format_pl_table(scenario, year):
    """格式化单年利润表为 HTML"""
    fc = FORECAST[scenario][year]
    return f"""<table>
      <thead><tr><th>科目</th><th>{year}{'E' if year > 2025 else ''}</th><th>占营收%</th></tr></thead>
      <tbody>
        <tr><td>营业收入</td><td style="font-weight:600">{fc['total_rev']:,.0f} 亿</td><td>100.0%</td></tr>
        <tr><td>营业成本</td><td>{fc['total_cost']:,.0f} 亿</td><td>{fc['total_cost']/fc['total_rev']*100:.1f}%</td></tr>
        <tr style="font-weight:600"><td>毛利</td><td>{fc['gross_profit']:,.0f} 亿</td><td>{fc['gross_margin']:.1f}%</td></tr>
        <tr><td>销售费用</td><td>{fc['sale_exp']:,.0f} 亿</td><td>{fc['sale_exp']/fc['total_rev']*100:.1f}%</td></tr>
        <tr><td>管理费用</td><td>{fc['manage_exp']:,.0f} 亿</td><td>{fc['manage_exp']/fc['total_rev']*100:.1f}%</td></tr>
        <tr><td>研发费用</td><td>{fc['rd_exp']:,.0f} 亿</td><td>{fc['rd_exp']/fc['total_rev']*100:.1f}%</td></tr>
        <tr><td>财务费用</td><td>{fc['fin_exp']:,.0f} 亿</td><td>{fc['fin_exp']/fc['total_rev']*100:.1f}%</td></tr>
        <tr style="font-weight:700;color:{C['red'] if fc['op_profit'] < 0 else C['green']}">
          <td>营业利润</td><td>{fc['op_profit']:,.0f} 亿</td><td>{fc['op_profit']/fc['total_rev']*100:.1f}%</td></tr>
        <tr><td>利润总额</td><td>{fc['total_profit']:,.0f} 亿</td><td>{fc['total_profit']/fc['total_rev']*100:.1f}%</td></tr>
        <tr><td>所得税</td><td>{fc['income_tax']:,.0f} 亿</td><td>—</td></tr>
        <tr style="font-weight:700;font-size:15px;color:{C['red'] if fc['net_profit'] < 0 else C['dark']}">
          <td>净利润</td><td>{fc['net_profit']:,.0f} 亿</td><td>{fc['net_margin']:.1f}%</td></tr>
        <tr style="font-weight:700">
          <td>归母净利润</td><td>{fc['parent_profit']:,.0f} 亿</td><td>—</td></tr>
        <tr style="font-weight:700;font-size:16px">
          <td>EPS</td><td>{fc['eps']:.2f} 元</td><td>—</td></tr>
      </tbody></table>"""

def build_summary_table():
    """预测摘要表：三种情景三年核心指标"""
    rows = ""
    for sc in ["上行", "基准", "下行"]:
        for yr in [2026, 2027, 2028]:
            fc = FORECAST[sc][yr]
            color = C["green"] if fc["parent_profit"] > 0 else C["red"]
            rows += f"""<tr>
              <td>{sc}</td><td>{yr}E</td>
              <td>{fc['hog']:,}</td><td>{fc['price']}</td><td>{fc['cost_per_kg']}</td>
              <td>{fc['total_rev']:,.0f}</td>
              <td style="color:{color};font-weight:600">{fc['parent_profit']:,.0f}</td>
              <td style="color:{color};font-weight:600">{fc['eps']:.2f}</td>
            </tr>"""
    return f"""<table>
      <thead><tr><th>情景</th><th>年份</th><th>出栏(万头)</th><th>猪价(元/kg)</th><th>成本(元/kg)</th><th>营收(亿)</th><th>归母净利(亿)</th><th>EPS(元)</th></tr></thead>
      <tbody>{rows}</tbody></table>"""

def build_sensitivity_text():
    """敏感性分析文字"""
    base_hog = HOG_FORECAST[2027]
    # 收入影响：±1 元/kg → 活猪收入变动 = hog × weight × 1 / 1e4
    # 总营收变动 = 活猪收入变动 × 收入乘数
    raw_impact = base_hog * AVG_WEIGHT / 1e4  # 亿元/元
    rev_impact = raw_impact * REV_MULTIPLIER
    eps_impact = rev_impact * 0.98 / TOTAL_SHARES  # 简化：全部通过营收传导
    cost_impact = raw_impact  # 成本变动同样
    base_eps = FORECAST["基准"][2027]["eps"]

    return (f"<b>猪价敏感性：</b>猪价每变动 <b>±1 元/kg</b>，"
            f"活猪收入变动约 <b>±{raw_impact:.0f} 亿</b>，总营收变动约 <b>±{rev_impact:.0f} 亿</b>，"
            f"EPS 变动约 <b>±{eps_impact:.2f} 元</b>（占基准 2027E EPS {base_eps:.2f} 的 {abs(eps_impact/base_eps)*100:.0f}%）。<br>"
            f"<b>成本敏感性：</b>完全成本每变动 <b>±1 元/kg</b>，"
            f"营业成本变动约 <b>±{cost_impact:.0f} 亿</b>，EPS 变动约 <b>±{cost_impact * 0.98 / TOTAL_SHARES:.2f} 元</b>。<br>"
            f"<b>猪价和成本的敏感性几乎对称且均极高</b>——这解释了牧原盈利的剧烈周期性。")

def build_cycle_position():
    """周期位置分析"""
    # 获取最近季度猪价和阶段
    recent_qs = sorted([q for q in PIG_PRICE_Q.keys() if q >= "2023Q1"], reverse=True)[:6]
    recent_info = []
    for q in recent_qs:
        price = PIG_PRICE_Q[q]
        recent_info.append(f"{q}: {price:.1f}元/kg")

    sow_decline = ("2025Q4 末 3990 万头 → 2026Q1 3904 万头（-3.3% YoY）"
                   "→ Q2 3780 万头（-6.5% YoY，仅高出 3750 万头调控目标 0.8%）"
                   "→ 预计年底 ~3750 万头（接近正常保有量）")

    return (f"<b>当前周期位置（2026Q3）：</b>猪价处于周期低谷——最近季度均价 "
            f"{', '.join(reversed(recent_info))}。<br>"
            f"<b>供给端：</b>能繁母猪从 2024 年末 4078 万头持续下降，{sow_decline}。"
            f"按 10 个月生物时滞，2026 年的生猪出栏对应 2025 年高存栏→供给充裕→猪价低迷。"
            f"2027 年出栏对应 2026 年加速去化后的低存栏→供给收缩→猪价回升。<br>"
            f"<b>期货市场验证：</b>LH2611=12.07、LH2701=12.70、LH2705=13.45——"
            f"期货曲线已定价 2027 年猪价反弹至 12-13 元/kg，与基准假设一致。<br>"
            f"<b>结论：</b>2026 年全年处于周期下行/筑底阶段（行业性亏损），"
            f"2027 年进入周期反转的<b>概率较高</b>，但反转强度取决于去化速度。")

def build_cycle_check():
    """周期均值对比：现实检查"""
    # 计算周期历史均值
    cycle_yrs = [y for y in SORTED_YEARS if 2018 <= y <= 2025]
    avg8_parent = sum(FIN[yr]["parent_profit"] for yr in cycle_yrs) / len(cycle_yrs)
    avg5_parent = sum(FIN[yr]["parent_profit"] for yr in SORTED_YEARS if 2021 <= yr <= 2025) / 5
    avg8_eps = sum(FIN[yr]["eps"] for yr in cycle_yrs) / len(cycle_yrs)

    # 预测均值
    fc_parents = [FORECAST["基准"][yr]["parent_profit"] for yr in [2026, 2027, 2028]]
    fc_3yr_avg = sum(fc_parents) / 3

    return (f"<b>历史周期均值（2018-2025）：</b>归母净利润约 <b>{avg8_parent:,.0f} 亿</b>（EPS {avg8_eps:.2f}）。<br>"
            f"<b>近5年均值（2021-2025）：</b>归母净利润约 <b>{avg5_parent:,.0f} 亿</b>。<br>"
            f"<b>预测3年均值（2026-2028E 基准）：</b>归母净利润约 <b>{fc_3yr_avg:,.0f} 亿</b>。<br><br>"
            f"{'<b>✅ 现实检查通过：</b>预测均值与历史周期均值可比，无曲棍球棒现象。' if abs(fc_3yr_avg - avg8_parent) / max(abs(avg8_parent), 1) < 0.5 else '<b>⚠️ 需关注：</b>预测均值与历史均值偏差较大，请检查假设。'}")

def build_methodology():
    """预测方法论——解释预测依据和逻辑链条"""
    return (
        f"<b>预测方法：</b>因果关系法（Hooke 第 2 类）——销售收入由独立变量「出栏量 × 猪价」驱动。"
        f"<br><br><b>证据链（猪价预测依据）：</b>"
        f"<ol>"
        f"<li><b>供给领先指标：</b>能繁母猪存栏是猪价的 10 个月领先指标。"
        f"2025Q4 末存栏 3990 万头 → 2026 年出栏对应供给充裕 → 猪价低迷；"
        f"2026Q1 存栏降至 3904 万头（-3.3% YoY）→ Q2 加速去化至 3780 万头（-6.5% YoY）"
        f"→ 2027 年出栏对应供给收缩 → 猪价回升。Q2 存栏仅高出 3750 万头调控目标 0.8%。</li>"
        f"<li><b>期货市场定价：</b>大商所生猪期货 LH2611=12.07、LH2701=12.70、LH2705=13.45 元/kg——"
        f"市场预期 2027 年猪价 12-13 元/kg，与基准假设（12.5 元/kg）一致。</li>"
        f"<li><b>成本支撑：</b>行业完全成本普遍在 12-15 元/kg。猪价低于行业平均成本的时间不可持续——"
        f"持续亏损迫使高成本产能退出，从而推升价格。</li>"
        f"<li><b>历史周期规律：</b>2006 年以来中国经历 5 轮完整猪周期，每轮约 3-4 年。"
        f"本轮周期 2022Q2 见顶，2026 年是下行第 4 年——接近周期尾部。</li>"
        f"</ol>"
        f"<b>收入模型：</b>总营收 = 出栏量 × 均重 110kg × 猪价 × 收入乘数 {REV_MULTIPLIER}。"
        f"乘数来源于历史验证（2025 年 1441/(7798×110×14.4/1e4)=1.17），"
        f"反映屠宰溢价（猪肉售价 > 活猪价）和饲料/其他外销收入的增量贡献。"
        f"<br><br><b>成本模型：</b>营业成本 = 养殖成本（出栏量 × 均重 × 完全成本）+ 非养猪业务成本（增量收入 × 成本率 {NON_HOG_COST_RATE}）。"
        f"期间费用率基于近 3 年历史均值。"
    )

def build_valuation_preview():
    """估值预览——基于周期平均 EPS × 合理 PE"""
    cycle_yrs = [y for y in SORTED_YEARS if 2018 <= y <= 2025]
    avg8_eps = sum(FIN[yr]["eps"] for yr in cycle_yrs) / len(cycle_yrs)
    avg5_eps = sum(FIN[yr]["eps"] for yr in SORTED_YEARS if 2021 <= yr <= 2025) / 5

    # 牧原历史 PE 区间
    pe_low = 10   # 周期底部 PE
    pe_mid = 15   # 合理 PE
    pe_high = 22  # 周期顶部 PE

    # 基于 8 年周期均值
    val_low_8 = avg8_eps * pe_low
    val_mid_8 = avg8_eps * pe_mid
    val_high_8 = avg8_eps * pe_high

    # 基于 5 年近期均值
    val_low_5 = avg5_eps * pe_low
    val_mid_5 = avg5_eps * pe_mid
    val_high_5 = avg5_eps * pe_high

    # 当前股价参考（2026 年 7 月末约 38 元）
    current_price = "~38"

    return (f"<b>⚠️ 本节为估值预览——正式估值见第 6 步（使用 DCF + 相对价值法 + 并购价值法 + LBO 法交叉验证）。</b>"
            f"<br><br>"
            f"<b>简化估值（周期平均 EPS × 合理 PE）：</b>"
            f"<br>"
            f"· 基于 <b>8 年周期均值 EPS {avg8_eps:.2f}</b>："
            f"PE {pe_low}× = <b>{val_low_8:.0f} 元</b>（保守），"
            f"PE {pe_mid}× = <b>{val_mid_8:.0f} 元</b>（合理），"
            f"PE {pe_high}× = <b>{val_high_8:.0f} 元</b>（乐观）"
            f"<br>"
            f"· 基于 <b>近 5 年均值 EPS {avg5_eps:.2f}</b>："
            f"PE {pe_low}× = <b>{val_low_5:.0f} 元</b>（保守），"
            f"PE {pe_mid}× = <b>{val_mid_5:.0f} 元</b>（合理），"
            f"PE {pe_high}× = <b>{val_high_5:.0f} 元</b>（乐观）"
            f"<br><br>"
            f"<b>合理估值区间（8 年均值）：{val_low_8:.0f} - {val_mid_8:.0f} 元/股</b>"
            f"<br>"
            f"当前股价约 {current_price} 元，处于合理估值区间内。"
            f"<br><br>"
            f"<b>安全边际考量：</b>若取 8 年周期均值 PE 12×（更保守）= <b>{avg8_eps * 12:.0f} 元</b>，"
            f"当前价格 {current_price} 元较此有 "
            f"{(float(current_price.replace('~','')) - avg8_eps * 12) / (avg8_eps * 12) * 100:+.0f}% 的溢价。"
            f"下行保护有限——投资需依赖猪价周期反转的催化。"
    )

# ==================== HTML 模板 ====================

STYLE = """body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;margin:0;background:#fff;color:#1a1a1a;font-size:15px;line-height:1.7}
.header{border-bottom:1px solid #e0e0e0;padding:36px 40px 28px}
.header h1{margin:0;font-size:22px;font-weight:600}
.header .sub{color:#999;margin-top:8px;font-size:13px}
.container{max-width:900px;margin:0 auto;padding:32px 24px 80px}
.section{padding:0;margin:40px 0}
.section h2{font-size:16px;font-weight:600;padding-bottom:8px;border-bottom:1px solid #e0e0e0;margin:0 0 16px}
.section h3{font-size:14px;font-weight:600;color:#555;margin:18px 0 8px}
.section p,.section li{font-size:14px;line-height:1.8;color:#444}
table{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0}
th,td{border-bottom:1px solid #eee;padding:8px 10px;text-align:left;vertical-align:top}
th{font-weight:500;color:#888;font-size:12px;letter-spacing:.3px}
.source{font-size:11px;color:#bbb;margin-bottom:8px}
.box{border-left:2px solid #3498db;padding:12px 18px;margin:16px 0}
.box-red{border-left:2px solid #c0392b;padding:12px 18px;margin:16px 0}
.box-green{border-left:2px solid #27ae60;padding:12px 18px;margin:16px 0}
.box-orange{border-left:2px solid #e67e22;padding:12px 18px;margin:16px 0}
.col2{display:grid;grid-template-columns:1fr 1fr;gap:32px}
@media(max-width:680px){.col2{grid-template-columns:1fr}}"""

FOOTER = f"""<div class="footer" style="text-align:center;padding:30px;color:#bbb;font-size:12px">
  牧原股份 (002714.SZ) — 财务预测报告 · 第 5 步<br>
  方法论：Graham & Dodd / Hooke 证券分析框架 · 预测日期：{TODAY_STR}
</div>"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>财务预测 — 牧原股份 (002714.SZ)</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>{style}</style>
</head>
<body>
<div class="header">
  <h1>财务预测 — 牧原股份 (002714.SZ)</h1>
  <div class="sub">证券分析 · 第 5 步 · {today} · 预测期 2026-2028E</div>
</div>
<div class="container">

  <!-- 0. 预测摘要 -->
  <div class="section">
    <h2>0. 预测摘要</h2>
    <p class="source">来源：假设基于历史财务数据、生猪期货远期曲线、产能数据及行业周期分析</p>
    <div class="box">
      <p style="margin:0"><b>核心假设（基准情景）：</b><br>
      ① 出栏量：2026E 8,100 万头 → 2028E 8,500 万头（增速放缓至 2-3%）<br>
      ② 猪价：2026E 10.5 元/kg（亏损年）→ 2027E 12.5 → 2028E 13.5（周期温和复苏）<br>
      ③ 完全成本：2026E 11.5 → 2028E 11.0 元/kg（持续降本）<br>
      ④ <b>基准情景含 2026 年全年下行（行业性亏损），满足周期型公司预测要求</b>
      </p>
    </div>
    {summary_table}
  </div>

  <!-- 0b. 预测方法论 -->
  <div class="section">
    <h2>0b. 预测方法论与依据</h2>
    <p class="source">来源：Hooke 财务预测第 2-3 步——销售收入方法匹配 + 自上而下假设设定</p>
    <div class="box">
      <p style="margin:0">{methodology}</p>
    </div>
  </div>

  <!-- 1. 出栏量与猪价假设 -->
  <div class="section">
    <h2>1. 出栏量与猪价假设</h2>
    <p class="source">来源：出栏量——公司公告+产能数据；猪价——生猪期货+周期分析</p>
    <div>{ch1}</div>
    <p>{hog_price_text}</p>
  </div>

  <!-- 2. 三种情景猪价路径 -->
  <div class="section">
    <h2>2. 三种情景猪价路径</h2>
    <p class="source">来源：历史猪价——国家统计局/行情宝；期货——大商所 LH 合约（2026-07-28 收盘）；情景假设——基于能繁母猪存栏趋势</p>
    <div>{ch2}</div>
    <h3>情景逻辑</h3>
    <ul>
      <li><b>上行情景：</b>能繁母猪去化超预期（降至 3700 万头以下）+ 消费复苏 + 疫病扰动供给 → 猪价强劲反弹至 14-15.5 元/kg</li>
      <li><b>基准情景（最佳猜测）：</b>产能温和去化 + 正常消费 → 2027 年猪价回升至 12.5 元/kg（盈亏平衡之上），2028 年正常化至 13.5</li>
      <li><b>下行情景：</b>去化缓慢、效率提升抵消存栏下降 + 消费持续疲软 + 进口增加 → 猪价长期在 11-11.5 元/kg 低位徘徊</li>
    </ul>
  </div>

  <!-- 2b. 周期位置分析 -->
  <div class="section">
    <h2>2b. 周期位置研判</h2>
    <p class="source">来源：季度猪价数据——国家统计局/行情宝；能繁母猪存栏——农业农村部；期货——大商所</p>
    <div class="box">
      <p style="margin:0">{cycle_position}</p>
    </div>
  </div>

  <!-- 3. 利润表预测 -->
  <div class="section">
    <h2>3. 利润表预测（基准情景）</h2>
    <p class="source">来源：基于上述假设，自上而下构建预测利润表</p>
    <div>{ch3}</div>
    <h3>基准情景三年利润表</h3>
    <div class="col2">
      <div>{pl_2026}</div>
      <div>{pl_2027}</div>
    </div>
    <div style="margin-top:16px">{pl_2028}</div>
  </div>

  <!-- 4. 三种情景对比 -->
  <div class="section">
    <h2>4. 三种情景对比</h2>
    <p class="source">来源：三种情景的完整利润表预测</p>
    <div>{ch4}</div>
    <div style="margin-top:16px">{ch6}</div>
  </div>

  <!-- 5. 敏感性分析 -->
  <div class="section">
    <h2>5. 敏感性分析</h2>
    <p class="source">来源：基于 2027E 基准情景，变动猪价和出栏量假设</p>
    <div>{ch5}</div>
    <div class="box-orange">
      <p style="margin:0">{sensitivity_text}</p>
    </div>
  </div>

  <!-- 6. 风险因素 -->
  <div class="section">
    <h2>6. 关键风险与不确定性</h2>
    <ol>
      <li><b>猪价预测是最不确定的变量：</b>猪价受能繁母猪存栏、疫病、政策（收储/放储）、进口、消费替代等多因素影响，历史上预测误差可超过 ±30%</li>
      <li><b>出栏量不及预期：</b>2026Q1 能繁母猪 313 万头（较 2025 年末 323 万头下降 3%），若持续去化可能影响 2027 年出栏潜力</li>
      <li><b>成本下降速度：</b>饲料原料（玉米/豆粕）价格受国际市场和天气影响，成本下降路径可能不线性</li>
      <li><b>曲棍球棒风险：</b>基准情景 2027 年盈利大幅回升（从亏损→盈利），需警惕过度乐观。上行情景（2027E EPS {upside_eps_2027:.2f} 元）历史上仅在 2020 年超级周期出现过</li>
      <li><b>港股摊薄：</b>H 股发行增加总股本约 4%，未来若进一步融资可能稀释 EPS</li>
      <li><b>模型局限：</b>预测基于年化均价，未细化季度波动；收入乘数和费用率基于历史均值，结构性变化（如屠宰占比持续提升）可能改变参数</li>
    </ol>
  </div>

  <!-- 7. 现实检查——与历史周期均值对比 -->
  <div class="section">
    <h2>7. 现实检查</h2>
    <p class="source">来源：Hooke 财务预测第 7 步——将预测结果与历史数据进行对比验证</p>
    <div class="box-green">
      <p style="margin:0">{cycle_check}</p>
    </div>
    <p style="margin-top:12px">根据 Hooke 方法论，周期型公司估值应使用<b>整个周期的平均盈利</b>（第 6 步估值将使用近 5 年均值 EPS {avg5_eps_val:.2f} 元 和 8 年均值 EPS {avg8_eps_val:.2f} 元作为估值参数）。</p>
  </div>

  <!-- 8. 估值预览 -->
  <div class="section">
    <h2>8. 估值预览（简化）</h2>
    <p class="source">来源：周期平均 EPS × 合理 PE 倍数——正式估值见第 6 步（DCF + 相对价值法 + 并购 + LBO）</p>
    <div class="box-orange">
      <p style="margin:0">{valuation_preview}</p>
    </div>
  </div>

</div><!-- container -->
{footer}
</body>
</html>"""

# ==================== 主函数 ====================

def main():
    print("\n" + "=" * 60)
    print("牧原股份 财务预测 — 第 5 步")
    print("=" * 60)

    # 生成图表
    chart_funcs = [
        ("ch1", ch1_rev_hog),
        ("ch2", ch2_price_scenarios),
        ("ch3", ch3_waterfall),
        ("ch4", ch4_eps),
        ("ch5", ch5_sensitivity),
        ("ch6", ch6_scenario_table),
    ]

    chart_html = {}
    for name, func in chart_funcs:
        try:
            fig = func()
            chart_html[name] = fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                                           config={"responsive": True, "displayModeBar": False})
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            import traceback; traceback.print_exc()
            chart_html[name] = f"<p style='color:#c0392b'>图表生成失败: {e}</p>"

    # 生成文本
    hog_price_text = (
        f"<b>出栏量：</b>2025 年出栏 7,798 万头（+8.9%），2026H1 实际 3,862 万头。"
        f"公司战略从高速扩张转为稳健增长，预计 2026-2028 年出栏增速放缓至 2-5%，"
        f"2028E 达 8,500 万头（接近当前产能上限 {CAPACITY:,} 万头/年）。"
        f"<br><b>猪价路径：</b>2026Q1 均价 11.56、Q2 9.48、Q3(至8月初) ~10.7 元/kg——上半年行业深度亏损。"
        f"2026H2 预计猪价温和反弹至 11-12 元/kg（季节性+产能去化传导），全年均价 10.5 元/kg。"
        f"期货 LH2611=12.07、LH2705=13.45 暗示 2027 年回升至 12-13 元/kg 区间，"
        f"叠加能繁母猪加速去化（2026Q1: 3,904 万头/-3.3% YoY → Q2: 3,780 万头/-6.5% YoY，已接近 3,750 万头调控目标），基准假设 2027E 均价 12.5 元/kg。"
    )

    # 历史均值
    cycle_yrs = [y for y in SORTED_YEARS if 2018 <= y <= 2025]
    avg8_eps_val = sum(FIN[yr]["eps"] for yr in cycle_yrs) / len(cycle_yrs)
    avg5_eps_val = sum(FIN[yr]["eps"] for yr in SORTED_YEARS if 2021 <= yr <= 2025) / 5

    upside_eps_2027 = FORECAST["上行"][2027]["eps"]

    # 组装 HTML
    html = HTML.format(
        style=STYLE,
        today=TODAY_STR,
        summary_table=build_summary_table(),
        methodology=build_methodology(),
        ch1=chart_html["ch1"], ch2=chart_html["ch2"], ch3=chart_html["ch3"],
        ch4=chart_html["ch4"], ch5=chart_html["ch5"], ch6=chart_html["ch6"],
        hog_price_text=hog_price_text,
        cycle_position=build_cycle_position(),
        pl_2026=format_pl_table("基准", 2026),
        pl_2027=format_pl_table("基准", 2027),
        pl_2028=format_pl_table("基准", 2028),
        sensitivity_text=build_sensitivity_text(),
        cycle_check=build_cycle_check(),
        valuation_preview=build_valuation_preview(),
        upside_eps_2027=upside_eps_2027,
        avg5_eps_val=avg5_eps_val,
        avg8_eps_val=avg8_eps_val,
        footer=FOOTER,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"\n✅ 报告已生成: {REPORT_PATH}")
    print(f"   文件大小: {REPORT_PATH.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
