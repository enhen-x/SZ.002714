# -*- coding: utf-8 -*-
"""
牧原股份估值分析 — 牧原股份 (SZ.002714)
证券分析八步流程 · 第6步：估值

市场验证估值框架（替代旧四方法加权，旧框架未经验证已删除）：
  1. §1-2 成长阶段划分（小盘期/扩张期/成熟大盘期）+ 阶段估值分布
  2. §4 成熟期估值模型验证：PB / 周期均值PE / PS / TTM PE 对比
     → 周期均值PE（公平价值）+ PB（峰值预测）胜出，TTM PE 否决
  3. §5 峰值预测：PB 3.9-4.3×（2025 成熟期峰值实测）× 财务预测 2028E BPS

周期型公司调整：使用完整周期平均盈利；公平价值 43-54 元，2028 峰值基准 66-73 / 上行 90-99 元
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "估值报告.html"
TODAY_STR = datetime.now().strftime("%Y-%m-%d")

# ==================== 颜色常量（与前序报告一致） ====================
C = {
    "blue": "#3498db",     "red": "#c0392b",      "green": "#27ae60",
    "orange": "#e67e22",   "purple": "#8e44ad",   "dark": "#2c3e50",
    "gray": "#7f8c8d",     "teal": "#1abc9c",     "midblue": "#2980b9",
    "darkgreen": "#1e8449", "gold": "#f39c12",
}
PLOTLY_TEMPLATE = "plotly_white"

# ==================== 数据加载（复用 analyze_forecast.py 逻辑） ====================

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
    return annual.sort_values("_year")

# 加载财务数据
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
        # D&A = 固定资产折旧 + 使用权资产摊销（仅计FA_IR_DEPR避免与OILGAS_BIOLOGY_DEPR重复）
        "depreciation": (safe_float(cf.get("FA_IR_DEPR"), 0) + safe_float(cf.get("USERIGHT_ASSET_AMORTIZE"), 0)) / 1e8,
        "roe": safe_float(ind.get("ROEJQ"), 0) if ind is not None else None,
    }
    rev = d["revenue"]
    if rev > 0:
        d["gross_margin_calc"] = (rev - d["operate_cost"]) / rev * 100
        d["net_margin"] = d["net_profit"] / rev * 100
    else:
        d["gross_margin_calc"] = 0
        d["net_margin"] = 0
    d["interest_debt"] = d["short_loan"] + d["long_loan"] + d.get("notes_payable", 0)
    # EBITDA
    d["ebit"] = d["total_profit"] + d["interest_exp"]
    d["ebitda"] = d["ebit"] + d.get("depreciation", 0)
    # Debt ratio
    d["debt_ratio"] = d["total_liab"] / d["total_assets"] * 100 if d["total_assets"] > 0 else 0
    d["ocf_to_np"] = d["ocf"] / d["net_profit"] if d["net_profit"] != 0 else 99
    d["ebit_int_cover"] = d["ebit"] / d["interest_exp"] if d["interest_exp"] > 0 else 99
    FIN[yr] = d

SORTED_YEARS = sorted(FIN.keys())
LATEST = max(SORTED_YEARS)
print(f"财务数据: {SORTED_YEARS[0]}-{LATEST} ({len(SORTED_YEARS)} 年)")

# ==================== 关键参数 ====================

TOTAL_SHARES = 54.7        # 亿股（含H股）
CURRENT_PRICE = 39.3        # 2026-07-28 收盘价
CURRENT_MKT_CAP = CURRENT_PRICE * TOTAL_SHARES  # ~2150 亿

# 周期平均盈利（估值核心参数）
CYCLE_8Y = [y for y in SORTED_YEARS if 2018 <= y <= 2025]
CYCLE_5Y = [y for y in SORTED_YEARS if 2021 <= y <= 2025]

AVG8_EPS = sum(FIN[yr]["eps"] for yr in CYCLE_8Y) / len(CYCLE_8Y)
AVG5_EPS = sum(FIN[yr]["eps"] for yr in CYCLE_5Y) / len(CYCLE_5Y)
AVG8_PARENT = sum(FIN[yr]["parent_profit"] for yr in CYCLE_8Y) / len(CYCLE_8Y)
AVG5_PARENT = sum(FIN[yr]["parent_profit"] for yr in CYCLE_5Y) / len(CYCLE_5Y)
AVG8_EBIT = sum(FIN[yr]["ebit"] for yr in CYCLE_8Y) / len(CYCLE_8Y)
AVG8_EBITDA = sum(FIN[yr]["ebitda"] for yr in CYCLE_8Y) / len(CYCLE_8Y)
AVG8_FCF = sum((FIN[yr]["ocf"] + FIN[yr]["capex"]) for yr in CYCLE_8Y) / len(CYCLE_8Y)  # capex is negative

print(f"周期均值: 8Y EPS={AVG8_EPS:.2f}, 5Y EPS={AVG5_EPS:.2f}")
print(f"8Y 归母={AVG8_PARENT:.0f}亿, 8Y EBITDA={AVG8_EBITDA:.0f}亿, 8Y FCF={AVG8_FCF:.0f}亿")

# ==================== 预测数据（从 FORECAST 模型加载） ====================

# 复用 analyze_forecast.py 的核心假设
AVG_WEIGHT = 110
REV_MULTIPLIER = 1.16
NON_HOG_COST_RATE = 0.90
INTEREST_RATE = 0.035
TAX_RATE_LOW = 0.0
TAX_RATE_HIGH = 0.05
COST_RATES = {"sale_rate": 0.23, "manage_rate": 0.92, "rd_rate": 1.15}

HOG_FORECAST = {2025: 7798, 2026: 8100, 2027: 8300, 2028: 8500}
PRICE_SCENARIOS = {
    "上行": {2025: 14.4, 2026: 11.0, 2027: 14.0, 2028: 15.5},
    "基准": {2025: 14.4, 2026: 10.5, 2027: 12.5, 2028: 13.5},
    "下行": {2025: 14.4, 2026: 10.0, 2027: 11.0, 2028: 11.5},
}
COST_SCENARIOS = {
    "上行": {2025: 12.0, 2026: 11.5, 2027: 11.5, 2028: 11.3},
    "基准": {2025: 12.0, 2026: 11.5, 2027: 11.3, 2028: 11.0},
    "下行": {2025: 12.0, 2026: 11.8, 2027: 11.5, 2028: 11.3},
}

def project_ebit_eps(scenario, year):
    """返回 (ebit, eps, revenue, interest_exp, total_profit)"""
    hog = HOG_FORECAST.get(year, 8500)
    price = PRICE_SCENARIOS[scenario][year]
    cost_per_kg = COST_SCENARIOS[scenario][year]  # 分情景成本（与 Step 5 财务预测一致）

    hog_rev_raw = hog * AVG_WEIGHT * price / 1e4
    total_rev = hog_rev_raw * REV_MULTIPLIER
    hog_cost = hog * AVG_WEIGHT * cost_per_kg / 1e4
    non_hog_rev = total_rev - hog_rev_raw
    non_hog_cost = non_hog_rev * NON_HOG_COST_RATE
    total_cost = hog_cost + non_hog_cost
    gross_profit = total_rev - total_cost

    sale_exp = total_rev * COST_RATES["sale_rate"] / 100
    manage_exp = total_rev * COST_RATES["manage_rate"] / 100
    rd_exp = total_rev * COST_RATES["rd_rate"] / 100

    base_debt = FIN[LATEST]["interest_debt"]
    debt_reduction = {2025: 0, 2026: 25, 2027: 55, 2028: 85, 2029: 100, 2030: 115}
    net_debt = max(base_debt - debt_reduction.get(year, 0), base_debt * 0.6)
    fin_exp = net_debt * INTEREST_RATE
    interest_exp = fin_exp

    op_profit = gross_profit - sale_exp - manage_exp - rd_exp - fin_exp
    total_profit = op_profit
    ebit = total_profit + interest_exp

    tax_rate = TAX_RATE_HIGH if total_profit > 100 else TAX_RATE_LOW
    income_tax = max(total_profit * tax_rate, 0)
    net_profit = total_profit - income_tax
    parent_profit = net_profit * 0.98
    eps = parent_profit / TOTAL_SHARES

    return ebit, eps, total_rev, interest_exp, total_profit

FORECAST = {}
for sc in ["上行", "基准", "下行"]:
    FORECAST[sc] = {}
    for yr in [2025, 2026, 2027, 2028]:
        ebit, eps, rev, ie, tp = project_ebit_eps(sc, yr)
        da_est = rev * 0.10
        FORECAST[sc][yr] = {"ebit": ebit, "eps": eps, "revenue": rev,
                            "interest_exp": ie, "total_profit": tp,
                            "ebitda": ebit + da_est, "da": da_est}

# ── 生猪期货远期曲线 ──
df_futures = pd.read_csv(ROOT / "data" / "生猪期货远期曲线.csv")
FUTURES_CURVE = []
for _, row in df_futures.iterrows():
    price = pd.to_numeric(row.get("期货价格_元每公斤", row.get("price", 0)), errors="coerce")
    if pd.notna(price) and price > 0:
        contract = str(row.get("symbol", row.get("contract", "")))
        volume = float(pd.to_numeric(row.get("持仓量", row.get("volume", 0)), errors="coerce"))
        FUTURES_CURVE.append({"month": contract, "price": float(price), "volume": volume})
print(f"生猪期货远期曲线 ({len(FUTURES_CURVE)} 个合约):")
for fc in FUTURES_CURVE:
    print(f"  {fc['month']}: {fc['price']:.2f}元/kg (持仓{fc['volume']:,})")

# 期货隐含均价 (合约代码格式: LH2609 = 2026年9月)
futures_2026h2 = [fc for fc in FUTURES_CURVE if "LH2609" in fc["month"] or "LH2611" in fc["month"]]
futures_2027h1 = [fc for fc in FUTURES_CURVE if "LH2701" in fc["month"] or "LH2703" in fc["month"] or "LH2705" in fc["month"]]
avg_futures_2026h2 = sum(fc["price"] for fc in futures_2026h2) / len(futures_2026h2) if futures_2026h2 else 0
avg_futures_2027h1 = sum(fc["price"] for fc in futures_2027h1) / len(futures_2027h1) if futures_2027h1 else 0
print(f"  期货隐含2026H2均价: {avg_futures_2026h2:.2f}元/kg")
print(f"  期货隐含2027H1均价: {avg_futures_2027h1:.2f}元/kg")

# ── 期货市场变量（供 §3 使用） ──
base_price = PRICE_SCENARIOS["基准"][2027]
sc_base_price = base_price
lh2611 = next((fc["price"] for fc in FUTURES_CURVE if "LH2611" in fc["month"]), 0)
lh2705 = next((fc["price"] for fc in FUTURES_CURVE if "LH2705" in fc["month"]), 0)
futures_vs_base = "高于" if avg_futures_2027h1 > base_price else ("低于" if avg_futures_2027h1 < base_price else "等于")
futures_scenario_label = "上行" if avg_futures_2027h1 > base_price + 1 else ("基准" if abs(avg_futures_2027h1 - base_price) <= 1 else "下行")

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

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>估值分析 — 牧原股份 (002714.SZ)</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>{style}</style>
</head>
<body>
<div class="header">
  <h1>估值分析 — 牧原股份 (002714.SZ)</h1>
  <div class="sub">证券分析 · 第 6 步 · {today} · 周期型公司 · 市场验证估值模型</div>
</div>
<div class="container">

  <!-- 1. 股价与估值指标的历史演进 -->
  <div class="section">
    <h2>1. 股价与估值指标的历史演进 — 基于市值阶段的估值框架</h2>
    <p class="source">来源：本地不复权日线 × 单季财报摊薄EPS/BPS/营收 × 年度资产负债表归母权益（股本估算=归母权益/BPS）。月度频率（2014-2026），季报数据前向填充到月。</p>
    {eps_price_ch12}
    <p style="font-size:12px;color:#888">两张图：① 月度股价+PB双面板（按四个成长阶段背景着色）→ ② PE/PS/总市值三面板，展示估值指标的完整演进。核心发现：<b>随着市值从小盘→中盘→大盘→成熟大盘，PE的极端值频率和幅度持续下降，季振幅从50%+降至~20%——大市值公司的定价更理性、更基本面驱动。</b>当前牧原已进入成熟大盘阶段（~2500亿市值），适用以周期均值PE为核心的估值框架。</p>
  </div>

  <!-- 2. 统计量化分析 -->
  <div class="section">
    <h2>2. 各阶段估值分布与当前分位数</h2>
    <p class="source">来源：基于第1节月度估值数据（PB/PE/PS），按三阶段（小盘期/扩张期/成熟大盘期）分组统计分布特征。分位数仅在当前所处阶段（成熟大盘期）内比较——跨阶段比较会因规模、盈利结构差异而失真。</p>
    {stage_dist_ch12}
  </div>

  <!-- 3. 期货市场 -->
  <div class="section">
    <h2>3. 期货市场隐含猪价 vs 模型假设</h2>
    <p class="source">来源：大连商品交易所 生猪期货 LH合约。期货反映市场对远期猪价的真实资金投票，用于校准模型假设。</p>
    <div class="box-orange">
      <p style="margin:0">
        <b>期货 vs 模型关键对比：</b><br>
        · <b>LH2611 (2026年11月) = {lh2611:.2f}元/kg</b> — 期货隐含2026年末猪价<br>
        · <b>LH2705 (2027年5月) = {lh2705:.2f}元/kg</b> — 期货隐含2027H1均价≈{avg_fut_2027h1:.2f}元/kg，{futures_vs_base}模型基准({sc_base_price:.1f})<br>
        · <b>期货定价偏向：{futures_scenario_label}情景</b> — 市场资金投票的猪价路径<br><br>
        <b>投资含义：</b><br>
        ① 期货仅覆盖到2027年5月，更远期的周期高峰（16-22元/kg）尚未在期货中定价——这是潜在的<b>超额收益来源</b><br>
        ② 期货市场正在定价中等强度的猪价复苏，复苏节奏取决于产能去化速度<br>
        ③ <b>核心矛盾：当前股价是否已反映期货隐含的复苏预期？</b>——需要结合估值框架判断
      </p>
    </div>
  </div>

  <!-- 4. 成熟期估值模型验证 -->
  <div class="section">
    <h2>4. 成熟期估值模型验证 — 用市场数据决定哪个模型最合适</h2>
    <p class="source">来源：成熟大盘期（2022-01 至今，56 个月）月度不复权股价 × 单季财报 BPS/TTM EPS/TTM 营收 × 滚动8Y周期均值EPS。判定标准：倍数稳定性（IQR/中位）、拟合误差（中位倍数隐含价 vs 实际价 MAD）、全程可定义性。</p>
    {stage_model_ch14}
  </div>

  <!-- 5. 峰值预测 -->
  <div class="section">
    <h2>5. 财务预测 → 周期峰值预测（市场验证模型）</h2>
    <p class="source">来源：财务预测三情景（2026-2028E EPS）→ 滚动 2028E BPS → × 成熟期实测峰值倍数（PB 3.9-4.3×，校准自 2025 年峰值：股价 59.68/BPS 14.04=4.25×）。</p>
    {peak_forecast_ch15}
  </div>

  <!-- 6. 数据来源与局限性 -->
  <div class="section">
    <h2>6. 数据来源与局限性</h2>
    <ul>
      <li><b>模型验证局限：</b>成熟期分布仅 56 个月（2022-01 至今），样本期覆盖一轮完整盈亏周期但历史较短；分位数是参照而非结论</li>
      <li><b>峰值倍数递减风险：</b>峰值 PB 存在递减趋势（2022 过渡期 5.1× → 2025 成熟期 4.25×），H 股发行摊薄 BPS，实际峰值可能低于预测</li>
      <li><b>周期均值 EPS 窗口敏感：</b>8 年滚动窗口把 2026 年创纪录亏损计入均值，公平价值与峰值预测对窗口选择敏感</li>
      <li><b>预测假设依赖：</b>峰值预测依赖财务预测三情景（猪价、出栏、成本），实际走势可能与三种情景均不同</li>
      <li><b>数据新鲜度：</b>市场行情截止 2026-07-28；财务报表截止 2025 年报；预测基于 2026Q2 数据</li>
    </ul>
  </div>

</div>
<div style="text-align:center;padding:30px;color:#bbb;font-size:12px">
  牧原股份 (002714.SZ) — 估值报告 · 第 6 步<br>
  方法论：Graham & Dodd / Hooke 证券分析框架 · 分析日期：{today}
</div>
</body>
</html>"""

# ==================== 主函数 ====================

# 跨函数数据缓存（ch12→ch13 共享）
_CH12_CACHE = {"monthly": None, "stage_ranges": None, "stage_stats": None}
_CH14_CACHE = {"pecyc_st": None}

def ch12_eps_price_relationship():
    """股价与估值指标的历史演进 — 基于市值阶段的估值框架

    图1: 月度不复权股价 + PB 双面板，按成长阶段背景着色
    图2: PE(TTM) + PS(TTM) + 总市值 三面板，展示估值指标完整演进
    """
    # ── 1. 月度股价 ──
    daily_csv = ROOT / "data" / "牧原_日线股价.csv"
    df_daily = pd.read_csv(daily_csv)
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    df_daily["month"] = df_daily["date"].dt.to_period("M")
    monthly = df_daily.groupby("month")["close"].last().reset_index()
    monthly["month_dt"] = monthly["month"].dt.to_timestamp()
    monthly["yr"] = monthly["month_dt"].dt.year

    # ── 2. 季度财报 + TTM ──
    df_qf = pd.read_csv(ROOT / "data" / "主要财务指标_按单季度.csv", dtype=str)
    df_qf["REPORT_DATE"] = pd.to_datetime(df_qf["REPORT_DATE"])
    df_qf["EPSJB"] = pd.to_numeric(df_qf["EPSJB"], errors="coerce")
    df_qf["BPS"] = pd.to_numeric(df_qf["BPS"], errors="coerce")
    df_qf["TOTALOPERATEREVE"] = pd.to_numeric(df_qf["TOTALOPERATEREVE"], errors="coerce")
    df_qf = df_qf.sort_values("REPORT_DATE").reset_index(drop=True)
    df_qf["ttm_eps"] = df_qf["EPSJB"].rolling(4, min_periods=4).sum()
    df_qf["ttm_rev"] = df_qf["TOTALOPERATEREVE"].rolling(4, min_periods=4).sum()
    df_qf["quarter"] = df_qf["REPORT_DATE"].dt.to_period("Q")

    # ── 3. 年度股本 ──
    bs = pd.read_csv(ROOT / "data" / "资产负债表_按报告期.csv")
    bs["REPORT_DATE"] = pd.to_datetime(bs["REPORT_DATE"])
    bs["TOTAL_PARENT_EQUITY"] = pd.to_numeric(bs["TOTAL_PARENT_EQUITY"], errors="coerce")
    bs_q4 = bs[bs["REPORT_DATE"].dt.month == 12][["REPORT_DATE", "TOTAL_PARENT_EQUITY"]].copy()
    bs_q4["year"] = bs_q4["REPORT_DATE"].dt.year
    qf_q4 = df_qf[df_qf["REPORT_DATE"].dt.month == 12][["REPORT_DATE", "BPS"]].copy()
    qf_q4["year"] = qf_q4["REPORT_DATE"].dt.year
    shares_yr = bs_q4.merge(qf_q4, on="year")
    shares_yr["shares"] = shares_yr["TOTAL_PARENT_EQUITY"] / shares_yr["BPS"] / 1e8
    shares_map = {int(r["year"]): r["shares"] for _, r in shares_yr.iterrows()}
    shares_map[2026] = shares_map.get(2025, 55.0)
    monthly["shares"] = monthly["yr"].map(shares_map).ffill()

    # ── 4. 季度指标→月度 ──
    qtr_bps, qtr_ttm_eps, qtr_ttm_rev = {}, {}, {}
    for _, r in df_qf.iterrows():
        q = r["quarter"]
        if pd.notna(r["BPS"]): qtr_bps[q] = float(r["BPS"])
        if pd.notna(r["ttm_eps"]): qtr_ttm_eps[q] = float(r["ttm_eps"])
        if pd.notna(r["ttm_rev"]): qtr_ttm_rev[q] = float(r["ttm_rev"])
    monthly["quarter"] = monthly["month_dt"].dt.to_period("Q")
    monthly["bps"] = monthly["quarter"].map(qtr_bps).ffill()
    monthly["ttm_eps"] = monthly["quarter"].map(qtr_ttm_eps).ffill()
    monthly["ttm_rev"] = monthly["quarter"].map(qtr_ttm_rev).ffill()

    monthly = monthly[(monthly["month_dt"] >= pd.Timestamp("2014-01-01")) &
                      (monthly["bps"].notna())].reset_index(drop=True)

    # ── 5. 估值指标 ──
    monthly["mkt_cap"] = monthly["close"] * monthly["shares"]
    monthly["pb"] = monthly["close"] / monthly["bps"]
    monthly["pe"] = np.where(
        (monthly["ttm_eps"].notna()) & (abs(monthly["ttm_eps"]) > 0.05),
        monthly["close"] / monthly["ttm_eps"], np.nan)
    monthly["ps"] = np.where(
        (monthly["ttm_rev"].notna()) & (monthly["ttm_rev"] > 1000),
        monthly["mkt_cap"] / (monthly["ttm_rev"] / 1e8), np.nan)

    mdates = monthly["month_dt"].tolist()
    n_m = len(monthly)

    # ── 6. 成长阶段划分 ──
    stages_def = [
        {"label": "小盘期 2014-2018", "yr_max": 2018,
         "color": "rgba(243,156,18,0.10)", "desc": "出栏扩张期，散户主导定价"},
        {"label": "扩张期 2019-2021", "yr_max": 2021,
         "color": "rgba(52,152,219,0.10)", "desc": "非瘟超级周期，盈利爆发式增长"},
        {"label": "成熟大盘期 2022-至今", "yr_max": 2026,
         "color": "rgba(46,204,113,0.10)", "desc": "周期回归，机构主导定价"},
    ]

    stage_ranges = []
    prev_bound = pd.Timestamp("2014-01-01")
    for st in stages_def:
        end_date = pd.Timestamp(f"{st['yr_max']}-12-31")
        if end_date >= prev_bound:
            stage_ranges.append((prev_bound, end_date, st))
            prev_bound = end_date + pd.Timedelta(days=1)

    # ═══ 图1: 月度股价 + PB 双面板 ═══
    fig1 = make_subplots(
        rows=2, cols=1,
        subplot_titles=("<b>月度不复权收盘价（2014-2026）</b>",
                         "<b>月度PB = 股价/BPS</b>"),
        vertical_spacing=0.12, row_heights=[0.55, 0.45])

    for row_idx in [1, 2]:
        for start_dt, end_dt, st in stage_ranges:
            fig1.add_vrect(x0=start_dt, x1=end_dt, fillcolor=st["color"],
                           layer="below", line_width=0, row=row_idx, col=1)

    fig1.add_trace(go.Scatter(
        x=mdates, y=monthly["close"].values, mode="lines",
        name="月度收盘价（不复权）",
        line=dict(color=C["orange"], width=2.2)), row=1, col=1)

    events = [("2018-08-15", "非瘟爆发", C["red"]),
              ("2021-03-15", "猪价见顶", C["darkgreen"]),
              ("2023-12-15", "全年亏损", C["gray"]),
              ("2025-06-15", "H股递表", C["midblue"])]
    for evt_date, evt_label, evt_color in events:
        evt_dt = pd.Timestamp(evt_date)
        if evt_dt >= mdates[0] and evt_dt <= mdates[-1]:
            idx = min(range(n_m), key=lambda i: abs((mdates[i] - evt_dt).days))
            fig1.add_annotation(x=evt_dt, y=monthly["close"].values[idx],
                                text=evt_label, showarrow=True, arrowhead=2,
                                ax=0, ay=-35, font=dict(size=9, color=evt_color),
                                row=1, col=1)

    fig1.add_trace(go.Scatter(
        x=mdates, y=monthly["pb"].values, mode="lines",
        name="PB = 股价/BPS",
        line=dict(color=C["midblue"], width=2)), row=2, col=1)
    fig1.add_hline(y=1.0, line_dash="dot", line_color="#999", line_width=1, row=2, col=1)
    fig1.add_hline(y=3.0, line_dash="dot", line_color=C["orange"], line_width=0.8,
                   opacity=0.5, row=2, col=1)

    for row_idx in [1, 2]:
        fig1.update_xaxes(title_text="", tickangle=30, tickfont=dict(size=8), row=row_idx, col=1)
    fig1.update_yaxes(title_text="<b>股价（元）</b>", gridcolor="#f0f0f0", row=1, col=1)
    fig1.update_yaxes(title_text="<b>PB（x）</b>", gridcolor="#f0f0f0", row=2, col=1)
    fig1.update_layout(
        title=dict(text="<b>牧原股份月度股价与PB — 三个成长阶段</b>",
                   x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
        template="plotly_white", height=580,
        legend=dict(orientation="h", yanchor="bottom", y=1.05, font=dict(size=10)),
        margin=dict(l=60, r=40, t=50, b=50), hovermode="x unified")

    # ═══ 图2: PE + PS + 总市值 三面板 ═══
    fig2 = make_subplots(
        rows=3, cols=1,
        subplot_titles=("<b>PE(TTM) — EPS亏损期无定义（截断±100x）</b>",
                         "<b>PS(TTM) — 市销率 = 总市值/TTM营收</b>",
                         "<b>总市值（亿元）— 规模决定定价逻辑</b>"),
        vertical_spacing=0.10, row_heights=[0.33, 0.33, 0.34])

    pe_display = monthly["pe"].clip(-100, 100).values
    for row_idx in range(1, 4):
        for start_dt, end_dt, st in stage_ranges:
            fig2.add_vrect(x0=start_dt, x1=end_dt, fillcolor=st["color"],
                           layer="below", line_width=0, row=row_idx, col=1)

    fig2.add_trace(go.Scatter(
        x=mdates, y=pe_display, mode="lines", name="PE(TTM)",
        line=dict(color=C["green"], width=1.5)), row=1, col=1)
    fig2.add_hline(y=0, line_dash="solid", line_color="#999", line_width=1, row=1, col=1)

    fig2.add_trace(go.Scatter(
        x=mdates, y=monthly["ps"].values, mode="lines", name="PS(TTM)",
        line=dict(color=C["purple"], width=1.5)), row=2, col=1)

    fig2.add_trace(go.Scatter(
        x=mdates, y=monthly["mkt_cap"].values, mode="lines", name="总市值（亿元）",
        line=dict(color=C["teal"], width=2)), row=3, col=1)
    for level in [200, 500, 2000]:
        fig2.add_hline(y=level, line_dash="dot", line_color="#999",
                       line_width=0.8, row=3, col=1)

    for row_idx in range(1, 4):
        fig2.update_xaxes(title_text="", tickangle=30, tickfont=dict(size=8), row=row_idx, col=1)
    fig2.update_yaxes(title_text="<b>PE（x）</b>", gridcolor="#f0f0f0", row=1, col=1)
    fig2.update_yaxes(title_text="<b>PS（x）</b>", gridcolor="#f0f0f0", row=2, col=1)
    fig2.update_yaxes(title_text="<b>市值（亿）</b>", gridcolor="#f0f0f0", row=3, col=1)
    fig2.update_layout(
        title=dict(text="<b>估值指标全景：PE · PS · 总市值（月度，2014-2026）</b>",
                   x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
        template="plotly_white", height=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, font=dict(size=9)),
        margin=dict(l=60, r=40, t=50, b=50), hovermode="x unified")

    # ═══ 图3: 成长阶段划分示意图（总市值 + 阶段标注） ═══
    fig3 = go.Figure()

    for start_dt, end_dt, st in stage_ranges:
        fig3.add_vrect(x0=start_dt, x1=end_dt, fillcolor=st["color"],
                       layer="below", line_width=0)

    fig3.add_trace(go.Scatter(
        x=mdates, y=monthly["mkt_cap"].values, mode="lines",
        name="总市值（亿元）",
        line=dict(color=C["teal"], width=2.5)))

    # 阶段分界线
    for boundary in [pd.Timestamp("2019-01-01"), pd.Timestamp("2022-01-01")]:
        fig3.add_vline(x=boundary, line_dash="dash", line_color="#888",
                       line_width=1.2, opacity=0.8)

    # 阶段标注（顶部）
    for start_dt, end_dt, st in stage_ranges:
        mid = start_dt + (end_dt - start_dt) / 2
        fig3.add_annotation(x=mid, y=1.02, xref="x", yref="paper",
                            text=f"<b>{st['label']}</b>",
                            showarrow=False,
                            font=dict(size=12, color="#2c3e50"),
                            xanchor="center")

    # 市值坎参考线
    for level in [200, 500, 2000]:
        fig3.add_hline(y=level, line_dash="dot", line_color="#999",
                       line_width=0.8, opacity=0.6)
    fig3.add_annotation(x=mdates[0], y=220, text="200亿",
                        showarrow=False, font=dict(size=8, color="#999"), xanchor="left")
    fig3.add_annotation(x=mdates[0], y=520, text="500亿",
                        showarrow=False, font=dict(size=8, color="#999"), xanchor="left")
    fig3.add_annotation(x=mdates[0], y=2020, text="2000亿",
                        showarrow=False, font=dict(size=8, color="#999"), xanchor="left")

    # 关键事件
    events = [("2018-08-15", "非瘟爆发", C["red"]),
              ("2021-03-15", "猪价见顶", C["darkgreen"]),
              ("2023-12-15", "全年亏损", C["gray"]),
              ("2025-06-15", "H股递表", C["midblue"])]
    for evt_date, evt_label, evt_color in events:
        evt_dt = pd.Timestamp(evt_date)
        if evt_dt >= mdates[0] and evt_dt <= mdates[-1]:
            idx = min(range(n_m), key=lambda i: abs((mdates[i] - evt_dt).days))
            fig3.add_annotation(x=evt_dt, y=monthly["mkt_cap"].values[idx],
                                text=evt_label, showarrow=True, arrowhead=2,
                                ax=0, ay=-35, font=dict(size=9, color=evt_color))

    fig3.update_layout(
        title=dict(text="<b>成长阶段划分 — 基于总市值</b>",
                   x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
        template="plotly_white", height=380,
        yaxis_title="<b>总市值（亿元）</b>",
        margin=dict(l=60, r=40, t=60, b=50),
        hovermode="x unified")
    fig3.update_xaxes(title_text="", tickangle=30, tickfont=dict(size=8))
    fig3.update_yaxes(gridcolor="#f0f0f0")

    note3 = (
        "<b>三阶段划分逻辑：</b><br>"
        + "· <b>小盘期（2014-2018）：</b>市值≈200-800亿，出栏扩张期，散户主导定价，PE极端不稳定<br>"
        + "· <b>扩张期（2019-2021）：</b>市值从800→4000亿，非瘟超级周期，盈利爆发式增长，PB从5×重估至15×<br>"
        + "· <b>成熟大盘期（2022-至今）：</b>市值≈2000-3500亿，周期回归，机构投资者主导，PE区间收窄<br>"
        + "· <b>市值坎 200/500/2000亿</b>（虚线）：每突破一道坎，定价逻辑发生质变——规模越大，机构覆盖越密，"
        + "流动性越好，极端估值出现的频率和幅度越低。"
    )

    # ── 阶段统计 ──
    stage_stats = []
    for start_dt, end_dt, st in stage_ranges:
        mask = (monthly["month_dt"] >= start_dt) & (monthly["month_dt"] <= end_dt)
        seg = monthly[mask]
        if len(seg) > 0:
            mc_avg = seg["mkt_cap"].mean()
            pb_vals = seg["pb"]
            pe_vals = seg["pe"].dropna()
            pe_pos = pe_vals[(pe_vals > 0) & (pe_vals < 200)]
            ps_vals = seg["ps"].dropna()

            def pct(vals, q):
                return float(vals.quantile(q / 100.0)) if len(vals) > 0 else float("nan")

            pb_stats = {"med": float(pb_vals.median()), "p25": pct(pb_vals, 25),
                        "p75": pct(pb_vals, 75), "min": float(pb_vals.min()),
                        "max": float(pb_vals.max()), "n": len(pb_vals)}
            pe_stats = {"med": float(pe_pos.median()) if len(pe_pos) else float("nan"),
                        "p25": pct(pe_pos, 25), "p75": pct(pe_pos, 75),
                        "min": float(pe_pos.min()) if len(pe_pos) else float("nan"),
                        "max": float(pe_pos.max()) if len(pe_pos) else float("nan"),
                        "n_valid": len(pe_pos), "n_total": len(pe_vals)}
            ps_stats = {"med": float(ps_vals.median()), "p25": pct(ps_vals, 25),
                        "p75": pct(ps_vals, 75), "min": float(ps_vals.min()),
                        "max": float(ps_vals.max()), "n": len(ps_vals)}

            amps = []
            for q in seg["quarter"].unique():
                q_data = seg[seg["quarter"] == q]
                if len(q_data) >= 2:
                    qh, ql = q_data["close"].max(), q_data["close"].min()
                    if ql > 0: amps.append((qh - ql) / ql * 100)
            med_amp = float(np.median(amps)) if amps else 0

            stage_stats.append({
                "label": st["label"], "mc_avg": mc_avg,
                "pb": pb_stats, "pe": pe_stats, "ps": ps_stats,
                "q_amp": med_amp, "desc": st["desc"]})

    methods = ["PB法为主（小盘+EPS不稳定）",
               "PB+PE结合（盈利爆发，成长重估）",
               "周期均值PE法（机构定价+周期框架）"]
    stage_rows = ""
    for i, st in enumerate(stage_stats):
        pb = st["pb"]; pe = st["pe"]; ps = st["ps"]
        pe_info = f"PE={pe['med']:.0f}x" if not np.isnan(pe["med"]) else "PE=N/A"
        stage_rows += (
            f"<tr><td><b>阶段{i+1}</b></td><td>{st['label']}</td>"
            f"<td>市值≈{st['mc_avg']:.0f}亿</td>"
            f"<td>PB={pb['med']:.1f}x {pe_info} PS={ps['med']:.1f}x</td>"
            f"<td>季振幅≈{st['q_amp']:.0f}%</td><td>{st['desc']}</td>"
            f"<td>{methods[i]}</td></tr>")

    latest = monthly.iloc[-1]
    note1 = (
        f"<b>成长阶段划分（基于总市值）：</b><br><br>"
        + "<table><thead><tr><th>阶段</th><th>名称</th><th>市值</th>"
        + "<th>估值指标(中位)</th><th>波动率</th><th>定价特征</th>"
        + "<th>适用估值方法</th></tr></thead>"
        + f"<tbody>{stage_rows}</tbody></table><br>"
        + "<b>核心规律——三个阶段，三种定价逻辑：</b><br>"
        + "① 小盘期（2014-2018）：市值200-800亿，季振幅50%+，PE极端不稳定（微利时100x+），"
        + "PB是唯一可靠的估值锚<br>"
        + "② 扩张期（2019-2021）：非瘟超级周期，盈利爆发+市值从800→4000亿，"
        + "市场从怀疑→信任牧原的龙头地位，PB从5x重估至15x<br>"
        + "③ 成熟大盘期（2022-至今）：市值2000-3500亿，季振幅降至~20%，PE区间收窄，"
        + "机构投资者主导——极端估值频率和幅度大幅降低<br><br>"
        + "<b>为什么大市值定价更有效？</b>三个机制："
        + "机构覆盖增加→信息效率提高 → "
        + "流动性扩容→游资难以操控 → "
        + "融券+期货→高估会被套利纠正<br><br>"
        + f"<b>当前快照（{latest['month_dt'].strftime('%Y-%m')}）：</b> "
        + f"市值={latest['mkt_cap']:.0f}亿 | PB={latest['pb']:.1f}x | "
        + (f"PE={latest['pe']:.0f}x | " if pd.notna(latest['pe']) else "PE=N/A | ")
        + f"PS={latest['ps']:.1f}x"
    )

    note2 = (
        "<b>估值指标全景解读：</b><br>"
        + "· <b>PE(TTM)：</b>因TTM EPS可负可趋零，PE在亏损期无定义（截断±100x）。"
        + "说明为何当期PE不能做估值分母——需用周期均值EPS替代（如8年均值2.04元）。<br>"
        + "· <b>PS(TTM)：</b>市销率是盈利波动时的替代指标。"
        + "牧原PS从早期1-2x→非瘟期0.5-1x→当前~1.5x。<br>"
        + "· <b>总市值：</b>200亿→500亿→2000亿三道坎对应三个截然不同的定价世界。"
        + "当前~2500亿=蓝筹周期股，适用周期均值PE 15-25x框架。"
    )

    # 存入缓存供 ch13 使用
    _CH12_CACHE["monthly"] = monthly
    _CH12_CACHE["stage_ranges"] = stage_ranges
    _CH12_CACHE["stage_stats"] = stage_stats

    return [(fig1, note1), (fig2, note2), (fig3, note3)]


def ch13_stage_distribution():
    """各阶段估值分布示意图 + 当前成熟大盘阶段分位数"""
    monthly = _CH12_CACHE["monthly"]
    stage_ranges = _CH12_CACHE["stage_ranges"]
    stage_stats = _CH12_CACHE["stage_stats"]

    if monthly is None or stage_stats is None:
        return "<p style='color:#c0392b'>错误：需先运行第1节以计算月度估值数据。</p>"

    latest = monthly.iloc[-1]
    cur_pb = float(latest["pb"])
    cur_pe = float(latest["pe"]) if pd.notna(latest["pe"]) else None
    cur_ps = float(latest["ps"])

    # ── 构建各阶段的估值序列 ──
    stage_labels = [st["label"] for st in stage_stats]
    stage_pb_data = []
    stage_pe_data = []
    stage_ps_data = []
    for start_dt, end_dt, st in stage_ranges:
        mask = (monthly["month_dt"] >= start_dt) & (monthly["month_dt"] <= end_dt)
        seg = monthly[mask]
        stage_pb_data.append(seg["pb"].dropna().values)
        pe_vals = seg["pe"].dropna()
        pe_pos = pe_vals[(pe_vals > 0) & (pe_vals < 200)]
        stage_pe_data.append(pe_pos.values)
        stage_ps_data.append(seg["ps"].dropna().values)

    stage_short = ["小盘期\n2014-2018", "扩张期\n2019-2021", "成熟大盘期\n2022-至今"]
    colors_bg = ["rgba(243,156,18,0.08)", "rgba(52,152,219,0.08)", "rgba(46,204,113,0.08)"]

    # ═══ 图: 三面板箱线图（PB / PE / PS） ═══
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("<b>PB 分布（各阶段）</b>",
                         "<b>PE(TTM) 分布（各阶段）</b>",
                         "<b>PS 分布（各阶段）</b>"),
        horizontal_spacing=0.09)

    metric_configs = [
        ("pb", stage_pb_data, cur_pb, "PB (x)", 0),
        ("pe", stage_pe_data, cur_pe, "PE(TTM) (x)", 1),
        ("ps", stage_ps_data, cur_ps, "PS (x)", 2),
    ]

    for metric, data_list, cur_val, ytitle, col_idx in metric_configs:
        for i, data in enumerate(data_list):
            # 显式设 x 位置，避免因 skip 空数据导致盒子错位
            x_pos = np.full(len(data), i) if len(data) > 0 else np.array([])
            if len(data) == 0:
                continue
            # Box trace
            fig.add_trace(go.Box(
                y=data, x=x_pos,
                name=stage_short[i].replace("\n", " "),
                marker=dict(color=list(C.values())[[0, 4, 6][i]]),
                fillcolor=colors_bg[i],
                line=dict(width=1.5),
                boxpoints="outliers", jitter=0.3,
                showlegend=(col_idx == 0),
                legendgroup=stage_short[i],
            ), row=1, col=col_idx + 1)

        # 当前值标记线（仅在成熟大盘阶段 = index 2）
        last_data = data_list[-1] if len(data_list) > 0 else np.array([])
        if cur_val is not None and len(last_data) > 0:
            fig.add_hline(
                y=cur_val, line_dash="dash", line_color=C["red"],
                line_width=2, row=1, col=col_idx + 1,
                annotation=dict(
                    text=f"当前 {cur_val:.1f}",
                    x=0.98, xanchor="right",
                    font=dict(size=9, color=C["red"])))

    for col_idx in range(1, 4):
        fig.update_xaxes(tickfont=dict(size=9), row=1, col=col_idx)
        fig.update_yaxes(title_text="", gridcolor="#f0f0f0", row=1, col=col_idx)
    fig.update_xaxes(tickvals=[0, 1, 2], ticktext=stage_short, row=1, col=1)
    fig.update_xaxes(tickvals=[0, 1, 2], ticktext=stage_short, row=1, col=2)
    fig.update_xaxes(tickvals=[0, 1, 2], ticktext=stage_short, row=1, col=3)
    fig.update_layout(
        title=dict(text="<b>各阶段估值分布示意图 — 箱线图（含当前值标记）</b>",
                   x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
        template="plotly_white", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.06, font=dict(size=9)),
        margin=dict(l=40, r=20, t=50, b=60),
    )

    # ── 分位数分析 ──
    last_st = stage_stats[-1]
    mask_last = ((monthly["month_dt"] >= stage_ranges[-1][0]) &
                 (monthly["month_dt"] <= stage_ranges[-1][1]))
    pb_last = monthly.loc[mask_last, "pb"]
    pe_last = monthly.loc[mask_last, "pe"].dropna()
    pe_last_pos = pe_last[(pe_last > 0) & (pe_last < 200)]
    ps_last = monthly.loc[mask_last, "ps"].dropna()

    def percentile_of(val, vals):
        if val is None or len(vals) == 0: return None
        return float((vals < val).sum() / len(vals) * 100)

    pb_pct = percentile_of(cur_pb, pb_last)
    pe_pct = percentile_of(cur_pe, pe_last_pos) if cur_pe is not None else None
    ps_pct = percentile_of(cur_ps, ps_last)

    def pct_label(pct_val):
        if pct_val is None: return ("N/A", "#999")
        if pct_val < 10: return ("极低 <P10", C["red"])
        if pct_val < 25: return ("偏低 P10-P25", C["orange"])
        if pct_val < 40: return ("中偏低 P25-P40", C["gold"])
        if pct_val <= 60: return ("中枢 P40-P60", C["green"])
        if pct_val <= 75: return ("中偏高 P60-P75", C["midblue"])
        if pct_val <= 90: return ("偏高 P75-P90", C["purple"])
        return ("极高 >P90", C["red"])

    pb_lbl, pb_clr = pct_label(pb_pct)
    pe_lbl, pe_clr = pct_label(pe_pct)
    ps_lbl, ps_clr = pct_label(ps_pct)

    pb_range_lo = float(pb_last.quantile(0.25)) * float(latest["bps"])
    pb_range_hi = float(pb_last.quantile(0.75)) * float(latest["bps"])

    note = (
        "<b>示意图解读：</b><br>"
        + "· 箱体 = P25-P75（中间50%观测的区间），线 = 中位数，须 = 1.5×IQR范围<br>"
        + "· <b>红色虚线</b> = 当前值在成熟大盘阶段分布中的位置<br><br>"
        + "<b>当前估值在成熟大盘阶段的分位数：</b><br><br>"
        + "<table>"
        + "<tr><th>指标</th><th>当前值</th><th>阶段中位数</th>"
        + "<th>当前分位数</th><th>位置判断</th></tr>"
        + f"<tr><td><b>PB</b></td><td>{cur_pb:.2f}x</td><td>{last_st['pb']['med']:.2f}x</td>"
        + f"<td style='color:{pb_clr}'><b>{pb_pct:.0f}%</b></td>"
        + f"<td style='color:{pb_clr}'><b>{pb_lbl}</b></td></tr>"
    )
    if cur_pe is not None:
        note += (
            f"<tr><td><b>PE(TTM)</b></td><td>{cur_pe:.0f}x</td>"
            f"<td>{last_st['pe']['med']:.1f}x</td>"
            f"<td style='color:{pe_clr}'><b>{pe_pct:.0f}%</b></td>"
            f"<td style='color:{pe_clr}'><b>{pe_lbl}</b></td></tr>"
        )
    else:
        note += ("<tr><td><b>PE(TTM)</b></td><td colspan='4' style='color:#999'>"
                 "当前EPS亏损或微利，PE无意义</td></tr>")
    note += (
        f"<tr><td><b>PS</b></td><td>{cur_ps:.2f}x</td><td>{last_st['ps']['med']:.2f}x</td>"
        + f"<td style='color:{ps_clr}'><b>{ps_pct:.0f}%</b></td>"
        + f"<td style='color:{ps_clr}'><b>{ps_lbl}</b></td></tr>"
        + "</table><br>"
        + "<b>投资含义：</b><br>"
        + "· PB历史中枢区间（P25-P75）= 隐含股价 <b>"
        + f"{pb_range_lo:.1f}-{pb_range_hi:.1f}元</b>"
    )
    if cur_pb < float(last_st["pb"]["p25"]):
        note += "——当前PB <b>低于</b>P25，处于历史偏低区域"
    elif cur_pb > float(last_st["pb"]["p75"]):
        note += "——当前PB <b>高于</b>P75，处于历史偏高区域"
    else:
        note += "——处于中枢区间"
    note += (
        "<br>· PE偏高而PB/PS偏低 → 周期底部盈利压缩导致PE失真，PB+PS更具参考价值<br>"
        + "· <b>局限：</b>历史分布忽略结构性变化（出栏规模、成本结构），分位数只是参照，不是结论。"
    )

    return [(fig, note)]


def ch14_stage_model_validation():
    """成熟大盘期估值模型验证 — 用市场实际定价决定哪个模型最合适

    候选模型：PB / 周期均值PE / PS / TTM PE
    判定标准：① 倍数稳定性（IQR/中位数） ② 拟合误差（中位倍数隐含价 vs 实际价 MAD）
              ③ 全程可定义性（亏损期是否有意义）
    """
    # ── 月度数据（与 ch12 同口径） ──
    daily_csv = ROOT / "data" / "牧原_日线股价.csv"
    df_daily = pd.read_csv(daily_csv)
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    df_daily["month"] = df_daily["date"].dt.to_period("M")
    monthly = df_daily.groupby("month")["close"].last().reset_index()
    monthly["month_dt"] = monthly["month"].dt.to_timestamp()
    monthly["yr"] = monthly["month_dt"].dt.year

    df_qf = pd.read_csv(ROOT / "data" / "主要财务指标_按单季度.csv", dtype=str)
    df_qf["REPORT_DATE"] = pd.to_datetime(df_qf["REPORT_DATE"])
    df_qf["EPSJB"] = pd.to_numeric(df_qf["EPSJB"], errors="coerce")
    df_qf["BPS"] = pd.to_numeric(df_qf["BPS"], errors="coerce")
    df_qf["TOTALOPERATEREVE"] = pd.to_numeric(df_qf["TOTALOPERATEREVE"], errors="coerce")
    df_qf = df_qf.sort_values("REPORT_DATE").reset_index(drop=True)
    df_qf["ttm_eps"] = df_qf["EPSJB"].rolling(4, min_periods=4).sum()
    df_qf["ttm_rev"] = df_qf["TOTALOPERATEREVE"].rolling(4, min_periods=4).sum()
    df_qf["quarter"] = df_qf["REPORT_DATE"].dt.to_period("Q")

    bs = pd.read_csv(ROOT / "data" / "资产负债表_按报告期.csv", dtype=str)
    bs["REPORT_DATE"] = pd.to_datetime(bs["REPORT_DATE"])
    bs["TOTAL_PARENT_EQUITY"] = pd.to_numeric(bs["TOTAL_PARENT_EQUITY"], errors="coerce")
    bs_q4 = bs[bs["REPORT_DATE"].dt.month == 12][["REPORT_DATE", "TOTAL_PARENT_EQUITY"]].copy()
    bs_q4["year"] = bs_q4["REPORT_DATE"].dt.year
    qf_q4 = df_qf[df_qf["REPORT_DATE"].dt.month == 12][["REPORT_DATE", "BPS"]].copy()
    qf_q4["year"] = qf_q4["REPORT_DATE"].dt.year
    shares_yr = bs_q4.merge(qf_q4, on="year")
    shares_yr["shares"] = shares_yr["TOTAL_PARENT_EQUITY"] / shares_yr["BPS"] / 1e8
    shares_map = {int(r["year"]): r["shares"] for _, r in shares_yr.iterrows()}
    monthly["shares"] = monthly["yr"].map(shares_map).ffill()

    # 滚动8年周期均值EPS（与 Step 4/6 口径一致）
    cyc_eps = {}
    for y in sorted(FIN.keys()):
        win = [yy for yy in range(y - 7, y + 1) if yy in FIN]
        if len(win) >= 5:
            cyc_eps[y] = sum(FIN[yy]["eps"] for yy in win) / len(win)

    qtr_bps = dict(zip(df_qf["quarter"], df_qf["BPS"]))
    qtr_ttm = dict(zip(df_qf["quarter"], df_qf["ttm_eps"]))
    qtr_rev = dict(zip(df_qf["quarter"], df_qf["ttm_rev"]))
    monthly["quarter"] = monthly["month_dt"].dt.to_period("Q")
    monthly["bps"] = monthly["quarter"].map(qtr_bps).ffill()
    monthly["ttm_eps"] = monthly["quarter"].map(qtr_ttm).ffill()
    monthly["ttm_rev"] = monthly["quarter"].map(qtr_rev).ffill()
    monthly["cycle_eps"] = monthly["yr"].map(cyc_eps).ffill()
    monthly = monthly[(monthly["month_dt"] >= pd.Timestamp("2014-01-01")) &
                      monthly["bps"].notna()].reset_index(drop=True)
    monthly["mkt_cap"] = monthly["close"] * monthly["shares"]
    monthly["pb"] = monthly["close"] / monthly["bps"]
    monthly["pe_cyc"] = np.where(monthly["cycle_eps"] > 0.05,
                                 monthly["close"] / monthly["cycle_eps"], np.nan)
    monthly["pe_ttm"] = np.where(monthly["ttm_eps"].abs() > 0.05,
                                 monthly["close"] / monthly["ttm_eps"], np.nan)
    monthly["ps"] = np.where(monthly["ttm_rev"] > 1000,
                             monthly["mkt_cap"] / (monthly["ttm_rev"] / 1e8), np.nan)

    s3 = monthly[monthly["month_dt"] >= pd.Timestamp("2022-01-01")].reset_index(drop=True)
    s3s = monthly[monthly["month_dt"] >= pd.Timestamp("2022-07-01")].reset_index(drop=True)

    def dist_stats(vals):
        q = np.percentile(vals, [10, 25, 50, 75, 90])
        return {"p10": float(q[0]), "p25": float(q[1]), "p50": float(q[2]),
                "p75": float(q[3]), "p90": float(q[4]),
                "iqr_med": float((q[3] - q[1]) / q[2]) if q[2] else float("nan")}

    pb_st = dist_stats(s3["pb"].dropna().values)
    pecyc_st = dist_stats(s3["pe_cyc"].dropna().values)
    ps_st = dist_stats(s3["ps"].dropna().values)
    pe_pos = s3["pe_ttm"].dropna()
    pe_pos = pe_pos[(pe_pos > 0) & (pe_pos < 200)]
    pet_st = dist_stats(pe_pos.values) if len(pe_pos) >= 8 else None

    pb_s = dist_stats(s3s["pb"].dropna().values)
    pecyc_s = dist_stats(s3s["pe_cyc"].dropna().values)

    def mad_of(col, mult, frame=None):
        f = s3 if frame is None else frame
        dev = ((f[col] * mult - f["close"]) / f["close"] * 100).dropna()
        return float(dev.abs().median())

    mad_pb = mad_of("bps", pb_st["p50"])
    mad_cyc = mad_of("cycle_eps", pecyc_st["p50"])
    mad_pb_s = mad_of("bps", pb_s["p50"], s3s)
    mad_cyc_s = mad_of("cycle_eps", pecyc_s["p50"], s3s)
    dev_ps = ((s3["ps"].median() * (s3["ttm_rev"] / 1e8) / s3["shares"] - s3["close"]) /
              s3["close"] * 100).dropna()
    mad_ps = float(dev_ps.abs().median())

    # 动态计算当前定价位置与公平价值带（避免硬编码口径不一致）
    cur_bps = float(s3.iloc[-1]["bps"])
    cur_pb = CURRENT_PRICE / cur_bps
    cur_cycpe = CURRENT_PRICE / float(cyc_eps[max(cyc_eps.keys())])
    fv_lo = AVG8_EPS * pecyc_st["p25"]
    fv_hi = AVG8_EPS * pecyc_st["p75"]
    _CH14_CACHE["pecyc_st"] = pecyc_st

    # ── 图：PB 与 周期均值PE 的成熟期分布带 ──
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("<b>PB = 股价/BPS — 成熟期分布带</b>",
                                        "<b>周期均值PE = 股价/滚动8Y均值EPS — 成熟期分布带</b>"),
                        vertical_spacing=0.10, row_heights=[0.5, 0.5])
    x = s3["month_dt"].tolist()
    for row_i, (key, st, color) in enumerate([
            ("pb", pb_st, C["midblue"]), ("pe_cyc", pecyc_st, C["orange"])], start=1):
        vals = s3[key].clip(0, 100) if key == "pe_cyc" else s3[key]
        fig.add_trace(go.Scatter(x=x, y=[st["p25"]] * len(x), mode="lines",
                                 line=dict(width=0), showlegend=False, hoverinfo="skip"),
                      row=row_i, col=1)
        fig.add_trace(go.Scatter(x=x, y=[st["p75"]] * len(x), mode="lines",
                                 line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(52,152,219,0.10)" if row_i == 1 else "rgba(230,126,34,0.10)",
                                 name="P25-P75 中枢带", hoverinfo="skip"), row=row_i, col=1)
        fig.add_trace(go.Scatter(x=x, y=vals, mode="lines", name="月度倍数",
                                 line=dict(color=color, width=1.8)), row=row_i, col=1)
        fig.add_hline(y=st["p50"], line_dash="solid", line_color="#2c3e50", line_width=1,
                      annotation_text=f"P50={st['p50']:.1f}x", annotation_position="left",
                      row=row_i, col=1)
        fig.add_hline(y=st["p10"], line_dash="dot", line_color="#999", line_width=1,
                      annotation_text=f"P10={st['p10']:.1f}", annotation_position="left",
                      row=row_i, col=1)
        fig.add_hline(y=st["p90"], line_dash="dot", line_color="#c0392b", line_width=1,
                      annotation_text=f"P90={st['p90']:.1f}", annotation_position="right",
                      row=row_i, col=1)
    # 2025年8月成熟期峰值标注
    peak_idx = s3["close"].idxmax()
    peak_dt = s3.loc[peak_idx, "month_dt"]
    fig.add_vline(x=peak_dt, line_dash="dash", line_color="#1e8449", line_width=1,
                  row=1, col=1)
    fig.add_vline(x=peak_dt, line_dash="dash", line_color="#1e8449", line_width=1,
                  row=2, col=1)
    fig.add_annotation(x=peak_dt, y=s3.loc[peak_idx, "pb"], text="2025峰值 PB≈3.96",
                       showarrow=True, arrowhead=2, ax=40, ay=-30,
                       font=dict(size=9, color="#1e8449"), row=1, col=1)
    fig.add_annotation(x=peak_dt, y=s3.loc[peak_idx, "pe_cyc"], text="2025峰值 周期PE≈23.8",
                       showarrow=True, arrowhead=2, ax=40, ay=-30,
                       font=dict(size=9, color="#1e8449"), row=2, col=1)
    fig.update_layout(title=dict(text="<b>成熟大盘期（2022-至今）市场实际支付的估值倍数分布</b>",
                                 x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
                      template="plotly_white", height=520,
                      legend=dict(orientation="h", yanchor="bottom", y=1.04, font=dict(size=10)),
                      margin=dict(l=60, r=40, t=50, b=50), hovermode="x unified")
    fig.update_xaxes(title_text="", tickangle=30, tickfont=dict(size=8), row=2, col=1)
    fig.update_yaxes(title_text="<b>PB（x）</b>", gridcolor="#f0f0f0", row=1, col=1)
    fig.update_yaxes(title_text="<b>周期PE（x）</b>", gridcolor="#f0f0f0", row=2, col=1)

    # ═══════ 前瞻拟合分析：下一期基本面（前瞻 PB/PE/PS） vs 股价 ═══════
    # 前瞻倍数 = 当月股价 ÷ 下一季度基本面（BPS / TTM EPS / TTM 营收）
    qs_sorted = sorted(df_qf["quarter"].unique())

    def fwd_map(key):
        vals = {}
        for i, q in enumerate(qs_sorted):
            if i + 1 >= len(qs_sorted):
                continue
            r = df_qf[df_qf["quarter"] == qs_sorted[i + 1]]
            if not r.empty and pd.notna(r.iloc[0][key]):
                vals[str(q)] = float(r.iloc[0][key])
        return vals

    fwd_bps_map = fwd_map("BPS")
    fwd_eps_map = fwd_map("ttm_eps")
    fwd_rev_map = fwd_map("ttm_rev")
    s3["fwd_bps"] = s3["quarter"].astype(str).map(fwd_bps_map)
    s3["fwd_eps"] = s3["quarter"].astype(str).map(fwd_eps_map)
    s3["fwd_rev"] = s3["quarter"].astype(str).map(fwd_rev_map)
    s3["pb_fwd"] = s3["close"] / s3["fwd_bps"]
    s3["pe_fwd"] = np.where(s3["fwd_eps"].abs() > 0.05, s3["close"] / s3["fwd_eps"], np.nan)
    s3["ps_fwd"] = np.where(s3["fwd_rev"] > 1000, s3["mkt_cap"] / (s3["fwd_rev"] / 1e8), np.nan)

    def fit_metrics(mult_col, fund_col, label, is_ps=False):
        """单一模型×口径的拟合指标（成熟期 2022+）"""
        d = s3[["close", mult_col, fund_col, "shares"]].dropna().copy()
        if is_ps:
            d = d[d[fund_col] > 1000]
        elif "eps" in fund_col:
            d = d[d[fund_col].abs() > 0.05]
        else:
            d = d[d[fund_col] > 0]
        if len(d) < 8:
            return None
        vals = d[mult_col]
        if "pe" in mult_col:
            vals = vals[(vals > 0) & (vals < 200)]
        elif is_ps:
            vals = vals[(vals > 0.3) & (vals < 10)]
        else:
            vals = vals[vals > 0]
        d = d.loc[vals.index]
        if len(d) < 8:
            return None
        q = np.percentile(vals, [10, 25, 50, 75, 90])
        med = float(q[2])
        implied = med * (d[fund_col] / 1e8) / d["shares"] if is_ps else med * d[fund_col]
        dev = ((implied - d["close"]) / d["close"] * 100)
        mad = float(dev.abs().median())
        lp, lf = np.log(d["close"]), np.log(d[fund_col].abs())
        r = float(np.corrcoef(lp, lf)[0, 1])
        rho = float(pd.Series(lp).corr(pd.Series(lf), method="spearman"))
        return {"label": label, "n": len(d), "p50": med, "iqr": float((q[3] - q[1]) / med),
                "mad": mad, "r": r, "r2": r ** 2, "rho": rho}

    metrics = []
    for label, mc, fc, ps_flag in [
            ("PB 当期", "pb", "bps", False),
            ("PB 前瞻", "pb_fwd", "fwd_bps", False),
            ("PE(TTM) 当期", "pe_ttm", "ttm_eps", False),
            ("PE(TTM) 前瞻", "pe_fwd", "fwd_eps", False),
            ("PS 当期", "ps", "ttm_rev", True),
            ("PS 前瞻", "ps_fwd", "fwd_rev", True),
            ("周期均值PE 当期", "pe_cyc", "cycle_eps", False)]:
        m = fit_metrics(mc, fc, label, ps_flag)
        if m:
            metrics.append(m)

    # ── 图2：前瞻/当期基本面 vs 股价（对数散点 + 回归线） ──
    fig2 = make_subplots(rows=3, cols=1,
                         subplot_titles=("<b>PB — 股价 vs BPS（对数）</b>",
                                         "<b>PE(TTM) — 股价 vs TTM EPS（对数，仅盈利期）</b>",
                                         "<b>PS — 市值 vs TTM 营收（对数）</b>"),
                         vertical_spacing=0.10, row_heights=[1/3, 1/3, 1/3])
    series_cfg = [
        ("pb", "bps", "PB 当期", "fwd_bps", "pb_fwd", "PB 前瞻"),
        ("pe_ttm", "ttm_eps", "PE 当期", "fwd_eps", "pe_fwd", "PE 前瞻"),
        ("ps", "ttm_rev", "PS 当期", "fwd_rev", "ps_fwd", "PS 前瞻"),
    ]
    for row_i, (mc_t, fc_t, lb_t, fc_f, mc_f, lb_f) in enumerate(series_cfg, start=1):
        for mc, fc, lb, color, marker in [
                (mc_t, fc_t, lb_t, C["midblue"], "circle"),
                (mc_f, fc_f, lb_f, C["orange"], "diamond")]:
            d = s3[["close", mc, fc]].replace([np.inf, -np.inf], np.nan).dropna()
            if "pe" in mc:
                d = d[(d[mc] > 0) & (d[mc] < 200)]
            elif "ps" in mc:
                d = d[(d[mc] > 0.3) & (d[mc] < 10)]
            else:
                d = d[d[mc] > 0]
            if len(d) < 8:
                continue
            lx, ly = np.log(d[fc].abs()), np.log(d["close"])
            fig2.add_trace(go.Scatter(x=lx, y=ly, mode="markers", name=lb,
                                      marker=dict(color=color, size=6, symbol=marker, opacity=0.75),
                                      text=d.index, hoverinfo="x+y"),
                           row=row_i, col=1)
            b, a = np.polyfit(lx, ly, 1)
            xs = np.linspace(lx.min(), lx.max(), 30)
            r2v = np.corrcoef(lx, ly)[0, 1] ** 2
            fig2.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines",
                                      line=dict(color=color, width=1.5, dash="dot"),
                                      showlegend=False, hoverinfo="skip"), row=row_i, col=1)
            fig2.add_annotation(x=0.98, y=0.08 if row_i in (1, 3) else 0.92, xref="x domain",
                                yref="y domain", text=f"{lb} R²={r2v:.2f}",
                                showarrow=False, font=dict(size=9, color=color),
                                xanchor="right", row=row_i, col=1)
    fig2.update_xaxes(title_text="ln(基本面)", tickfont=dict(size=9), row=3, col=1)
    fig2.update_yaxes(title_text="ln(股价)", tickfont=dict(size=9))
    fig2.update_layout(title=dict(text="<b>成熟期：当期 vs 前瞻基本面与股价的拟合（对数相关性）</b>",
                                  x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
                       template="plotly_white", height=680,
                       legend=dict(orientation="h", yanchor="bottom", y=1.03, font=dict(size=10)),
                       margin=dict(l=60, r=40, t=50, b=50))

    # ── 图3：拟合指标对比（MAD 与倍数稳定性） ──
    labels_short = [m["label"] for m in metrics]
    mad_vals = [m["mad"] for m in metrics]
    iqr_vals = [m["iqr"] for m in metrics]
    r2_vals = [m["r2"] for m in metrics]
    colors_bar = [C["midblue"] if "当期" in lb else C["orange"] for lb in labels_short]
    fig3 = make_subplots(rows=2, cols=1,
                         subplot_titles=("<b>拟合误差 MAD（中位倍数隐含价 vs 实际价，越低越好）</b>",
                                         "<b>倍数稳定性 IQR/中位（越低越好）</b>"),
                         vertical_spacing=0.12, row_heights=[0.5, 0.5])
    fig3.add_trace(go.Bar(x=labels_short, y=mad_vals, marker_color=colors_bar,
                          text=[f"{v:.1f}%" for v in mad_vals], textposition="outside",
                          textfont=dict(size=9)), row=1, col=1)
    fig3.add_trace(go.Bar(x=labels_short, y=iqr_vals, marker_color=colors_bar,
                          text=[f"{v:.2f}" for v in iqr_vals], textposition="outside",
                          textfont=dict(size=9)), row=2, col=1)
    fig3.update_layout(title=dict(text="<b>前瞻 vs 当期：拟合误差与倍数稳定性对比</b>",
                                  x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
                       template="plotly_white", height=520,
                       margin=dict(l=60, r=40, t=50, b=60), showlegend=False)
    fig3.update_xaxes(tickangle=20, tickfont=dict(size=9))
    fig3.update_yaxes(gridcolor="#f0f0f0", row=1, col=1)
    fig3.update_yaxes(gridcolor="#f0f0f0", row=2, col=1)

    # ── 前瞻拟合解读 ──
    mt_rows = ""
    for m in metrics:
        mt_rows += (f"<tr><td>{m['label']}</td><td>{m['n']}</td><td>{m['p50']:.2f}×</td>"
                    f"<td>{m['iqr']:.2f}</td><td>{m['mad']:.1f}%</td>"
                    f"<td>{m['r']:+.2f}</td><td>{m['r2']:.3f}</td><td>{m['rho']:+.2f}</td></tr>")
    note2 = (
        "<b>前瞻拟合解读 — 用下一期基本面检验市场定价（前瞻倍数）：</b><br><br>"
        "<table><thead><tr><th>模型口径</th><th>n</th><th>倍数P50</th><th>稳定性 IQR/中位</th>"
        "<th>拟合误差 MAD</th><th>相关系数 r</th><th>R²</th><th>Spearman ρ</th></tr></thead>"
        f"<tbody>{mt_rows}</tbody></table><br>"
        "<b>① 相关性（R²）为何都低、甚至为负？</b>成熟期单阶段内，股价主要由<b>倍数自身的周期波动</b>驱动"
        "（2022 高位 → 2023-24 压缩 → 2025 回升），而 BPS/营收持续上升——基本面水平本身无法单独解释股价，"
        "R² 低（≤0.25）甚至为负（PB 当期 r=-0.48）正是“倍数周期 > 基本面增长”的体现。"
        "<b>因此选择模型不能只看相关性，更要看倍数稳定性与拟合误差。</b><br><br>"
        "<b>② 前瞻 vs 当期：</b>前瞻 PB（下一季度 BPS）的稳定性与拟合误差均优于当期"
        "（IQR/中位 0.22 vs 0.24，MAD 10.6% vs 12.0%）——市场定价确实<b>前瞻 BPS</b>；"
        "PS 前瞻 IQR 0.17 更窄，但 PS 与盈利质量脱钩，仅作旁证；"
        "PE(TTM) 无论当期还是前瞻都不可用（亏损期无定义、盈利期极不稳定）。<br><br>"
        "<b>③ 哪个好用？</b>"
        "· <b>前瞻 PB 最好用</b>：全程可定义 + 前瞻拟合误差最小（MAD 10.6%）+ BPS 是唯一可由盈利预测直接滚动的基本面"
        "——这正是 §5 峰值预测用 PB×2028E BPS 的原因。<br>"
        "· <b>周期均值PE 仍是最稳的盈利锚</b>（MAD 8.7%，公平价值用）。<br>"
        "· <b>PE(TTM) 被否决</b>（含前瞻口径）。"
    )

    def fmt(st):
        return (f"P25={st['p25']:.1f} / P50={st['p50']:.1f} / P75={st['p75']:.1f}"
                f"（P10-P90: {st['p10']:.1f}-{st['p90']:.1f}）")

    table_rows = (
        f"<tr><td><b>PB 市净率</b></td><td>股价/BPS</td><td>{fmt(pb_st)}</td>"
        f"<td>0.24（稳定期0.23）</td><td>{mad_pb:.1f}%（稳定期{mad_pb_s:.1f}%）</td>"
        f"<td style='color:#27ae60'>✅ 全程可定义</td>"
        f"<td style='color:#e67e22'><b>峰值预测主模型</b></td></tr>"
        f"<tr><td><b>周期均值PE</b></td><td>股价/滚动8Y均值EPS</td><td>{fmt(pecyc_st)}</td>"
        f"<td>0.22（稳定期0.19）</td><td>{mad_cyc:.1f}%（稳定期{mad_cyc_s:.1f}%）</td>"
        f"<td style='color:#27ae60'>✅ 全程可定义</td>"
        f"<td style='color:#2980b9'><b>公平价值主模型</b></td></tr>"
        f"<tr><td>PS 市销率</td><td>市值/TTM营收</td><td>{fmt(ps_st)}</td>"
        f"<td>0.22</td><td>{mad_ps:.1f}%</td>"
        f"<td style='color:#27ae60'>✅ 全程可定义</td><td>旁证</td></tr>"
        + (f"<tr><td>PE(TTM)</td><td>股价/TTM EPS</td>"
           f"<td>盈利期 P50={pet_st['p50']:.1f}x（P25-P75: {pet_st['p25']:.1f}-{pet_st['p75']:.1f}）</td>"
           f"<td>4.25（极不稳定）</td><td>亏损期无定义</td>"
           f"<td style='color:#c0392b'>❌ 亏损期无意义</td><td style='color:#c0392b'>否决</td></tr>"
           if pet_st else "")
    )

    note = (
        "<b>模型验证结论 — 用成熟期 56 个月的真实市场数据判定：</b><br><br>"
        "<table><thead><tr><th>模型</th><th>定义</th><th>成熟期分布（2022+）</th>"
        "<th>稳定性 IQR/中位</th><th>拟合误差 MAD</th><th>全程可定义</th><th>判定</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table><br>"
        "<b>为什么 TTM PE 被否决：</b>牧原在 2023/2024/2026 亏损期 TTM EPS 为负或趋零，"
        "PE 无定义或极端放大（成熟期 P10 达 -208×），无法作为稳定估值锚。<br><br>"
        "<b>为什么 PB 与周期均值PE 胜出：</b>"
        "① 两者在成熟期分布稳定（IQR/中位 0.19-0.24），以中位倍数回推股价，"
        "中位绝对误差仅 9-12%；② 亏损期依然可定义；"
        "③ 剔除 2022H1 过渡期（仍带扩张期心态、PB 6×+）后，"
        f"PB 分布收窄至 P25-P75 = {pb_s['p25']:.2f}-{pb_s['p75']:.2f}、"
        f"周期PE = {pecyc_s['p25']:.1f}-{pecyc_s['p75']:.1f}。<br><br>"
        f"<b>两者分工：</b>周期均值PE 用于<b>公平价值</b>（AVG8_EPS {AVG8_EPS:.2f} × 成熟期 "
        f"P25-P75 {pecyc_st['p25']:.1f}-{pecyc_st['p75']:.1f} ≈ <b>{fv_lo:.0f}-{fv_hi:.0f}元</b>），"
        "PB 用于<b>峰值预测</b>（BPS 可直接由盈利预测滚动，不受周期窗口选择影响）。"
        f"<br>· 当前价格 <b>{CURRENT_PRICE:.1f} 元</b> = 周期PE {cur_cycpe:.1f}×"
        f"（≈P10 {pecyc_st['p10']:.1f}，处于最低十分位）、PB {cur_pb:.1f}×（低于 P25 {pb_st['p25']:.1f}）"
        "——处于成熟期分布<b>偏低区域</b>。<br>"
        "· <b>局限：</b>历史分布忽略结构性变化（出栏规模、成本结构、H股摊薄），"
        "分位数只是参照，不是结论。"
    )
    return [(fig, note), (fig2, note2), (fig3, "")]


def ch15_peak_forecast():
    """基于财务预测的峰值预测 — 市场验证模型（PB）× 2028E 基本面

    峰值倍数校准：2025 年成熟期实际峰值（股价高点 59.68 元 / BPS 14.04 = PB 4.25×；
    2025-08 月度收盘 55.0 / BPS 13.89 = 3.96×）→ 取 3.9-4.3×。
    交叉验证：周期均值PE 峰值（2025 峰值 25.8×，成熟期 P90 23.9×）；峰值PE（2025 峰值 21.3×）。
    """
    df_qf = pd.read_csv(ROOT / "data" / "主要财务指标_按单季度.csv", dtype=str)
    df_qf["REPORT_DATE"] = pd.to_datetime(df_qf["REPORT_DATE"])
    df_qf["BPS"] = pd.to_numeric(df_qf["BPS"], errors="coerce")
    q4 = df_qf[df_qf["REPORT_DATE"].dt.month == 12].sort_values("REPORT_DATE")
    bps_2025 = float(q4[q4["REPORT_DATE"].dt.year == 2025]["BPS"].iloc[0])

    hist = {y: FIN[y]["eps"] for y in FIN if 2021 <= y <= 2025}
    hist_keys = sorted(hist.keys())

    pb_lo, pb_hi = 3.9, 4.3      # 2025 成熟期峰值 PB（月度 3.96 / 年度高点 4.25）
    cyc_lo, cyc_hi = 23.8, 25.8  # 2025 峰值周期PE（月度 23.8 / 年度高点 25.8）
    pe_peak = 21.3               # 2025 年度高点对应 trailing PE（59.68/2.80）

    scenarios = ["上行", "基准", "下行"]
    labels = []
    bars_y, bars_lo, bars_hi = [], [], []
    cyc_mid, pe_mid = [], []
    peak_pb, roe_map = {}, {}
    table_rows = ""
    for sc in scenarios:
        e26 = FORECAST[sc][2026]["eps"]
        e27 = FORECAST[sc][2027]["eps"]
        e28 = FORECAST[sc][2028]["eps"]
        bps28 = bps_2025 + e26 + e27 + e28
        cyc28 = (sum(hist[y] for y in hist_keys) + e26 + e27 + e28) / 8
        p_pb_lo = bps28 * pb_lo
        p_pb_hi = bps28 * pb_hi
        p_pb_mid = (p_pb_lo + p_pb_hi) / 2
        p_cyc_lo = cyc28 * cyc_lo
        p_cyc_hi = cyc28 * cyc_hi
        p_pe = e28 * pe_peak
        labels.append(f"{sc}<br>{'2028E EPS' if sc == '基准' else ''}")
        bars_y.append(p_pb_mid)
        bars_lo.append(p_pb_mid - p_pb_lo)
        bars_hi.append(p_pb_hi - p_pb_mid)
        cyc_mid.append((p_cyc_lo + p_cyc_hi) / 2)
        pe_mid.append(p_pe)
        roe_implied = e28 / bps28 * 100 if bps28 > 0 else 0
        peak_pb[sc] = (p_pb_lo, p_pb_hi)
        roe_map[sc] = roe_implied
        pe_flag = ""
        if p_pe > 0 and roe_implied > 25:
            pe_flag = f"<span style='color:#c0392b'>⚠️ 隐含ROE {roe_implied:.0f}% 超成熟期历史，PE 法会高估</span>"
        elif p_pe <= 0:
            pe_flag = "<span style='color:#999'>亏损年无峰值PE</span>"
        table_rows += (
            f"<tr><td><b>{sc}</b></td><td>{e28:.2f}</td><td>{bps28:.2f}</td><td>{cyc28:.2f}</td>"
            f"<td style='font-weight:600'>{p_pb_lo:.0f}-{p_pb_hi:.0f}</td>"
            f"<td>{p_cyc_lo:.0f}-{p_cyc_hi:.0f}</td>"
            f"<td>{p_pe:.0f}</td><td>{pe_flag}</td></tr>")

    # 公平价值带（来自 ch14 成熟期分布，兜底 21-26×）
    pecyc_st = _CH14_CACHE.get("pecyc_st")
    if pecyc_st is None:
        pecyc_st = {"p25": 21.0, "p75": 26.0}
    fv_lo = AVG8_EPS * pecyc_st["p25"]
    fv_hi = AVG8_EPS * pecyc_st["p75"]
    b_lo, b_hi = peak_pb["基准"]
    u_lo, u_hi = peak_pb["上行"]
    d_lo, d_hi = peak_pb["下行"]
    e28_up = FORECAST["上行"][2028]["eps"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=bars_y, name="PB峰值模型（2028E BPS × 3.9-4.3×）",
        marker_color=C["orange"],
        error_y=dict(type="data", symmetric=False, array=bars_hi, arrayminus=bars_lo,
                     thickness=1.5, color="#7f8c8d")))
    fig.add_trace(go.Scatter(
        x=labels, y=cyc_mid, mode="markers+text", name="周期均值PE交叉（×23.8-25.8）",
        marker=dict(color=C["teal"], size=10, symbol="diamond"),
        text=[f"{v:.0f}" for v in cyc_mid], textposition="bottom center",
        textfont=dict(size=10, color=C["teal"])))
    fig.add_trace(go.Scatter(
        x=labels, y=pe_mid, mode="markers", name="峰值PE交叉（×21.3）",
        marker=dict(color=C["red"], size=8, symbol="x")))
    fig.add_hline(y=CURRENT_PRICE, line_dash="dash", line_color="#2c3e50", line_width=1.2,
                  annotation_text=f"当前价 {CURRENT_PRICE:.1f} 元", annotation_position="right")
    fig.add_hrect(y0=fv_lo, y1=fv_hi, fillcolor="rgba(46,204,113,0.08)", line_width=0,
                  annotation_text=f"公平价值带 {fv_lo:.0f}-{fv_hi:.0f} 元", annotation_position="top left")
    fig.update_layout(
        title=dict(text="<b>2028E 周期峰值股价预测 — 市场验证 PB 模型 × 财务预测</b>",
                   x=0.02, y=0.99, font=dict(size=15, color="#1a1a1a")),
        template="plotly_white", height=480,
        yaxis_title="<b>峰值股价（元）</b>",
        legend=dict(orientation="h", yanchor="bottom", y=1.08, font=dict(size=10)),
        margin=dict(l=60, r=40, t=60, b=50))
    fig.update_xaxes(tickfont=dict(size=12))
    fig.update_yaxes(gridcolor="#f0f0f0")

    note = (
        "<b>峰值预测方法 — 唯一主模型：PB × 成熟期实测峰值倍数</b><br><br>"
        "市场验证逻辑：2025 年（成熟期最典型的峰值年）股价高点 59.68 元 ÷ BPS 14.04 = <b>PB 4.25×</b>；"
        "2025-08 月度收盘 55.0 ÷ BPS 13.89 = 3.96×。取 <b>3.9-4.3×</b> 作为峰值倍数，"
        "作用于财务预测滚动出的 <b>2028E BPS</b>。<br><br>"
        "<table><thead><tr><th>情景</th><th>2028E EPS</th><th>2028E BPS</th><th>2028E 周期EPS(8Y)</th>"
        "<th>PB峰值价（主）</th><th>周期PE交叉</th><th>峰值PE交叉</th><th>备注</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table><br>"
        "<b>为什么不用“峰值 EPS × PE”：</b>把 PE 直接乘到峰值 EPS 上是“双重周期化”——"
        "周期股峰值盈利对应的 PE 天然被压缩（2025 峰值 trailing PE 仅 21×、2022 峰值 26×），"
        f"且上行情景 EPS {e28_up:.2f} 隐含 ROE {roe_map['上行']:.0f}%，"
        "远超成熟期历史峰值（20-25%），PE 法将显著高估。<br><br>"
        "<b>交叉验证说明：</b>"
        "① 周期均值PE（8Y 2021-2028 平均 EPS × 峰值倍数 23.8-25.8×）给出偏低结果——"
        "因为 8 年窗口把 2026 年创纪录亏损（-2.07 EPS）计入均值，窗口敏感，仅作下限参照；"
        "② 峰值PE（2028E EPS × 21.3×）给出偏高结果——隐含 ROE 超历史，仅作上限参照。<br><br>"
        f"<b>结论：</b>基准情景 2028 周期峰值约 <b>{b_lo:.0f}-{b_hi:.0f} 元</b>"
        f"（{(b_lo / CURRENT_PRICE - 1) * 100:+.0f}%~{(b_hi / CURRENT_PRICE - 1) * 100:+.0f}% vs 当前 {CURRENT_PRICE:.1f}），"
        f"上行情景约 <b>{u_lo:.0f}-{u_hi:.0f} 元</b>"
        f"（{(u_lo / CURRENT_PRICE - 1) * 100:+.0f}%~{(u_hi / CURRENT_PRICE - 1) * 100:+.0f}%）。"
        "若猪价超预期冲高（16-18 元/kg）且 PB 维持 4×，峰值可挑战 100 元以上——"
        "与 B站视频研究 70-100 元区间一致，但倍数来自成熟期市场实测而非假设。<br>"
        "· <b>风险：</b>峰值 PB 存在递减趋势（2022 过渡期 5.1× → 2025 成熟期 4.25×），"
        "H 股发行摊薄 BPS，若 2028 峰值 PB 降至 3.5-3.8×，峰值价将回落至 59-64 元（基准）。"
    )
    return [(fig, note)]


def main():
    print("\n" + "=" * 60)
    print("牧原股份 估值分析 — 第 6 步（市场验证框架）")
    print("=" * 60)

    # 生成图表
    chart_funcs = [
        ("eps_price_ch12", ch12_eps_price_relationship),
        ("stage_dist_ch12", ch13_stage_distribution),
        ("stage_model_ch14", ch14_stage_model_validation),
        ("peak_forecast_ch15", ch15_peak_forecast),
    ]

    chart_html = {}
    for name, func in chart_funcs:
        try:
            result = func()
            if isinstance(result, (list, tuple)):
                parts = []
                for idx, item in enumerate(result, 1):
                    if isinstance(item, tuple) and len(item) == 2:
                        fig, note_html = item
                    else:
                        fig, note_html = item, ""
                    div_id = f"{name}_{idx}"
                    if hasattr(fig, "to_html"):
                        parts.append(fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id,
                                                 config={"responsive": True, "displayModeBar": False}))
                    elif fig and isinstance(fig, str):
                        parts.append(fig)
                    if note_html:
                        parts.append(f'<div class="chart-note">' + note_html + '</div>')
                chart_html[name] = "".join(parts)
            elif isinstance(result, str):
                chart_html[name] = '<div class="chart-note">' + result + '</div>'
            else:
                chart_html[name] = result.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                                                  config={"responsive": True, "displayModeBar": False})
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            import traceback; traceback.print_exc()
            chart_html[name] = f"<p style='color:#c0392b'>图表生成失败: {e}</p>"

    # 组装 HTML
    html = HTML.format(
        style=STYLE, today=TODAY_STR,
        eps_price_ch12=chart_html.get("eps_price_ch12", ""),
        stage_dist_ch12=chart_html.get("stage_dist_ch12", ""),
        stage_model_ch14=chart_html.get("stage_model_ch14", ""),
        peak_forecast_ch15=chart_html.get("peak_forecast_ch15", ""),
        # 期货市场变量
        sc_base_price=sc_base_price,
        lh2611=lh2611, lh2705=lh2705,
        avg_fut_2027h1=avg_futures_2027h1,
        futures_vs_base=futures_vs_base,
        futures_scenario_label=futures_scenario_label,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"\n✅ 报告已生成: {REPORT_PATH}")
    print(f"   文件大小: {REPORT_PATH.stat().st_size / 1024:.0f} KB")

if __name__ == "__main__":
    main()
