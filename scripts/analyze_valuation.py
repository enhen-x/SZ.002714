# -*- coding: utf-8 -*-
"""
牧原股份估值分析 — 牧原股份 (SZ.002714)
证券分析八步流程 · 第6步：估值

四种方法交叉验证（Hooke 框架）：
  1. DCF 内在价值法（权重 ~20%）
  2. 相对价值法（权重 ~60%）—— 核心方法
  3. 并购价值法（权重 ~10%）
  4. LBO 杠杆收购法（权重 ~10%）

周期型公司调整：使用完整周期平均盈利，安全边际 ±15%
"""

import json
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

# 加载历史PE数据（来自主要财务指标）
HIST_PE = {}
for _, row in annual_indicator.iterrows():
    yr = int(row["_year"])
    if 2018 <= yr <= 2025:
        per_toi = safe_float(row.get("PER_TOI"), None)  # 年末滚动PE(TTM)
        per_oi = safe_float(row.get("PER_OI"), None)    # 年末静态PE
        eps = safe_float(row.get("EPSJB"), 0)
        pe = per_toi if per_toi and per_toi < 200 else (per_oi if per_oi and per_oi < 200 else None)
        # 亏损年份PE无意义，但仍记录（标注"亏损"）
        HIST_PE[yr] = {"pe": pe, "eps": eps, "is_loss": eps < 0}
if HIST_PE:
    pe_str = ", ".join(f"{yr}:{HIST_PE[yr]['pe']:.1f}×" if HIST_PE[yr]['pe'] and not HIST_PE[yr]['is_loss']
                       else f"{yr}:亏损" for yr in sorted(HIST_PE.keys()))
    print(f"历史PE(TTM): {pe_str}")
    # 当前PE（最新年份年末PE，或使用CURRENT_PRICE/AVG8_EPS作为周期PE参考）
    CURRENT_PE_CYCLE = CURRENT_PRICE / AVG8_EPS  # 19.3 — 当前周期PE
else:
    CURRENT_PE_CYCLE = CURRENT_PRICE / AVG8_EPS

# ==================== 预测数据（从 FORECAST 模型加载） ====================

# 复用 analyze_forecast.py 的核心假设
AVG_WEIGHT = 110
REV_MULTIPLIER = 1.16
NON_HOG_COST_RATE = 0.90
INTEREST_RATE = 0.035
TAX_RATE_LOW = 0.0
TAX_RATE_HIGH = 0.05
COST_RATES = {"sale_rate": 0.23, "manage_rate": 0.92, "rd_rate": 1.15}

# D&A/营收比率（2023-2025年3年均值，用于FORECAST和DCF统一口径）
_da_rates_3y = []
for _yr in [2023, 2024, 2025]:
    if _yr in FIN and FIN[_yr].get("depreciation", 0) > 0 and FIN[_yr]["revenue"] > 0:
        _da_rates_3y.append(FIN[_yr]["depreciation"] / FIN[_yr]["revenue"])
DA_RATE = sum(_da_rates_3y) / len(_da_rates_3y) if _da_rates_3y else 0.10
print(f"统一D&A率（3Y均值）: {DA_RATE*100:.1f}% (各年: {[f'{r*100:.1f}%' for r in _da_rates_3y]})")

HOG_FORECAST = {2025: 7798, 2026: 8100, 2027: 8300, 2028: 8500}
PRICE_SCENARIOS = {
    "上行": {2025: 14.4, 2026: 11.0, 2027: 14.0, 2028: 15.5},
    "基准": {2025: 14.4, 2026: 10.5, 2027: 12.5, 2028: 13.5},
    "下行": {2025: 14.4, 2026: 10.0, 2027: 11.0, 2028: 11.5},
}
COST_SCENARIOS = {
    "基准": {2025: 12.0, 2026: 11.5, 2027: 11.3, 2028: 11.0},
}

def project_ebit_eps(scenario, year):
    """返回 (ebit, eps, revenue, interest_exp, total_profit)"""
    hog = HOG_FORECAST.get(year, 8500)
    price = PRICE_SCENARIOS[scenario][year]
    cost_per_kg = COST_SCENARIOS["基准"][year]

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

def peak_year_financials(pig_price, hog=8600, cost=11.0, year_label="峰值年"):
    """给定猪价下的峰值年财务数据——用于周期高峰情景分析"""
    hog_rev_raw = hog * AVG_WEIGHT * pig_price / 1e4
    total_rev = hog_rev_raw * REV_MULTIPLIER
    hog_cost = hog * AVG_WEIGHT * cost / 1e4
    non_hog_rev = total_rev - hog_rev_raw
    non_hog_cost = non_hog_rev * NON_HOG_COST_RATE
    total_cost = hog_cost + non_hog_cost
    gross_profit = total_rev - total_cost
    sale_exp = total_rev * COST_RATES["sale_rate"] / 100
    manage_exp = total_rev * COST_RATES["manage_rate"] / 100
    rd_exp = total_rev * COST_RATES["rd_rate"] / 100
    base_debt = FIN[LATEST]["interest_debt"]
    net_debt = base_debt * 0.65  # 周期高峰时已部分去杠杆（2025末~570→高峰~370亿）
    fin_exp = net_debt * INTEREST_RATE
    op_profit = gross_profit - sale_exp - manage_exp - rd_exp - fin_exp
    total_profit = op_profit
    ebit = total_profit + fin_exp
    tax_rate = TAX_RATE_HIGH if total_profit > 100 else TAX_RATE_LOW
    income_tax = max(total_profit * tax_rate, 0)
    net_profit = total_profit - income_tax
    parent_profit = net_profit * 0.98
    eps = parent_profit / TOTAL_SHARES
    da_est = total_rev * DA_RATE
    ebitda = ebit + da_est
    return {"eps": eps, "ebit": ebit, "ebitda": ebitda, "revenue": total_rev,
            "parent_profit": parent_profit, "pig_price": pig_price, "cost": cost,
            "hog": hog, "year": year_label}

FORECAST = {}
for sc in ["基准", "上行", "下行"]:
    FORECAST[sc] = {}
    for yr in [2025, 2026, 2027, 2028]:
        ebit, eps, rev, ie, tp = project_ebit_eps(sc, yr)
        # EBITDA = EBIT + D&A（使用3年均值DA_RATE，与DCF模型一致）
        da_est = rev * DA_RATE
        FORECAST[sc][yr] = {"ebit": ebit, "eps": eps, "revenue": rev,
                            "interest_exp": ie, "total_profit": tp,
                            "ebitda": ebit + da_est, "da": da_est}

# 周期正常化 EBITDA（使用 2027E 基准——中周期年份，避免8年均值被2023巨亏拖低）
NORM_EBITDA = FORECAST["基准"][2027]["ebitda"]
print(f"正常化 EBITDA (2027E): {NORM_EBITDA:.0f}亿")

# ==================== 生猪期货远期曲线 ====================
# 来源：大连商品交易所 LH合约 2026-07-28收盘价
# 用途：市场对未来猪价的"真金白银"定价，用于校准模型猪价假设

df_futures = load_csv("生猪期货远期曲线.csv")
FUTURES_CURVE = {}
if not df_futures.empty:
    for _, row in df_futures.iterrows():
        month = str(row.get("交割月份", ""))[:7]  # "2026-09-01" → "2026-09"
        price = safe_float(row.get("期货价格_元每公斤"), 0)
        volume = safe_float(row.get("持仓量"), 0)
        if month and price > 0:
            FUTURES_CURVE[month] = {"price": price, "volume": volume}

if FUTURES_CURVE:
    print(f"生猪期货远期曲线 ({len(FUTURES_CURVE)}个合约):")
    for m in sorted(FUTURES_CURVE.keys()):
        fc = FUTURES_CURVE[m]
        print(f"  {m}: {fc['price']:.2f}元/kg (持仓{fc['volume']:,.0f})")

    # 对比模型假设
    # 2026年模型基准 = 10.5（全年均价），但H1实际9.48，H2需更高才能拉平
    # 2027年模型基准 = 12.5
    futures_2026h2 = [fc["price"] for m, fc in FUTURES_CURVE.items() if m.startswith("2026")]
    futures_2027h1 = [fc["price"] for m, fc in FUTURES_CURVE.items() if m.startswith("2027")]
    avg_futures_2026h2 = sum(futures_2026h2) / len(futures_2026h2) if futures_2026h2 else 0
    avg_futures_2027h1 = sum(futures_2027h1) / len(futures_2027h1) if futures_2027h1 else 0

    print(f"  期货隐含2026H2均价: {avg_futures_2026h2:.2f}元/kg (模型基准全年={PRICE_SCENARIOS['基准'][2026]:.1f})")
    print(f"  期货隐含2027H1均价: {avg_futures_2027h1:.2f}元/kg (模型基准全年={PRICE_SCENARIOS['基准'][2027]:.1f})")

    # 判断：期货在模型的哪个情景？
    if avg_futures_2027h1 > 0:
        base_price = PRICE_SCENARIOS["基准"][2027]
        up_price = PRICE_SCENARIOS["上行"][2027]
        down_price = PRICE_SCENARIOS["下行"][2027]
        if avg_futures_2027h1 >= up_price:
            futures_scenario = "上行"
        elif avg_futures_2027h1 >= base_price:
            futures_scenario = "基准偏上"
        elif avg_futures_2027h1 >= down_price:
            futures_scenario = "下行偏上"
        else:
            futures_scenario = "下行"
        print(f"  期货市场定价偏向: {futures_scenario}情景 (期货2027H1={avg_futures_2027h1:.2f} vs 基准={base_price})")
else:
    avg_futures_2026h2 = 0
    avg_futures_2027h1 = 0
    futures_scenario = "数据缺失"
    print("⚠️ 生猪期货数据缺失，跳过期货对比分析")

# ==================== 历史周期低谷验证 ====================
# 目的：用历史低谷数据校准周期PE下限——模型PE 15-22×是否与市场实际定价一致？
# 方法：对每个低谷年份，计算"股价最低点 ÷ 当时滚动8年周期均值EPS = 低谷周期PE"

# 历史股价高低点（前复权，来源：同花顺/东方财富历史行情）
STOCK_ANNUAL_RANGE = {
    2017: (15, 9), 2018: (15, 5), 2019: (35, 14), 2020: (100, 35),
    2021: (92, 40), 2022: (63, 45), 2023: (55, 35), 2024: (88, 48), 2025: (79, 50),
    2026: (50, 35),  # 截至2026-08-04：年初~50 → 年中低点~35，当前39.3
}

# 计算每年滚动8年周期均值EPS
TROUGH_DATA = {}
for yr in range(2017, 2027):
    if yr not in FIN: continue
    cycle_years = [y for y in range(yr-7, yr+1) if y in FIN]
    if len(cycle_years) < 5: continue
    cycle_eps = sum(FIN[y]["eps"] for y in cycle_years) / len(cycle_years)
    sh, sl = STOCK_ANNUAL_RANGE.get(yr, (0, 0))
    pe_cycle_low = sl / cycle_eps if cycle_eps > 0.1 else 99
    pb_low = sl / FIN[yr].get("bvps", FIN[yr]["total_equity"] / TOTAL_SHARES) if FIN[yr].get("total_equity", 0) > 0 else 99
    TROUGH_DATA[yr] = {
        "eps": FIN[yr]["eps"], "cycle_eps": cycle_eps, "bps": FIN[yr]["total_equity"] / TOTAL_SHARES,
        "stock_high": sh, "stock_low": sl, "pe_cycle_low": pe_cycle_low,
        "pb_low": pb_low, "roe": FIN[yr].get("roe", 0),
    }

# 关键低谷年份
TROUGH_KEY_YEARS = [2018, 2021, 2023, 2025]
print(f"\n历史低谷PE验证 (滚动8Y周期EPS):")
for yr in TROUGH_KEY_YEARS:
    if yr in TROUGH_DATA:
        td = TROUGH_DATA[yr]
        print(f"  {yr}: 股价最低{td['stock_low']:.0f}元, 周期EPS={td['cycle_eps']:.2f}, "
              f"低谷周期PE={td['pe_cycle_low']:.1f}×, 低谷PB={td['pb_low']:.1f}×, ROE={td['roe']:.1f}%")

# 2018年前后对比（排除2019过渡年——猪价从12崩到41，股价剧烈波动不具备参考性）
pre_2019 = [td["pe_cycle_low"] for yr, td in TROUGH_DATA.items() if yr < 2019 and td["pe_cycle_low"] < 50]
post_2020 = [td["pe_cycle_low"] for yr, td in TROUGH_DATA.items() if yr >= 2021 and td["pe_cycle_low"] < 50]
avg_trough_pre = sum(pre_2019)/len(pre_2019) if pre_2019 else 0
avg_trough_post = sum(post_2020)/len(post_2020) if post_2020 else 0
# 2021年后最低低谷周期PE（2023年亏损年的20.6×是真正的压力测试）
trough_pe_floor = min(post_2020) if post_2020 else 20
trough_pe_avg = avg_trough_post
print(f"  2018前低谷PE均值: {avg_trough_pre:.1f}× (小盘/非瘟前)")
print(f"  2021后低谷PE均值: {avg_trough_post:.1f}× ({len(post_2020)}个年份)")
print(f"  2021后低谷PE下限: {trough_pe_floor:.1f}× (发生在2023亏损年)")

# 当前股价 vs 历史低谷PE下限
current_cycle_pe = CURRENT_PRICE / AVG8_EPS
floor_price_historical = AVG8_EPS * trough_pe_floor  # 历史低谷PE下限对应的理论底价
fair_trough_avg = AVG8_EPS * trough_pe_avg  # 历史低谷PE均值对应的公允价
print(f"  当前周期PE={current_cycle_pe:.1f}× (股价{CURRENT_PRICE}/周期EPS{AVG8_EPS:.2f})")
print(f"  2021后低谷PE下限={trough_pe_floor:.1f}× → 理论底价={floor_price_historical:.0f}元")
print(f"  2021后低谷PE均值={trough_pe_avg:.1f}× → 低谷公允价={fair_trough_avg:.0f}元")
print(f"  当前{CURRENT_PRICE}元 vs 历史底价{floor_price_historical:.0f}元 → "
      f"{'高于' if CURRENT_PRICE >= floor_price_historical else '低于'}历史低谷下限")

# ==================== 同行数据 ====================

# 基本面数据（来自 analyze_finance.py PEERS + 公司分析报告）
# EPS周期均值：2018-2025年8年均值，正邦2023年用扣非EPS（剔除债务重组一次性收益~85亿）
PEERS = {
    "牧原股份": {"code": "002714", "debt": 62.9, "roe": 20.6, "gross": 17.8, "net_m": 11.0,
                 "cost_kg": 11.3, "hog_2025": 7798, "mkt_cap": CURRENT_MKT_CAP,
                 "eps_2025": FIN[2025]["eps"], "eps_cycle": AVG8_EPS,
                 "bvps": FIN[2025]["total_equity"] / TOTAL_SHARES},
    "温氏股份": {"code": "300498", "debt": 55.0, "roe": 12.0, "gross": 10.0, "net_m": 6.5,
                 "cost_kg": 12.2, "hog_2025": 4048, "mkt_cap": 1129, "eps_2025": 1.35,
                 # 8Y: 0.75,2.22,1.18,-2.11,0.82,-0.97,1.39,0.79 → avg=0.51
                 "eps_cycle": 0.51, "bvps": 5.0},
    "新希望":   {"code": "000876", "debt": 72.0, "roe": 5.0,  "gross": 6.0,  "net_m": 3.0,
                 "cost_kg": 12.7, "hog_2025": 1755, "mkt_cap": 443,  "eps_2025": 0.71,
                 # 8Y: 0.40,1.22,1.17,-2.20,-0.36,0.04,0.09,0.17 → avg=0.07 (周期均值接近0)
                 "eps_cycle": 0.07, "bvps": 5.5},
    "正邦科技": {"code": "002157", "debt": 85.0, "roe": -15.0,"gross": 3.0,  "net_m": -8.0,
                 "cost_kg": 13.3, "hog_2025": 854,  "mkt_cap": 255,  "eps_2025": 0.10,
                 # 8Y: 0.08,0.69,2.29,-6.01,-4.28,-1.47(扣非),0.02,-0.06 → avg=-1.09
                 "eps_cycle": -1.09, "bvps": 1.3},
    "神农集团": {"code": "605296", "debt": 35.0, "roe": 15.0, "gross": 16.0, "net_m": 12.0,
                 "cost_kg": 12.5, "hog_2025": 320,  "mkt_cap": 150,  "eps_2025": 1.29,
                 # 8Y: 0.20,1.32,3.16,0.64,0.49,-0.77,1.31,0.65 → avg=0.88
                 "eps_cycle": 0.88, "bvps": 9.1},
}

# 同行行情（网页搜索 2026-07，来源：亿牛网 eniu.com）
PEER_MARKET = {
    "牧原股份": {"pe_ttm": 11.85, "pb": 3.42, "price": 39.3},
    "温氏股份": {"pe_ttm": 24.81, "pb": 2.87, "price": 14.1},
    "新希望":   {"pe_ttm": 10.39, "pb": 1.72, "price": 9.8},
    "正邦科技": {"pe_ttm": 2.19,  "pb": 2.19, "price": 2.9},
    "神农集团": {"pe_ttm": 50.76, "pb": 3.19, "price": 31.3},
}

# 为每个同行计算周期PE和EV/EBITDA
# 关键修正(Hooke)：周期型公司使用周期平均EPS，而非单年EPS
for name in PEERS:
    p = PEERS[name]
    pm = PEER_MARKET.get(name, {})
    p["price"] = pm.get("price", 0)
    p["pb"] = pm.get("pb", 0)
    p["pe_ttm"] = pm.get("pe_ttm", 0)
    # 周期PE = 当前股价 / 8年周期均值EPS（Hooke方法论核心）
    if p["eps_cycle"] > 0.01:
        p["pe_cycle"] = p["price"] / p["eps_cycle"]
    else:
        p["pe_cycle"] = None  # 周期均值EPS≤0时PE无意义
    # 单年PE（保留用于对比）
    p["pe_2025"] = p["price"] / p["eps_2025"] if p["eps_2025"] > 0 else 99

    # EV/EBITDA：使用各公司自己的估计正常化EBITDA
    # 方法：出栏量 × 均重 × (正常化猪价14元 - 公司成本) / 1e4 × 营收乘数 × EBITDA利润率
    # 简化处理：用2025年EBITDA作为正常化代理（2025猪价14.4属中等年份）
    hog = p["hog_2025"]
    cost = p["cost_kg"]
    # 估算营收 = 出栏 × 110kg × 14.4(2025均价) × 1.16(牧原乘数代理)
    est_rev = hog * 110 * 14.4 / 1e4 * 1.16
    # 估算EBITDA = 营收 × 行业EBITDA利润率（基于成本优势调整）
    # 成本越低→EBITDA利润率越高。牧原11.3→~17%, 神农12.5→~13%, 正邦13.3→~5%
    ebitda_margin_est = max(0.03, 0.22 - (cost - 10.0) * 0.04)  # 成本每高1元,利润率降4%
    est_ebitda = est_rev * ebitda_margin_est
    # EV = 市值 + 估计有息负债（按负债率缩放牧原有息负债496亿）
    est_debt = FIN[2025]["interest_debt"] * (p["debt"] / 62.9) if p["debt"] > 0 else 0
    p["ev"] = p["mkt_cap"] + est_debt
    p["ev_ebitda"] = p["ev"] / est_ebitda if est_ebitda > 1 else 99
    p["est_ebitda"] = est_ebitda

print(f"同行周期PE: 牧原={PEERS['牧原股份']['pe_cycle']:.1f}×, "
      f"温氏={PEERS['温氏股份']['pe_cycle']:.1f}×, "
      f"神农={PEERS['神农集团']['pe_cycle']:.1f}×")

# 同行排名（维度：盈利、成本、规模、财务健康）
def rank_peers():
    """综合排名：越高越好"""
    scores = {}
    for name, p in PEERS.items():
        s = 0
        s += (1 if p["roe"] > 15 else 0.5 if p["roe"] > 5 else 0) * 3  # ROE 权重3
        s += (1 if p["cost_kg"] < 12 else 0.5 if p["cost_kg"] < 13 else 0) * 3  # 成本 权重3
        s += (1 if p["hog_2025"] > 3000 else 0.5 if p["hog_2025"] > 1000 else 0) * 2  # 规模 权重2
        s += (1 if p["debt"] < 55 else 0.5 if p["debt"] < 70 else 0) * 1.5  # 杠杆 权重1.5
        s += (1 if p["net_m"] > 8 else 0.5 if p["net_m"] > 3 else 0) * 1.5  # 净利率 权重1.5
        scores[name] = round(s, 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

PEER_RANKING = rank_peers()
print("同行排名:", PEER_RANKING)

# ==================== 方法1: DCF 估值 ====================

# DCF 参数
Rf = 2.5        # 10Y国债 %
BETA = 1.1      # 周期股Beta略高于市场
ERP = 8.0       # 股权风险溢价 %（A股较成熟市场更高）
Ke = Rf + BETA * ERP  # 11.3%
Kd = 3.5        # 债务成本 %
TAX = 5.0       # 税率 %
D_E_ratio = 0.35  # D/(D+E) 目标（低于当前40%以体现去杠杆）
WACC = Ke * (1 - D_E_ratio) + Kd * (1 - TAX/100) * D_E_ratio  # ~8.5%
TERMINAL_G = 2.0  # 永续增长率 %（保守值）

print(f"WACC={WACC:.1f}%, Ke={Ke:.1f}%")

# ==================== 积层法（Build-up Method）交叉验证WACC ====================
# Hooke建议对周期型公司用积层法交叉验证CAPM结果
# k = Rf + ERP + 行业风险溢价 + 规模风险溢价 + 公司特定风险溢价
BUILDUP_ERP = 8.0        # 权益风险溢价（与CAPM一致）
BUILDUP_INDUSTRY = -0.5  # 行业风险：养猪业属民生必需，防御性略好于市场
BUILDUP_SIZE = 0.0       # 规模风险：大盘股（~2000亿市值），无规模溢价
BUILDUP_COMPANY = 1.5    # 公司特定：周期性+高杠杆+猪价波动风险
Ke_build = Rf + BUILDUP_ERP + BUILDUP_INDUSTRY + BUILDUP_SIZE + BUILDUP_COMPANY  # = 11.5%
WACC_build = Ke_build * (1 - D_E_ratio) + Kd * (1 - TAX/100) * D_E_ratio  # ~8.6%
print(f"积层法交叉验证: Ke_build={Ke_build:.1f}%, WACC_build={WACC_build:.1f}%")
print(f"  (Rf={Rf} + ERP={BUILDUP_ERP} + 行业{BUILDUP_INDUSTRY:+.1f} + 规模{BUILDUP_SIZE:+.1f} + 公司{BUILDUP_COMPANY:+.1f})")
print(f"CAPM WACC={WACC:.1f}% vs 积层法 WACC={WACC_build:.1f}% → 差异{WACC_build-WACC:.1f}pp，取均值{WACC:.1f}%合理")

# 统一的DCF参数（基于3年历史均值，全局计算一次）
_da_rate_display = DA_RATE  # 使用统一的D&A率

_capex_rates_3y = []
for _yr in [2023, 2024, 2025]:
    if _yr in FIN and FIN[_yr]["revenue"] > 0:
        _capex_rates_3y.append(abs(FIN[_yr]["capex"]) / FIN[_yr]["revenue"])
CAPEX_RATE = sum(_capex_rates_3y) / len(_capex_rates_3y) if _capex_rates_3y else 0.10

# 历史ΔWC/营收（近3年均值，排除2021年异常扩张年）
_wc_changes = []
for _yr in [2023, 2024, 2025]:
    if _yr in FIN and FIN[_yr]["revenue"] > 0:
        _wc = FIN[_yr]["ocf"] - FIN[_yr]["net_profit"] - FIN[_yr].get("depreciation", 0)
        _wc_changes.append(_wc / FIN[_yr]["revenue"])
WC_RATE = sum(_wc_changes) / len(_wc_changes) if _wc_changes else 0.02

def dcf_valuation(wacc=WACC, terminal_g=TERMINAL_G, scenario="基准"):
    """两阶段DCF模型：5年显式预测 + 终值"""

    # 5年投影
    years = list(range(2026, 2031))
    projections = []

    for i, yr in enumerate(years):
        if yr <= 2028:
            fc = FORECAST[scenario][yr]
            rev = fc["revenue"]
            ebit = fc["ebit"]
        else:
            # 归一化年
            hog = 8600
            price = 14.0
            cost = 10.8
            hog_rev_raw = hog * AVG_WEIGHT * price / 1e4
            rev = hog_rev_raw * REV_MULTIPLIER
            hog_cost = hog * AVG_WEIGHT * cost / 1e4
            non_hog_rev = rev - hog_rev_raw
            total_cost = hog_cost + non_hog_rev * NON_HOG_COST_RATE
            gross = rev - total_cost
            expenses = rev * (COST_RATES["sale_rate"] + COST_RATES["manage_rate"] + COST_RATES["rd_rate"]) / 100
            net_debt = max(FIN[LATEST]["interest_debt"] - 115, FIN[LATEST]["interest_debt"] * 0.5)
            fin_exp = net_debt * INTEREST_RATE
            ebit = gross - expenses

        da = rev * DA_RATE
        capex = -rev * CAPEX_RATE * (0.7 if yr >= 2029 else 1.0)  # 成熟期capex下降
        delta_wc = -rev * WC_RATE
        fcf = ebit * (1 - TAX/100) + da + capex + delta_wc

        projections.append({
            "year": yr, "revenue": rev, "ebit": ebit, "da": da,
            "capex": capex, "delta_wc": delta_wc, "fcf": fcf,
        })

    # 终值 = 50%永续 + 50%退出乘数
    fcf_terminal = projections[-1]["fcf"]
    tv_perpetuity = fcf_terminal * (1 + terminal_g/100) / (wacc/100 - terminal_g/100)
    tv_exit = projections[-1]["ebit"] * 10  # EBIT × 10
    terminal_value = 0.5 * tv_perpetuity + 0.5 * tv_exit

    # 折现
    pv_fcfs = 0
    for i, proj in enumerate(projections):
        pv_fcfs += proj["fcf"] / ((1 + wacc/100) ** (i + 1))
    pv_tv = terminal_value / ((1 + wacc/100) ** len(projections))

    enterprise_value = pv_fcfs + pv_tv
    net_debt_2025 = FIN[2025]["interest_debt"]
    equity_value = enterprise_value - net_debt_2025
    value_per_share = equity_value / TOTAL_SHARES

    return {
        "projections": projections,
        "terminal_value": terminal_value,
        "pv_fcfs": pv_fcfs,
        "pv_tv": pv_tv,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "value_per_share": value_per_share,
        "tv_perpetuity": tv_perpetuity,
        "tv_exit": tv_exit,
    }

DCF_BASE = dcf_valuation()
print(f"\nDCF参数: D&A率={DA_RATE*100:.1f}% Capex率={CAPEX_RATE*100:.1f}% WC率={WC_RATE*100:.1f}% WACC={WACC:.1f}% g={TERMINAL_G:.1f}%")
print(f"DCF 基准: EV={DCF_BASE['enterprise_value']:.0f}亿, "
      f"每股={DCF_BASE['value_per_share']:.1f}元, "
      f"PV_FCFs={DCF_BASE['pv_fcfs']:.0f}亿, PV_TV={DCF_BASE['pv_tv']:.0f}亿")

# ==================== 方法2: 相对价值法 ====================

def relative_valuation():
    """使用周期平均EPS × 合理PE（Hooke方法论：周期公司用周期均值盈利）"""
    # 同行周期PE参考（基于8年周期均值EPS）：
    #   温氏 ~27.7×（排名2，但猪+鸡双主业波动更小→应享更高PE）
    #   神农 ~35.8×（排名3，小盘成长溢价）
    #   新希望 ~140×（周期EPS≈0，PE无参考意义）
    #   正邦科技 N/A（周期EPS为负）
    # 牧原排名第1（成本最低、ROE最高、规模最大），但大盘股应有一定PE折价
    # 合理周期PE：15-22×（较之前12-18×上调，反映同行周期PE水平和#1地位）

    # 基于8年周期均值 (EPS=2.04)
    pe_low, pe_mid, pe_high = 15, 19, 22
    val_low = AVG8_EPS * pe_low
    val_mid = AVG8_EPS * pe_mid
    val_high = AVG8_EPS * pe_high

    # 基于5年周期均值（更保守）
    val_low_5 = AVG5_EPS * pe_low
    val_mid_5 = AVG5_EPS * pe_mid
    val_high_5 = AVG5_EPS * pe_high

    # P/B 估值
    bvps = FIN[2025]["total_equity"] / TOTAL_SHARES
    pb_low, pb_mid, pb_high = 2.5, 3.0, 4.0
    val_pb_low = bvps * pb_low
    val_pb_mid = bvps * pb_mid
    val_pb_high = bvps * pb_high

    # EV/EBITDA 估值（使用周期正常化EBITDA）
    ev_ebitda_low, ev_ebitda_mid, ev_ebitda_high = 8, 10, 13
    val_ev_low = (NORM_EBITDA * ev_ebitda_low - FIN[2025]["interest_debt"]) / TOTAL_SHARES
    val_ev_mid = (NORM_EBITDA * ev_ebitda_mid - FIN[2025]["interest_debt"]) / TOTAL_SHARES
    val_ev_high = (NORM_EBITDA * ev_ebitda_high - FIN[2025]["interest_debt"]) / TOTAL_SHARES

    return {
        "pe_8y": {"low": val_low, "mid": val_mid, "high": val_high,
                  "pe_low": pe_low, "pe_mid": pe_mid, "pe_high": pe_high},
        "pe_5y": {"low": val_low_5, "mid": val_mid_5, "high": val_high_5},
        "pb": {"low": val_pb_low, "mid": val_pb_mid, "high": val_pb_high,
               "bvps": bvps, "pb_low": pb_low, "pb_mid": pb_mid, "pb_high": pb_high},
        "ev_ebitda": {"low": val_ev_low, "mid": val_ev_mid, "high": val_ev_high,
                      "ev_ebitda_low": ev_ebitda_low, "ev_ebitda_mid": ev_ebitda_mid,
                      "ev_ebitda_high": ev_ebitda_high},
        "recommended": {"low": val_low, "mid": val_mid, "high": val_high},
    }

REL = relative_valuation()
print(f"相对价值法: PE 8Y {REL['pe_8y']['pe_mid']}× = {REL['pe_8y']['mid']:.0f}元, "
      f"PB {REL['pb']['pb_mid']}× = {REL['pb']['mid']:.0f}元")

# ==================== 方法3: 并购价值法 ====================

def ma_valuation():
    """行业并购EV/EBITDA倍数——使用周期正常化EBITDA"""
    ev_mult_low, ev_mult_high = 6, 10
    net_debt = FIN[2025]["interest_debt"]
    ev_low = NORM_EBITDA * ev_mult_low
    ev_high = NORM_EBITDA * ev_mult_high
    eq_low = ev_low - net_debt
    eq_high = ev_high - net_debt
    price_low = eq_low / TOTAL_SHARES
    price_high = eq_high / TOTAL_SHARES

    # 股价不应低于收购价值的70%-75%
    floor_70 = price_low * 0.70
    floor_75 = price_high * 0.75

    return {
        "ev_low": ev_low, "ev_high": ev_high,
        "price_low": price_low, "price_high": price_high,
        "floor_70": floor_70, "floor_75": floor_75,
        "ev_mult_low": ev_mult_low, "ev_mult_high": ev_mult_high,
        "mid": (price_low + price_high) / 2,
    }

MA = ma_valuation()
print(f"并购价值法: {MA['ev_mult_low']}-{MA['ev_mult_high']}× EBITDA → "
      f"{MA['price_low']:.0f}-{MA['price_high']:.0f}元, 底价70%={MA['floor_70']:.0f}元")

# ==================== 方法4: LBO 估值 ====================

def lbo_valuation():
    """PE收购视角"""
    # 假设：杠杆5× EBITDA，持有5年，退出8× EBITDA，目标IRR 15-20%
    target_ebitda = NORM_EBITDA  # 2027E 基准，中周期
    entry_ev_multiples = [5.5, 6.5, 7.5]
    prices = []
    for mult in entry_ev_multiples:
        ev = target_ebitda * mult
        eq = ev - FIN[2025]["interest_debt"]
        prices.append(eq / TOTAL_SHARES)

    return {
        "low": prices[0], "mid": prices[1], "high": prices[2],
        "entry_multiples": entry_ev_multiples,
        "target_ebitda": target_ebitda,
    }

LBO = lbo_valuation()
print(f"LBO: {LBO['entry_multiples'][0]}-{LBO['entry_multiples'][2]}× EBITDA → "
      f"{LBO['low']:.0f}-{LBO['high']:.0f}元")

# ==================== 加权估值 ====================

def weighted_valuation():
    """四种方法加权汇总"""
    dcf_mid = DCF_BASE["value_per_share"]
    rel_mid = REL["recommended"]["mid"]
    ma_mid = MA["mid"]
    lbo_mid = LBO["mid"]

    # 取各方法的低/高
    dcf_low = DCF_BASE["value_per_share"] * 0.80
    dcf_high = DCF_BASE["value_per_share"] * 1.25
    rel_low = REL["recommended"]["low"]
    rel_high = REL["recommended"]["high"]
    ma_low = MA["price_low"]
    ma_high = MA["price_high"]
    lbo_low = LBO["low"]
    lbo_high = LBO["high"]

    weights = {"dcf": 0.20, "rel": 0.60, "ma": 0.10, "lbo": 0.10}

    w_low = dcf_low*weights["dcf"] + rel_low*weights["rel"] + ma_low*weights["ma"] + lbo_low*weights["lbo"]
    w_mid = dcf_mid*weights["dcf"] + rel_mid*weights["rel"] + ma_mid*weights["ma"] + lbo_mid*weights["lbo"]
    w_high = dcf_high*weights["dcf"] + rel_high*weights["rel"] + ma_high*weights["ma"] + lbo_high*weights["lbo"]

    # 安全边际 ±15%
    safety_margin = 0.15
    safe_low = w_mid * (1 - safety_margin)
    safe_high = w_mid * (1 + safety_margin)

    # 与当前价格对比
    premium = (CURRENT_PRICE - w_mid) / w_mid * 100

    return {
        "weights": weights,
        "components": {
            "DCF (20%)": (dcf_low, dcf_mid, dcf_high),
            "相对价值 (60%)": (rel_low, rel_mid, rel_high),
            "并购价值 (10%)": (ma_low, ma_mid, ma_high),
            "LBO (10%)": (lbo_low, lbo_mid, lbo_high),
        },
        "weighted": (w_low, w_mid, w_high),
        "safety": (safe_low, safe_high),
        "current_price": CURRENT_PRICE,
        "premium_pct": premium,
        "target_low": w_low, "target_mid": w_mid, "target_high": w_high,
    }

WV = weighted_valuation()
print(f"\n加权估值: {WV['target_low']:.0f} - {WV['target_mid']:.0f} - {WV['target_high']:.0f} 元")
print(f"安全边际(±15%): {WV['safety'][0]:.0f} - {WV['safety'][1]:.0f} 元")
print(f"当前 {CURRENT_PRICE} 元 vs 目标 {WV['target_mid']:.0f} 元 → {WV['premium_pct']:+.0f}%")

# ==================== 三种情景估值矩阵 ====================

def scenario_valuation():
    """将估值扩展到三种情景，展示猪价变化对目标价的影响"""
    results = {}
    for sc in ["下行", "基准", "上行"]:
        # DCF under this scenario
        dcf = dcf_valuation(scenario=sc)
        dcf_val = dcf["value_per_share"]

        # 相对PE：周期均值EPS不变（基于历史），但2027E EPS用于交叉参考
        eps_2027 = FORECAST[sc][2027]["eps"]
        fwd_pe_val = eps_2027 * REL["pe_8y"]["pe_mid"]  # 用目标PE中值

        # 并购和LBO不变（基于正常化EBITDA，不随情景变化）
        ma_val = MA["mid"]
        lbo_val = LBO["mid"]

        # 加权（DCF 20%, 相对周期PE 60%, M&A 10%, LBO 10%）
        rel_val = REL["recommended"]["mid"]  # 周期PE估值不变
        w = 0.20 * dcf_val + 0.60 * rel_val + 0.10 * ma_val + 0.10 * lbo_val

        results[sc] = {
            "dcf": dcf_val,
            "rel_cycle": rel_val,
            "eps_2027": eps_2027,
            "fwd_pe_val": fwd_pe_val,
            "ma": ma_val,
            "lbo": lbo_val,
            "weighted": w,
            "price_2027": PRICE_SCENARIOS[sc][2027],
            "price_2026": PRICE_SCENARIOS[sc][2026],
        }

    return results

SCENARIO_VAL = scenario_valuation()
for sc in ["下行", "基准", "上行"]:
    sv = SCENARIO_VAL[sc]
    print(f"{sc}情景 (猪价{sv['price_2027']}元/kg): "
          f"DCF={sv['dcf']:.0f} 加权={sv['weighted']:.0f} EPS_2027E={sv['eps_2027']:.2f}")

# ==================== 情景概率加权估值 ====================
# 基于期货曲线+产能周期判断，为三种情景分配概率权重
SCENARIO_PROBS = {"下行": 0.20, "基准": 0.50, "上行": 0.30}  # 期货偏基准偏上→上行权重略高于下行
prob_weighted_val = sum(SCENARIO_VAL[sc]["weighted"] * SCENARIO_PROBS[sc] for sc in ["下行", "基准", "上行"])
print(f"\n情景概率加权估值: 下行20%×{SCENARIO_VAL['下行']['weighted']:.0f} + "
      f"基准50%×{SCENARIO_VAL['基准']['weighted']:.0f} + 上行30%×{SCENARIO_VAL['上行']['weighted']:.0f} = {prob_weighted_val:.1f}元")

# ==================== 周期高峰估值 ====================
# 峰值PE的推导（三层交叉验证）：
#   第一层·历史实证：2020年ASF超级周期，峰值PE=15-19×（猪价34→39, EPS 5.33→股价100）
#   第二层·Hooke理论：市场在周期高峰压缩PE（盈利明显不可持续），典型区间10-16×
#   第三层·交叉验证：周期PE=19×, 周期EPS=2.04, 峰值EPS可能4-11元
#     → 若PE完全不压缩：19×11=209元（不可能，市场会识别不可持续性）
#     → 若PE适度压缩：14×7.5=105元（合理的高峰目标）
#     → 若PE大幅压缩：10×4.4=44元（保守，接近当前周期均值估值）
# 结论：峰值PE区间 10-16×，中枢14×

PEAK_PE_LOW, PEAK_PE_MID, PEAK_PE_HIGH = 10, 14, 16

def cycle_peak_valuation():
    """周期高峰估值矩阵：猪价→EPS→峰值股价"""
    # 猪价区间：从周期均值到超级周期，覆盖所有可能的高峰情景
    pig_prices = [13, 14, 15, 16, 17, 18, 20, 22, 24, 26, 28]
    results = {}
    for pp in pig_prices:
        fin = peak_year_financials(pp)
        fin["peak_price_low"]  = fin["eps"] * PEAK_PE_LOW   # 保守: PE大幅压缩
        fin["peak_price_mid"]  = fin["eps"] * PEAK_PE_MID   # 基准: 典型周期高峰PE
        fin["peak_price_high"] = fin["eps"] * PEAK_PE_HIGH  # 乐观: PE温和压缩
        # 按概率加权（温和高峰概率高，极端高峰概率低）
        if pp <= 16:
            fin["peak_weight"] = 0.30  # 温和高峰：较大概率
        elif pp <= 20:
            fin["peak_weight"] = 0.25  # 中等高峰
        elif pp <= 24:
            fin["peak_weight"] = 0.10  # 强周期
        else:
            fin["peak_weight"] = 0.03  # 极端/超级周期（低概率）
        results[pp] = fin
    return results

CYCLE_PEAK = cycle_peak_valuation()

# 历史高峰对照数据（用于图表标注和验证）
HISTORICAL_PEAKS = [
    {"year": "2016", "pig_price": 21.2, "eps": 2.25, "peak_stock": 14, "peak_pe": 6.2,
     "note": "小盘时期(市值<200亿)，参考价值低"},
    {"year": "2020", "pig_price": 39.2, "eps": 5.33, "peak_stock": 100, "peak_pe": 18.8,
     "note": "ASF超级周期，峰值PE≈19×"},
    {"year": "2022", "pig_price": 28.1, "eps": 2.49, "peak_stock": 63, "peak_pe": 25.3,
     "note": "小周期反弹(均价仅18.7)，非真正高峰"},
]

# ==================== 图表 ====================

STYLE_CONFIG = dict(
    template=PLOTLY_TEMPLATE,
    font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
    hovermode="x unified",
)

def ch1_dcf_fcf():
    """FCF 预测瀑布图"""
    projs = DCF_BASE["projections"]
    fig = go.Figure()

    years = [str(p["year"]) + "E" for p in projs]
    fcf_vals = [p["fcf"] for p in projs]
    ebit_vals = [p["ebit"] for p in projs]

    fig.add_trace(go.Bar(x=years, y=ebit_vals, name="EBIT",
                         marker_color=C["midblue"], opacity=0.7))
    fig.add_trace(go.Bar(x=years, y=fcf_vals, name="FCF",
                         marker_color=C["green"], opacity=0.85))

    for i, p in enumerate(projs):
        fig.add_annotation(x=years[i], y=p["ebit"] + 20,
                          text=f"FCF<br>{p['fcf']:.0f}亿", showarrow=False,
                          font=dict(size=10, color=C["dark"]))

    fig.update_yaxes(title="亿元")
    fig.update_layout(
        title=dict(text="DCF 自由现金流预测（2026E-2030E）", x=0.02, y=0.98,
                   font=dict(size=15, color="#1a1a1a")),
        height=400, bargap=0.35, **STYLE_CONFIG,
        legend=dict(orientation="h", yanchor="bottom", y=1.08),
        margin=dict(l=55, r=30, t=80, b=55),
    )
    return fig

def ch2_wacc_sensitivity():
    """WACC vs 永续增长率 → 每股价值"""
    wacc_range = np.arange(6.0, 10.5, 0.5)
    g_range = np.arange(1.5, 4.0, 0.25)

    z = []
    for w in wacc_range:
        row = []
        for g in g_range:
            result = dcf_valuation(wacc=w, terminal_g=g)
            row.append(round(result["value_per_share"], 1))
        z.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=[f"{g:.1f}%" for g in g_range],
        y=[f"{w:.1f}%" for w in wacc_range],
        colorscale=[
            [0.0, C["red"]],
            [0.3, "#f5b7b1"],
            [0.5, "#ffffff"],
            [0.7, "#a9dfbf"],
            [1.0, C["green"]],
        ],
        zmid=DCF_BASE["value_per_share"],
        text=[[f"{v:.0f}" for v in row] for row in z],
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title=dict(text="每股价值（元）", side="right")),
    ))

    # 标记基准点
    fig.add_scatter(x=[f"{TERMINAL_G:.1f}%"], y=[f"{WACC:.1f}%"],
                    mode="markers", marker=dict(color=C["dark"], size=12, symbol="x"),
                    name=f"基准 WACC={WACC:.1f}% g={TERMINAL_G:.1f}%")

    fig.update_yaxes(title="WACC")
    fig.update_xaxes(title="永续增长率")
    fig.update_layout(
        title=dict(text="DCF 敏感性：WACC × 永续增长率 → 每股价值",
                   x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=430, **STYLE_CONFIG,
        margin=dict(l=55, r=30, t=80, b=80),
    )
    return fig

def ch3_peer_comparison():
    """同行估值对比 — 使用周期PE（Hooke方法论）"""
    names = list(PEERS.keys())

    fig = make_subplots(rows=1, cols=3,
                        subplot_titles=("周期PE (8Y均值EPS)", "市净率 P/B", "EV/EBITDA (估算)"),
                        horizontal_spacing=0.12)

    # 周期PE（核心修正：使用周期均值EPS）
    pe_vals = []
    pe_texts = []
    for n in names:
        pc = PEERS[n].get("pe_cycle")
        if pc is not None and pc > 0 and pc < 200:
            pe_vals.append(pc)
            pe_texts.append(f"{pc:.1f}")
        else:
            pe_vals.append(0)
            pe_texts.append("N/A")
    colors_pe = [C["midblue"] if n == "牧原股份" else C["gray"] for n in names]
    fig.add_trace(go.Bar(x=names, y=pe_vals, name="周期PE", marker_color=colors_pe,
                         text=pe_texts, textposition="outside",
                         textfont=dict(size=10)), row=1, col=1)

    # PB
    pb_vals = [PEERS[n]["pb"] for n in names]
    colors_pb = [C["midblue"] if n == "牧原股份" else C["gray"] for n in names]
    fig.add_trace(go.Bar(x=names, y=pb_vals, name="PB", marker_color=colors_pb,
                         text=[f"{v:.2f}" for v in pb_vals], textposition="outside",
                         textfont=dict(size=10)), row=1, col=2)

    # EV/EBITDA（使用成本调整后的估算，clip极端值）
    ev_vals_raw = [PEERS[n]["ev_ebitda"] for n in names]
    ev_vals = [min(max(v, 0), 30) for v in ev_vals_raw]  # clip 0-30
    ev_texts = [f"{v:.1f}" for v in ev_vals_raw]
    colors_ev = [C["midblue"] if n == "牧原股份" else C["gray"] for n in names]
    fig.add_trace(go.Bar(x=names, y=ev_vals, name="EV/EBITDA", marker_color=colors_ev,
                         text=ev_texts, textposition="outside",
                         textfont=dict(size=10)), row=1, col=3)

    fig.update_yaxes(title="倍数", row=1, col=1)
    fig.update_yaxes(title="倍数", row=1, col=2)
    fig.update_yaxes(title="倍数", row=1, col=3)
    for i in [1, 2, 3]:
        fig.update_xaxes(tickangle=30, row=1, col=i)

    fig.update_layout(
        title=dict(text="同行估值倍数对比 — 基于周期均值EPS（牧原以深色标注）", x=0.02, y=0.98,
                   font=dict(size=15, color="#1a1a1a")),
        height=420, showlegend=False, **STYLE_CONFIG,
        margin=dict(l=55, r=30, t=100, b=80),
    )
    return fig

def ch4_pe_band():
    """PE Band — 整数年份X轴，PE倍数Y轴，估值带+走势+当前PE"""
    hist_yrs = sorted(HIST_PE.keys())  # [2018, ..., 2025]
    yr_labels = [str(yr) for yr in hist_yrs]

    # 收集实际PE数据 — 用整数年份做X，None做缺值断开
    yr_int = list(hist_yrs)
    actual_pe, has_data = [], []
    for yr in hist_yrs:
        hp = HIST_PE[yr]
        if hp["is_loss"] or hp["pe"] is None:
            actual_pe.append(None)
            has_data.append(False)
        else:
            actual_pe.append(max(0.5, min(hp["pe"], 80)))
            has_data.append(True)

    # 构建有数据的子集（用于填充区域，避免None断fill）
    x_valid = [yr for yr, ok in zip(hist_yrs, has_data) if ok]
    y_valid = [pe for pe, ok in zip(actual_pe, has_data) if ok]

    pe_low_hist, pe_mid_hist, pe_high_hist = 8, 15, 30

    fig = go.Figure()

    # === 估值带背景（rect shapes跨全X轴范围） ===
    x_left, x_right = hist_yrs[0] - 0.5, hist_yrs[-1] + 0.5
    zone_configs = [
        (0, pe_low_hist, "rgba(39,174,96,0.10)"),
        (pe_low_hist, pe_mid_hist, "rgba(52,152,219,0.06)"),
        (pe_mid_hist, pe_high_hist, "rgba(230,126,34,0.06)"),
        (pe_high_hist, 55, "rgba(192,57,43,0.07)"),
    ]
    for y0, y1, color in zone_configs:
        fig.add_shape(type="rect", x0=x_left, x1=x_right, y0=y0, y1=y1,
                      fillcolor=color, line_width=0, layer="below")

    # === PE Band水平参考线 ===
    for pe_val, color, label in [
        (pe_low_hist, C["green"], f"低估线 {pe_low_hist}×"),
        (pe_mid_hist, C["orange"], f"合理线 {pe_mid_hist}×"),
        (pe_high_hist, C["red"], f"高估线 {pe_high_hist}×"),
    ]:
        fig.add_shape(type="line", x0=x_left, x1=x_right,
                      y0=pe_val, y1=pe_val,
                      line=dict(color=color, width=1.5, dash="dash"), opacity=0.55)
        fig.add_annotation(x=hist_yrs[0], y=pe_val + 0.8, text=label,
                          showarrow=False, font=dict(size=9, color=color), xanchor="left")

    # === 实际PE走势（只有有数据的点连线，2023自动断开） ===
    hover_texts = []
    for yr, pe, ok in zip(hist_yrs, actual_pe, has_data):
        if ok:
            hover_texts.append(f"{yr}年<br>年末PE(TTM) = {pe:.1f}×<br>EPS = {FIN[yr]['eps']:.2f}元")
        else:
            hover_texts.append(f"{yr}年<br>全年亏损 · PE无意义")

    fig.add_trace(go.Scatter(
        x=hist_yrs, y=actual_pe, mode="lines+markers",
        line=dict(color=C["midblue"], width=2.8),
        marker=dict(size=11, color=C["midblue"], line=dict(color="white", width=2)),
        name="年末PE(TTM)",
        text=hover_texts, hoverinfo="text",
        connectgaps=False,
    ))

    # === PE走势下方浅色填充（仅有效数据段，与主线同步断） ===
    fig.add_trace(go.Scatter(
        x=hist_yrs, y=actual_pe, mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=0),
        fill="tozeroy", fillcolor="rgba(41,128,185,0.07)",
        showlegend=False, connectgaps=False,
    ))

    # === 亏损年份标注 ===
    for yr in hist_yrs:
        if yr in HIST_PE and HIST_PE[yr]["is_loss"]:
            fig.add_annotation(x=yr, y=2, text="<b>亏损</b>",
                              showarrow=True, arrowhead=2, arrowsize=1,
                              arrowcolor=C["red"], font=dict(size=10, color=C["red"]), ay=-30)

    # === 当前周期PE ===
    fig.add_shape(type="line", x0=x_left, x1=x_right,
                  y0=CURRENT_PE_CYCLE, y1=CURRENT_PE_CYCLE,
                  line=dict(color=C["dark"], width=2, dash="solid"), opacity=0.6)
    fig.add_annotation(x=hist_yrs[-1], y=CURRENT_PE_CYCLE + 1.4,
                      text=f"← 当前周期PE {CURRENT_PE_CYCLE:.1f}×",
                      showarrow=False, font=dict(size=11, color=C["dark"]), xanchor="right")

    # === 同行PE参考 ===
    for pname in ["温氏股份", "神农集团"]:
        if pname in PEERS and PEERS[pname].get("pe_cycle") and PEERS[pname]["pe_cycle"] < 100:
            pe_val = PEERS[pname]["pe_cycle"]
            fig.add_shape(type="line", x0=x_left, x1=x_right,
                          y0=pe_val, y1=pe_val,
                          line=dict(color=C["gray"], width=0.8, dash="dot"), opacity=0.4)
            fig.add_annotation(x=hist_yrs[-1], y=pe_val + 0.5,
                              text=f"{pname[:2]} {pe_val:.1f}×",
                              showarrow=False, font=dict(size=8, color=C["gray"]), xanchor="right")

    # === 坐标轴：数值X轴 + 自定义刻度标签 ===
    fig.update_xaxes(
        tickmode="array",
        tickvals=hist_yrs,
        ticktext=yr_labels,
        tickfont=dict(size=11, color="#333"),
        range=[hist_yrs[0] - 0.5, hist_yrs[-1] + 0.5],
        showgrid=True, gridcolor="#f0f0f0",
        showline=True, linecolor="#ccc", linewidth=1,
        zeroline=False,
    )
    fig.update_yaxes(
        title=dict(text="PE 估值倍数（倍）", font=dict(size=12, color="#555")),
        range=[0, 50], dtick=5,
        tickfont=dict(size=11),
        showgrid=True, gridcolor="#f0f0f0",
        showline=True, linecolor="#ccc", linewidth=1,
        zeroline=True, zerolinecolor="#ddd",
    )
    # 不在 layout 用 **STYLE_CONFIG，手动控制避免模板覆盖 xaxis/yaxis
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
        title=dict(text="PE Band 历史走势 — 年末PE(TTM)与估值带（2018-2025）",
                   x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.08),
        margin=dict(l=55, r=35, t=80, b=60),
        hovermode="x unified",
    )
    return fig

def ch4b_price_pb_trend():
    """股价走势与PB双轴图 — 季度粒度（优先使用真实日线，回退至年度插值）

    PB（市净率）比 PE 更适合与股价放在一起分析周期股：
    - BPS 始终为正，不会像 EPS 那样趋近零导致估值倍数爆炸
    - PB 与股价天然正相关，两条线走势协调
    - Graham & Dodd 推荐对周期股使用 PB 作为辅助估值锚
    """
    import urllib.request, json, ssl, os

    # ── 1. 尝试从本地缓存加载日线数据 ──
    daily_csv = ROOT / "data" / "牧原_日线股价.csv"
    df_daily = None

    # 1a. 本地已有缓存 → 直接用
    if daily_csv.exists():
        df_daily = pd.read_csv(daily_csv)
        df_daily["date"] = pd.to_datetime(df_daily["date"])

    # 1b. 无缓存 → 尝试在线拉取
    if df_daily is None:
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
            url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
                   "?secid=0.002714&fields1=f1,f2,f3,f4,f5,f6"
                   "&fields2=f51,f52,f53,f54,f55,f56"
                   "&klt=101&fqt=1&beg=20170101&end=20260804&lmt=3000")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                klines = data["data"]["klines"]
                records = []
                for k in klines:
                    p = k.split(",")
                    records.append({"date": p[0], "open": float(p[1]), "close": float(p[2]),
                                    "high": float(p[3]), "low": float(p[4])})
                df_daily = pd.DataFrame(records)
                df_daily["date"] = pd.to_datetime(df_daily["date"])
                # 写入缓存
                os.makedirs(daily_csv.parent, exist_ok=True)
                df_daily.to_csv(daily_csv, index=False, columns=["date","open","close","high","low"])
                print(f"  📡 在线拉取日线成功: {len(df_daily)} 条 → 已缓存")
        except Exception as e:
            print(f"  ⚠ 无法获取日线数据({e})，回退至年度插值模式")

    # ── 2. 构建季度数据 ──
    # 2a. 从季度财报加载 BPS（每股净资产）—— 比 TTM EPS 稳定得多
    df_qf = pd.read_csv(ROOT / "data" / "主要财务指标_按单季度.csv", dtype=str)
    df_qf["REPORT_DATE"] = pd.to_datetime(df_qf["REPORT_DATE"])
    df_qf["BPS"] = pd.to_numeric(df_qf["BPS"], errors="coerce")
    df_qf = df_qf.sort_values("REPORT_DATE")
    df_qf["quarter"] = df_qf["REPORT_DATE"].dt.to_period("Q")

    # 2b. 季度价格
    if df_daily is not None:
        # 有真实日线：按季度聚合
        df_daily["quarter"] = df_daily["date"].dt.to_period("Q")
        qtr_price = df_daily.groupby("quarter").agg(
            close=("close", "last"), high=("high", "max"), low=("low", "min")
        ).reset_index()
        # Merge with BPS
        qtr = qtr_price.merge(df_qf[["quarter", "BPS"]], on="quarter", how="left")
    else:
        # 回退：从年度高低点估算季度收盘价（年中值近似）
        qtr_list = []
        for yr, (sh, sl) in sorted(STOCK_ANNUAL_RANGE.items()):
            mid = (sh + sl) / 2
            for q in range(1, 5):
                q_str = f"{yr}Q{q}"
                q_period = pd.Period(q_str, freq="Q")
                qtr_list.append({"quarter": q_period, "close": mid, "high": sh, "low": sl})
        qtr = pd.DataFrame(qtr_list)
        qtr = qtr.merge(df_qf[["quarter", "BPS"]], on="quarter", how="left")

    # 过滤：从2018Q1开始，且至少要有BPS
    qtr = qtr[(qtr["quarter"] >= pd.Period("2018Q1", "Q")) & qtr["BPS"].notna()].reset_index(drop=True)

    # 2c. 计算季度 PB
    qtr["pb"] = qtr["close"] / qtr["BPS"]
    qtr["quarter_label"] = qtr["quarter"].astype(str)

    # ── 3. 当前实时数据点 ──
    latest_bps = qtr["BPS"].iloc[-1] if len(qtr) > 0 else None
    current_pb_real = CURRENT_PRICE / latest_bps if latest_bps and latest_bps > 0 else None

    # ── 4. 绘图 ──
    q_labels = qtr["quarter_label"].tolist()
    close_vals = qtr["close"].tolist()
    high_vals = qtr["high"].tolist()
    low_vals = qtr["low"].tolist()
    pb_raw = qtr["pb"].tolist()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 股价区间带
    fig.add_trace(go.Scatter(
        x=list(range(len(qtr))) + list(range(len(qtr)-1, -1, -1)),
        y=high_vals + low_vals[::-1],
        fill="toself", fillcolor="rgba(41,128,185,0.10)",
        line=dict(color="rgba(255,255,255,0)", width=0),
        name="季度股价区间", hoverinfo="skip",
    ), secondary_y=False)

    # 季度收盘价线
    hover_price = [f"{q_labels[i]}<br>收盘: {close_vals[i]:.1f}元<br>最高: {high_vals[i]:.1f}元 / 最低: {low_vals[i]:.1f}元"
                   for i in range(len(qtr))]
    fig.add_trace(go.Scatter(
        x=list(range(len(qtr))), y=close_vals, mode="lines+markers",
        line=dict(color=C["midblue"], width=2.2),
        marker=dict(size=6, color=C["midblue"], line=dict(color="white", width=1.5)),
        name="季度收盘价", text=hover_price, hoverinfo="text",
    ), secondary_y=False)

    # 当前股价水平线
    x_l, x_r = -0.5, len(qtr) - 0.5
    fig.add_shape(type="line", x0=x_l, x1=x_r, y0=CURRENT_PRICE, y1=CURRENT_PRICE,
                  line=dict(color=C["midblue"], width=1.5, dash="dot"), opacity=0.45)
    fig.add_annotation(x=len(qtr)-1, y=CURRENT_PRICE + 3,
                       text=f"当前 {CURRENT_PRICE}元",
                       showarrow=False, font=dict(size=10, color=C["midblue"]), xanchor="right")

    # PB 折线（右轴）—— 完整连续，不需要断开
    hover_pb = []
    for i in range(len(qtr)):
        hover_pb.append(f"{q_labels[i]}<br>PB = {pb_raw[i]:.2f}×<br>收盘 = {close_vals[i]:.1f}元<br>BPS = {qtr['BPS'].iloc[i]:.2f}元")
    fig.add_trace(go.Scatter(
        x=list(range(len(qtr))), y=pb_raw, mode="lines+markers",
        line=dict(color=C["red"], width=2.2),
        marker=dict(size=6, color=C["red"], line=dict(color="white", width=1.5)),
        name="季度末PB（市净率）", text=hover_pb, hoverinfo="text",
        connectgaps=True,
    ), secondary_y=True)

    # 当前PB标注
    if current_pb_real:
        fig.add_shape(type="line", x0=x_l, x1=x_r,
                      y0=current_pb_real, y1=current_pb_real,
                      line=dict(color=C["red"], width=1.5, dash="dot"), opacity=0.45)
        fig.add_annotation(x=len(qtr)-1, y=current_pb_real + (max(pb_raw) * 0.05),
                           text=f"当前PB {current_pb_real:.2f}×",
                           showarrow=False, font=dict(size=10, color=C["red"]), xanchor="right")

    # X轴: 每4个季度标一个年份
    tick_indices, tick_labels = [], []
    for i, lbl in enumerate(q_labels):
        if lbl.endswith("Q1") or i == len(q_labels)-1:
            tick_indices.append(i)
            tick_labels.append(lbl)
    fig.update_xaxes(
        tickmode="array", tickvals=tick_indices, ticktext=tick_labels,
        tickfont=dict(size=10, color="#333"),
        range=[x_l, x_r + 0.5],
        showgrid=True, gridcolor="#f0f0f0",
    )

    # PB 区间上下界（留白 10%）
    pb_ceil = max(pb_raw) * 1.10
    pb_floor = 0

    fig.update_yaxes(
        title=dict(text="股价（元）", font=dict(size=12, color=C["midblue"])),
        range=[0, max(high_vals) * 1.15],
        tickfont=dict(size=11, color=C["midblue"]),
        showgrid=True, gridcolor="#f0f0f0",
        secondary_y=False,
    )
    fig.update_yaxes(
        title=dict(text="PB 市净率（倍）", font=dict(size=12, color=C["red"])),
        range=[pb_floor, pb_ceil],
        tickfont=dict(size=11, color=C["red"]),
        secondary_y=True,
    )
    mode_note = "（日线聚合）" if df_daily is not None else "（年度高低点插值，季度BPS来自财报）"
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
        title=dict(text=f"股价走势与PB估值 — 季度粒度（2018Q1-{q_labels[-1]}）{mode_note}",
                   x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.08, font=dict(size=11)),
        margin=dict(l=55, r=55, t=80, b=70),
        hovermode="x unified",
    )
    return fig

def ch5_valuation_bridge():
    """四种方法 → 加权目标"""
    comps = WV["components"]
    methods = list(comps.keys())

    fig = go.Figure()

    for i, method in enumerate(methods):
        low, mid, high = comps[method]
        fig.add_trace(go.Bar(
            x=[method], y=[mid], name=method,
            marker_color=[C["midblue"], C["green"], C["orange"], C["purple"]][i],
            error_y=dict(type="data", symmetric=False,
                        array=[high - mid], arrayminus=[mid - low],
                        color=C["gray"], thickness=1.5, width=10),
            text=[f"{mid:.0f}元"], textposition="outside", textfont=dict(size=12),
        ))

    # 加权结果
    w_low, w_mid, w_high = WV["weighted"]
    fig.add_trace(go.Bar(
        x=["加权目标"], y=[w_mid],
        marker_color=C["dark"],
        error_y=dict(type="data", symmetric=False,
                    array=[w_high - w_mid], arrayminus=[w_mid - w_low],
                    color=C["dark"], thickness=2, width=12),
        text=[f"{w_mid:.0f}元"], textposition="outside", textfont=dict(size=14),
    ))

    # 当前股价参考线
    fig.add_hline(y=CURRENT_PRICE, line_dash="dash", line_color=C["red"], opacity=0.6,
                  annotation=dict(text=f"当前 {CURRENT_PRICE}元 {WV['premium_pct']:+.0f}%",
                                  font=dict(size=11, color=C["red"])))

    fig.update_yaxes(title="每股价值（元）")
    fig.update_layout(
        title=dict(text="估值汇总：四种方法 → 加权目标价",
                   x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=440, **STYLE_CONFIG,
        margin=dict(l=55, r=30, t=80, b=55),
    )
    return fig

def ch6_safety_margin():
    """安全边际可视化"""
    w_low, w_mid, w_high = WV["weighted"]
    safe_low, safe_high = WV["safety"]

    fig = go.Figure()

    # 估值区间
    fig.add_trace(go.Bar(
        x=["估值区间"], y=[w_high - w_low],
        base=w_low, width=0.4,
        marker=dict(color=C["midblue"], opacity=0.3),
        name="估值范围",
    ))
    fig.add_trace(go.Bar(
        x=["估值区间"], y=[safe_high - safe_low],
        base=safe_low, width=0.3,
        marker=dict(color=C["green"], opacity=0.5),
        name=f"安全边际 ±15%",
    ))

    # 中点和当前
    fig.add_hline(y=w_mid, line_color=C["midblue"], line_width=2,
                  annotation=dict(text=f"目标 {w_mid:.0f}元", font=dict(size=11, color=C["midblue"])))
    fig.add_hline(y=CURRENT_PRICE, line_color=C["red"], line_width=2, line_dash="dash",
                  annotation=dict(text=f"当前 {CURRENT_PRICE}元 (+{WV['premium_pct']:.0f}%)",
                                  font=dict(size=11, color=C["red"])))

    fig.add_hline(y=safe_low, line_color=C["green"], line_width=1, line_dash="dot")
    fig.add_hline(y=safe_high, line_color=C["green"], line_width=1, line_dash="dot")

    fig.update_yaxes(title="每股价值（元）", range=[max(0, w_low - 10), max(w_high, CURRENT_PRICE) + 8])
    fig.update_layout(
        title=dict(text="安全边际分析", x=0.02, y=0.98,
                   font=dict(size=15, color="#1a1a1a")),
        height=400, **STYLE_CONFIG,
        legend=dict(orientation="h", yanchor="bottom", y=1.08),
        margin=dict(l=55, r=30, t=80, b=55),
    )
    return fig

def ch7_summary_table():
    """估值汇总表"""
    header = ["估值方法", "权重", "低估", "合理", "高估", "核心参数"]
    rows = [
        ["DCF 内在价值", "20%",
         f"{DCF_BASE['value_per_share']*0.80:.0f}",
         f"{DCF_BASE['value_per_share']:.0f}",
         f"{DCF_BASE['value_per_share']*1.25:.0f}",
         f"WACC={WACC:.1f}% g={TERMINAL_G:.1f}%"],
        ["相对价值 (PE)", "60%",
         f"{REL['pe_8y']['low']:.0f}",
         f"{REL['pe_8y']['mid']:.0f}",
         f"{REL['pe_8y']['high']:.0f}",
         f"周期EPS {AVG8_EPS:.2f} × PE {REL['pe_8y']['pe_low']}-{REL['pe_8y']['pe_high']}×"],
        ["并购价值", "10%",
         f"{MA['price_low']:.0f}", f"{MA['mid']:.0f}", f"{MA['price_high']:.0f}",
         f"EV/EBITDA {MA['ev_mult_low']}-{MA['ev_mult_high']}×"],
        ["LBO", "10%",
         f"{LBO['low']:.0f}", f"{LBO['mid']:.0f}", f"{LBO['high']:.0f}",
         f"Entry {LBO['entry_multiples'][0]}-{LBO['entry_multiples'][2]}× EBITDA"],
        ["加权结果", "100%",
         f"{WV['target_low']:.0f}", f"{WV['target_mid']:.0f}", f"{WV['target_high']:.0f}",
         f"安全边际 ±15%: {WV['safety'][0]:.0f}-{WV['safety'][1]:.0f}元"],
    ]

    colors_row = [C["gray"], C["midblue"], C["orange"], C["purple"], C["dark"]]

    fig = go.Figure(data=[go.Table(
        header=dict(values=["<b>" + h + "</b>" for h in header],
                    fill_color=C["dark"], font=dict(color="white", size=12),
                    align="center", height=34),
        cells=dict(values=list(zip(*rows)),
                   fill_color=[["white", "#f8f9fa", "#f8f9fa", "#f8f9fa", "#f0f4f8"]],
                   font=dict(size=11, color="#1a1a1a"), align="center", height=30),
    )])

    fig.update_layout(
        title=dict(text="估值汇总表", x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=280, margin=dict(l=30, r=30, t=80, b=30),
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", size=12, color="#1a1a1a"),
    )
    return fig

def ch8_cycle_peak():
    """周期高峰情景：猪价→峰值股价映射"""
    pig_prices = list(CYCLE_PEAK.keys())

    fig = go.Figure()

    # 填充PE压缩区间（10-16×之间）
    price_10x = [CYCLE_PEAK[pp]["peak_price_low"] for pp in pig_prices]
    price_16x = [CYCLE_PEAK[pp]["peak_price_high"] for pp in pig_prices]
    price_14x = [CYCLE_PEAK[pp]["peak_price_mid"] for pp in pig_prices]

    fig.add_trace(go.Scatter(
        x=pig_prices + pig_prices[::-1],
        y=price_16x + price_10x[::-1],
        fill="toself", fillcolor="rgba(52,152,219,0.10)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=True,
        name=f"峰值PE {PEAK_PE_LOW}-{PEAK_PE_HIGH}× (合理区间)",
    ))

    # 三条PE线
    fig.add_trace(go.Scatter(
        x=pig_prices, y=price_10x, mode="lines+markers",
        line=dict(color=C["green"], width=1.5, dash="dot"),
        marker=dict(size=3), name=f"保守: PE {PEAK_PE_LOW}×",
    ))
    fig.add_trace(go.Scatter(
        x=pig_prices, y=price_14x, mode="lines+markers",
        line=dict(color=C["midblue"], width=2.5),
        marker=dict(size=5), name=f"基准: PE {PEAK_PE_MID}×",
    ))
    fig.add_trace(go.Scatter(
        x=pig_prices, y=price_16x, mode="lines+markers",
        line=dict(color=C["red"], width=1.5, dash="dot"),
        marker=dict(size=3), name=f"乐观: PE {PEAK_PE_HIGH}×",
    ))

    # === 历史高峰归一化参考点 ===
    # 问题：原始历史星星（2020:猪价39/股价100, 2022:猪价28/股价63）不能直接放到此图上
    # 原因：模型曲线基于当前规模(8600万头)和成本(11.0元)，历史数据基于当年不同的基本面
    # 解决：用模型归一化——"若今日牧原经历当年的猪价水平，按历史峰值PE，股价会是多少"
    for hp in HISTORICAL_PEAKS:
        if hp["year"] == "2020":
            # 2020年猪价39.2远超X轴(13-28)，改用模型在猪价22元处的EPS估算
            # 2020年历史峰值PE=18.8× → 若今日牧原猪价22元 EPS=17.11 → 17.11×18.8=322
            # 但322远高于图表合理范围，不标注具体点位，改为下方文字说明
            pass
        elif hp["year"] == "2022":
            # 2022年猪价28.1在X轴边缘，用模型EPS=26.67×历史PE=25.3=675（同样过高）
            pass

    # 替代方案：标注模型自身的"关键里程碑"——猪价到多少能破100？回到历史前高？
    # 反推：股价=EPS×PE → 100元需要 EPS=100/14=7.14 或 100/10=10.0
    # 从FORECAST：猪价~15.5元→EPS≈6.4, 猪价~16.5元→EPS≈8.5
    # 猪价~15.8元/kg × PE14× → ~100元

    # 当前价格参考线
    fig.add_hline(y=CURRENT_PRICE, line_dash="dash", line_color=C["gray"], opacity=0.5,
                  annotation=dict(text=f"当前 {CURRENT_PRICE}元",
                                  font=dict(size=10, color=C["gray"])))

    # 周期均值估值参考线
    cycle_target = WV["target_mid"] if 'WV' in dir() else 38
    fig.add_hline(y=cycle_target, line_dash="dot", line_color=C["green"], opacity=0.4,
                  annotation=dict(text=f"周期均值估值 {cycle_target:.0f}元",
                                  font=dict(size=10, color=C["green"])))

    # 历史前高100元参考线（附注：需猪价≈16元/kg × PE14× 或 猪价≈20元/kg × PE10×）
    fig.add_hline(y=100, line_dash="dash", line_color=C["orange"], opacity=0.4,
                  annotation=dict(text="前高~100元 (2020)",
                                  font=dict(size=10, color=C["orange"])))

    # 添加文字注释框：历史不可比性说明
    fig.add_annotation(
        x=0.02, y=0.95, xref="paper", yref="paper",
        text=("<b>⚠️ 历史对照说明</b><br>"
              "2020年股价100元时：出栏1812万头/成本14.0元<br>"
              "2027年模型：出栏8600万头/成本11.0元<br>"
              "——规模×4.7、成本降3元，同猪价下EPS远高于历史<br>"
              "因此历史高点(100元)在今日仅需<b>猪价~16元+PE14×</b>即可触及"),
        showarrow=False,
        font=dict(size=9, color="#666"),
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor=C["orange"],
        borderwidth=1,
        borderpad=6,
        align="left",
    )

    fig.update_xaxes(title="峰值年猪价（元/kg）——基于当前规模(8600万头)和成本(11.0元/kg)",
                     tickvals=pig_prices, range=[pig_prices[0] - 0.5, pig_prices[-1] + 0.5])
    fig.update_yaxes(title="隐含峰值股价（元）")
    fig.update_layout(
        title=dict(text="周期高峰情景：猪价 → 峰值EPS → 峰值股价（按不同PE压缩程度）",
                   x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=480, **STYLE_CONFIG,
        legend=dict(orientation="h", yanchor="bottom", y=1.08),
        margin=dict(l=55, r=30, t=80, b=65),
    )
    return fig

def ch9_futures_curve():
    """生猪期货远期曲线 vs 模型猪价假设"""
    if not FUTURES_CURVE:
        fig = go.Figure()
        fig.update_layout(title=dict(text="生猪期货数据缺失", x=0.02, y=0.98))
        return fig

    months = sorted(FUTURES_CURVE.keys())
    prices = [FUTURES_CURVE[m]["price"] for m in months]
    volumes = [FUTURES_CURVE[m]["volume"] for m in months]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 期货价格曲线
    month_labels = [m[5:7] + "月" for m in months]  # "2026-09" → "09月"
    hover_labels = [f"{m}<br>期货: {p:.2f}元/kg<br>持仓: {v:,.0f}" for m, p, v in zip(months, prices, volumes)]

    fig.add_trace(go.Scatter(
        x=months, y=prices, mode="lines+markers",
        line=dict(color=C["red"], width=2.5),
        marker=dict(size=8, color=C["red"], symbol="diamond",
                   line=dict(color="white", width=1)),
        name="生猪期货远期曲线",
        text=hover_labels, hoverinfo="text",
    ), secondary_y=False)

    # 模型情景参考区间
    # 基准2026=10.5, 基准2027=12.5, 上行2027=14.0
    # 用水平虚线表示模型年度均价
    base_2026 = PRICE_SCENARIOS["基准"][2026]
    base_2027 = PRICE_SCENARIOS["基准"][2027]
    up_2027 = PRICE_SCENARIOS["上行"][2027]
    down_2027 = PRICE_SCENARIOS["下行"][2027]

    # 2026年基准参考
    fig.add_hline(y=base_2026, line_dash="dot", line_color=C["gray"], opacity=0.5,
                  annotation=dict(text=f"模型基准2026={base_2026}",
                                  font=dict(size=9, color=C["gray"])))

    # 2027年三条情景线
    for price_val, label, color in [
        (down_2027, f"下行情景2027={down_2027}", C["green"]),
        (base_2027, f"基准情景2027={base_2027}", C["midblue"]),
        (up_2027, f"上行情景2027={up_2027}", C["orange"]),
    ]:
        fig.add_hline(y=price_val, line_dash="dash", line_color=color, opacity=0.4,
                      annotation=dict(text=label, font=dict(size=9, color=color)))

    # 持仓量（柱状图，右轴）
    fig.add_trace(go.Bar(
        x=months, y=volumes, name="持仓量",
        marker_color="rgba(127,140,141,0.25)",
        marker_line=dict(color="rgba(127,140,141,0.5)", width=0.5),
        width=0.5,
    ), secondary_y=True)

    # 当前现货参考（2026Q3均价≈10.7）
    fig.add_hline(y=10.7, line_dash="solid", line_color=C["dark"], opacity=0.4,
                  annotation=dict(text="当前现货~10.7元 (2026Q3至今)",
                                  font=dict(size=9, color=C["dark"])))

    fig.update_xaxes(title="交割月份", tickangle=30)
    fig.update_yaxes(title="期货价格（元/kg）", secondary_y=False,
                     range=[max(0, min(prices) - 1.5), max(prices) + 1.5])
    fig.update_yaxes(title="持仓量", secondary_y=True, showgrid=False)

    fig.update_layout(
        title=dict(text="生猪期货远期曲线 vs 模型猪价假设（2026-07-28收盘）",
                   x=0.02, y=0.98, font=dict(size=15, color="#1a1a1a")),
        height=420, **STYLE_CONFIG,
        legend=dict(orientation="h", yanchor="bottom", y=1.12),
        margin=dict(l=55, r=55, t=80, b=65),
    )
    return fig

def ch10_trough_pe():
    """历史低谷周期PE演化——验证模型PE下限"""
    years = sorted(TROUGH_DATA.keys())
    pe_vals = [min(TROUGH_DATA[yr]["pe_cycle_low"], 60) for yr in years]  # clip异常值
    pb_vals = [TROUGH_DATA[yr]["pb_low"] for yr in years]
    yrs_str = [str(yr) for yr in years]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 低谷周期PE柱状图
    colors = [C["red"] if yr in [2018] else (C["midblue"] if yr >= 2019 else C["gray"]) for yr in years]
    fig.add_trace(go.Bar(
        x=yrs_str, y=pe_vals, name="股价最低点÷周期EPS",
        marker_color=colors, width=0.55,
        text=[f"{v:.1f}×" for v in pe_vals], textposition="outside",
        textfont=dict(size=10),
    ), secondary_y=False)

    # 当前模型PE区间
    fig.add_hline(y=15, line_dash="dot", line_color=C["green"], opacity=0.5,
                  annotation=dict(text="模型PE下限 15×", font=dict(size=9, color=C["green"])))
    fig.add_hline(y=22, line_dash="dot", line_color=C["orange"], opacity=0.5,
                  annotation=dict(text="模型PE上限 22×", font=dict(size=9, color=C["orange"])))

    # 2021后低谷PE均值参考线（排除2019-2020过渡期）
    post_2020_vals = [v for yr, v in zip(years, pe_vals) if yr >= 2021]
    post_2020_avg = sum(post_2020_vals) / len(post_2020_vals) if post_2020_vals else 20
    fig.add_hline(y=post_2020_avg, line_dash="dash", line_color=C["midblue"], opacity=0.35,
                  annotation=dict(text=f"2021后低谷均值 {post_2020_avg:.1f}×",
                                  font=dict(size=9, color=C["midblue"])))

    # 分隔线标注2019/2020分界（非瘟前后）
    fig.add_vline(x=3.5, line_width=1, line_color="#999", line_dash="dot", opacity=0.5)
    fig.add_annotation(x=2, y=max(pe_vals)*0.95, text="非瘟前", showarrow=False,
                       font=dict(size=9, color="#999"))
    fig.add_annotation(x=6, y=max(pe_vals)*0.95, text="龙头溢价确立 (2021+)", showarrow=False,
                       font=dict(size=9, color=C["midblue"]))

    # P/B线（右轴）
    fig.add_trace(go.Scatter(
        x=yrs_str, y=pb_vals, mode="lines+markers",
        line=dict(color=C["orange"], width=1.5, dash="dot"),
        marker=dict(size=5, color=C["orange"]),
        name="低谷P/B (右轴)",
    ), secondary_y=True)

    fig.update_yaxes(title="低谷周期PE（倍）", secondary_y=False,
                     range=[0, max(pe_vals) * 1.2])
    fig.update_yaxes(title="低谷P/B（倍）", secondary_y=True,
                     range=[0, max(pb_vals) * 1.3], showgrid=False)

    fig.update_layout(
        title=dict(text="历史低谷验证：每年股价最低点 ÷ 当时滚动8Y周期EPS",
                   x=0.02, y=0.98, font=dict(size=14, color="#1a1a1a")),
        height=400, **STYLE_CONFIG,
        legend=dict(orientation="h", yanchor="bottom", y=1.08),
        margin=dict(l=55, r=55, t=80, b=55),
        bargap=0.3,
    )
    return fig

# ==================== HTML 构建 ====================

def build_dcf_detail():
    projs = DCF_BASE["projections"]
    rows = ""
    for p in projs:
        rows += (f"<tr><td>{p['year']}E</td>"
                 f"<td>{p['revenue']:,.0f}</td><td>{p['ebit']:,.0f}</td>"
                 f"<td>{p['da']:,.0f}</td><td>{p['capex']:,.0f}</td>"
                 f"<td>{p['delta_wc']:,.0f}</td>"
                 f"<td style='font-weight:600'>{p['fcf']:,.0f}</td></tr>")

    return f"""<table>
      <thead><tr><th>年份</th><th>营收(亿)</th><th>EBIT(亿)</th><th>D&A(亿)</th><th>Capex(亿)</th><th>ΔWC(亿)</th><th>FCF(亿)</th></tr></thead>
      <tbody>{rows}</tbody></table>
      <p style="margin-top:8px">终值构成：永续增长法 <b>{DCF_BASE['tv_perpetuity']:,.0f} 亿</b> (50%)
      + 退出乘数法 <b>{DCF_BASE['tv_exit']:,.0f} 亿</b> (50%)
      = 终值 <b>{DCF_BASE['terminal_value']:,.0f} 亿</b></p>
      <p><b>DCF估值结果：</b>企业价值 <b>{DCF_BASE['enterprise_value']:,.0f} 亿</b>
      − 有息负债 <b>{FIN[2025]['interest_debt']:,.0f} 亿</b>
      = 股权价值 <b>{DCF_BASE['equity_value']:,.0f} 亿</b>
      ÷ {TOTAL_SHARES} 亿股 = <b>{DCF_BASE['value_per_share']:.1f} 元/股</b></p>"""

def build_peer_detail():
    rows = ""
    for name in ["牧原股份", "温氏股份", "新希望", "正邦科技", "神农集团"]:
        p = PEERS[name]
        rank = next((i+1 for i, (n, _) in enumerate(PEER_RANKING) if n == name), "-")
        cycle_pe_str = f"{p.get('pe_cycle', 0):.1f}" if p.get('pe_cycle') and p['pe_cycle'] > 0 and p['pe_cycle'] < 200 else "N/A"
        rows += (f"<tr><td>{name}</td><td>{p['code']}</td>"
                 f"<td>{p['price']:.1f}</td><td>{p['mkt_cap']:.0f}</td>"
                 f"<td>{p['eps_2025']:.2f}</td><td>{p['eps_cycle']:.2f}</td>"
                 f"<td>{cycle_pe_str}</td><td>{p['pb']:.2f}</td>"
                 f"<td>{p['roe']:.1f}%</td><td>{p['cost_kg']:.1f}</td>"
                 f"<td>{p['debt']:.1f}%</td><td style='font-weight:600'>{rank}</td></tr>")

    return f"""<table>
      <thead><tr><th>公司</th><th>代码</th><th>股价</th><th>市值(亿)</th><th>2025EPS</th><th>周期EPS</th><th>周期PE</th><th>PB</th><th>ROE%</th><th>成本</th><th>负债%</th><th>排名</th></tr></thead>
      <tbody>{rows}</tbody></table>
      <p style="margin-top:8px;font-size:12px;color:#999">数据来源：基本面——2025年报；行情——亿牛网 2026-07（本机SSL阻断，手工采集）。<b>周期EPS=2018-2025年8年均值</b>（Hooke方法论：周期型公司使用周期平均盈利做估值对比）。
      正邦2023年EPS按扣非调整（剔除~85亿债务重组一次性收益）；新希望/正邦周期均值EPS≈0或为负→周期PE无意义。</p>"""

def build_peak_table():
    """构建周期高峰情景表"""
    rows = ""
    # 选取代表性猪价点
    display_prices = [14, 16, 18, 20, 22, 24, 26]
    for pp in display_prices:
        fin = CYCLE_PEAK[pp]
        eps = fin["eps"]
        p10 = fin["peak_price_low"]
        p14 = fin["peak_price_mid"]
        p16 = fin["peak_price_high"]
        upside = (p14 / CURRENT_PRICE - 1) * 100
        # 概率描述
        if pp <= 14:
            prob_desc = "较高（猪周期温和反弹是常态）"
        elif pp <= 18:
            prob_desc = "中等（需供需共振）"
        elif pp <= 22:
            prob_desc = "较低（需供给严重收缩）"
        else:
            prob_desc = "极低（需类似ASF的外部冲击）"
        highlight = 'style="font-weight:600;background:#f0f4f8"' if pp == 18 else ""

        rows += (f"<tr {highlight}><td>{pp}</td>"
                 f"<td>{prob_desc}</td>"
                 f"<td>{eps:.2f}</td>"
                 f"<td>{p10:.0f}</td><td style='font-weight:600'>{p14:.0f}</td><td>{p16:.0f}</td>"
                 f"<td style='color:{C['green'] if upside > 50 else C['orange'] if upside > 20 else C['gray']}'>"
                 f"{upside:+.0f}%</td></tr>")

    return f"""<table>
      <thead><tr><th>猪价(元/kg)</th><th>概率判断</th><th>峰值EPS(元)</th><th>保守 10×PE</th><th>基准 14×PE</th><th>乐观 16×PE</th><th>较当前{ CURRENT_PRICE }元<br>潜在涨幅</th></tr></thead>
      <tbody>{rows}</tbody></table>
      <p style="font-size:12px;color:#999">注：猪价16-18元/kg是历史周期最常出现的温和高峰区间（2016、2024）；20元以上需显著供给收缩；26元以上需类似ASF的外部冲击（2019-2020重现概率极低）。<br>
      高亮行为<b>典型周期高峰（猪价18元/kg）</b>——在无外部冲击下，一轮正常猪周期可能触及的价格上沿。</p>"""

def build_peer_ranking_detail():
    rows = ""
    for i, (name, score) in enumerate(PEER_RANKING):
        p = PEERS[name]
        rows += (f"<tr><td>{i+1}</td><td style='font-weight:{'700' if i==0 else '400'}'>{name}</td>"
                 f"<td>{score}</td><td>{p['roe']:.1f}%</td><td>{p['cost_kg']:.1f}</td>"
                 f"<td>{p['hog_2025']:,}</td><td>{p['debt']:.1f}%</td></tr>")

    return f"""<table>
      <thead><tr><th>排名</th><th>公司</th><th>综合得分</th><th>ROE%</th><th>成本(元/kg)</th><th>出栏(万头)</th><th>负债%</th></tr></thead>
      <tbody>{rows}</tbody></table>
      <p style="font-size:12px;color:#999">评分维度及权重：ROE(3)、成本优势(3)、规模(2)、财务健康(1.5)、净利率(1.5)</p>"""

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
  <div class="sub">证券分析 · 第 6 步 · {today} · 周期型公司 · 四种方法交叉验证</div>
</div>
<div class="container">

  <!-- 1. 估值摘要 -->
  <div class="section">
    <h2>1. 估值摘要与综合判断</h2>
    <p class="source">来源：第5步财务预测 · 周期平均盈利(2018-2025) · 同行对比(亿牛网2026-07) · 生猪期货(大商所2026-07-28) · 四种方法交叉验证 · 历史低谷PE校准</p>

    <div class="box">
      <p style="margin:0">
        <b>加权估值：</b>四种方法(DCF 20% + 相对价值 60% + 并购 10% + LBO 10%)加权目标价 <b style="font-size:18px">{target_mid:.0f} 元/股</b>（区间 {target_low:.0f}-{target_high:.0f} 元），安全边际 ±15%（{safe_low:.0f}-{safe_high:.0f}元）。<br>
        当前股价 <b>{current_price:.1f} 元</b>，较加权目标价 <b>{premium_sign}{abs_premium_pct:.0f}%</b> —— 处于模型合理区间内。<br>
        <b>概率加权估值（下行20%+基准50%+上行30%）= {prob_weighted:.1f}元</b> —— 与加权目标价基本一致。<br><br>

        <b>🔍 三重交叉验证（模型之外）：</b><br>
        ① <b>历史低谷PE验证：</b>2021年以来低谷周期PE从未低于 <b>{trough_floor:.0f}×</b>（即使在2023亏损年）。当前周期PE=<b>{current_cycle_pe:.1f}×</b>，<b style="color:#c0392b">处于2021年以来最低水平</b>，低于历史低谷下限。若回到低谷均值{trough_avg:.0f}×，公允价为<b>{fair_trough_avg:.0f}元</b>。<br>
        ② <b>期货市场验证：</b>大商所期货隐含2027H1均价≈{avg_fut_2027h1:.2f}元/kg，偏向<b>基准偏上</b>情景。当前股价{current_price}元已基本反映期货隐含的复苏预期——既未明显低估也未泡沫化。<br>
        ③ <b>周期高峰潜力：</b>若猪价回升至16-18元/kg（历史常见温和高峰），按峰值PE 14×，股价可达 <b>106-150元</b>（+170~280%）。这是周期股的长期不对称收益来源。<br><br>

        <b>📊 综合判断：</b><br>
        模型目标价38元代表<b>"周期均值下的合理价值"</b>——当前+3%说明短期不存在显著低估。<br>
        但历史低谷验证揭示了一个更深层的事实：市场的<b>"实际定价习惯"</b>（低谷PE≥{trough_floor:.0f}×）远高于模型的<b>"理论定价框架"</b>（PE 15-22×）。<br>
        <b>当前{current_price:.1f}元 ≈ 周期均值估值38元，但远低于市场习惯的低谷底价{floor_price:.0f}元。</b><br>
        如果历史规律成立，当前价格处于"<b>模型合理 + 市场便宜</b>"的交汇点——下行有限（历史低谷底价{floor_price:.0f}元），上行有周期高峰的期权价值。
      </p>
    </div>
    {summary_table}
  </div>

  <!-- 2. DCF 估值 -->
  <div class="section">
    <h2>2. DCF 内在价值法（权重 20%）</h2>
    <p class="source">来源：两阶段模型——5年显式预测(2026E-2030E) + 终值(50%永续+50%退出乘数)；WACC via CAPM；参数见下表</p>
    <h3>FCF 预测</h3>
    {dcf_ch1}
    {dcf_detail}
    <h3>WACC 敏感性</h3>
    {dcf_ch2}
    <p>DCF对WACC和永续增长率高度敏感——这也是Hooke建议DCF权重仅20%的原因。在基准WACC={wacc:.1f}%/g={terminal_g:.1f}%下，每股价值<b>{dcf_base_val:.1f}元</b>。</p>
    <h3>WACC交叉验证：积层法（Build-up Method）</h3>
    <div class="box">
      <p style="margin:0">
        <b>积层法公式：</b>k = Rf({rf}%) + ERP({erp}%) + 行业风险({industry_rp:+.1f}%) + 规模风险({size_rp:+.1f}%) + 公司特定风险({company_rp:+.1f}%)<br>
        <b>积层法 Ke = {ke_build:.1f}%</b>（vs CAPM Ke={ke_capm:.1f}%）<br>
        <b>积层法 WACC = {wacc_build:.1f}%</b>（vs CAPM WACC={wacc_capm:.1f}%）<br>
        两者差异仅{WACC_diff:.1f}pp，CAPM结果合理。取CAPM WACC={wacc_capm:.1f}%作为基准。<br>
        <span style="font-size:12px;color:#999">参数说明：行业风险-0.5%（养猪业民生必需，略具防御性）；规模风险0%（大盘股~2000亿市值）；公司特定+1.5%（高杠杆+强周期波动）</span>
      </p>
    </div>
  </div>

  <!-- 3. 相对价值法 -->
  <div class="section">
    <h2>3. 相对价值法（权重 60%）</h2>
    <p class="source">来源：同行公司年报2025 + 亿牛网2026-07行情（本机SSL阻断，手工采集）；使用周期平均EPS计算目标PE</p>
    <h3>3a. 同行估值对比</h3>
    {peer_ch3}
    <h3>3b. 同行基本面排名</h3>
    {peer_ranking}
    <h3>3c. 同行详细数据</h3>
    {peer_detail}
    <h3>3d. PE Band 历史区间</h3>
    {pe_band_ch4}
    <h3>3e. 股价走势与PB估值</h3>
    {price_pe_ch4b}
    <p style="font-size:12px;color:#888">季度股价取季末收盘价，灰色带为季度内最高/最低价区间。PB（市净率）= 季末收盘价 ÷ 季末每股净资产（BPS）。选择PB而非PE是因为周期股TTM EPS在周期底部趋近于零，PE会极端膨胀至无意义值（如175×），而BPS始终为正，PB走势与股价天然协调，更适合双轴对比分析。当前数据截至2026Q1财报 + 最新股价。</p>
    <div class="box-green">
      <p style="margin:0"><b>相对价值法结论：</b>牧原在同行中<b>综合排名第1</b>（成本最低、ROE最高、规模最大）。
      同行周期PE参考：温氏~28×、神农~36×（新希望/正邦周期EPS≤0，PE无意义）。
      给予牧原合理周期PE <b>{target_pe_low}-{target_pe_high}×</b> 周期均值EPS {avg8_eps:.2f}——
      较同行折价30-50%，反映大盘股PE折价和猪价高度不确定性。<br>
      得到每股价值 <b>{rel_low:.0f}-{rel_high:.0f} 元</b>（中值 {rel_mid:.0f} 元）。
      P/B和EV/EBITDA作为交叉验证。</p>
    </div>
  </div>

  <!-- 4. 并购价值法 -->
  <div class="section">
    <h2>4. 并购价值法（权重 10%）</h2>
    <p class="source">来源：行业典型并购EV/EBITDA倍数区间（养猪行业可比并购交易公开数据有限，使用行业经验区间）</p>
    <div class="box">
      <p style="margin:0">
        <b>假设：</b>行业并购EV/EBITDA倍数 <b>{ma_ev_low}-{ma_ev_high}×</b><br>
        <b>估值：</b>周期正常化EBITDA {norm_ebitda:.0f} 亿（2027E基准） × {ma_ev_low}-{ma_ev_high}× = EV {ma_ev_low_val:.0f}-{ma_ev_high_val:.0f} 亿<br>
        <b>每股价值：</b>{ma_low:.0f}-{ma_high:.0f} 元（中值 {ma_mid:.0f} 元）<br>
        <b>底价参考：</b>股价不应低于收购价值的70%-75% → <b>{ma_floor_70:.0f}-{ma_floor_75:.0f} 元</b>
      </p>
    </div>
  </div>

  <!-- 5. LBO -->
  <div class="section">
    <h2>5. LBO 杠杆收购法（权重 10%）</h2>
    <p class="source">来源：PE收购视角——Entry 5.5-7.5× EBITDA，Exit 8×，IRR 15-20%</p>
    <div class="box">
      <p style="margin:0">
        <b>假设：</b>收购杠杆 4-5× EBITDA，持有5年，退出8× EBITDA<br>
        <b>隐含Entry EV/EBITDA：</b>{lbo_entry_low}-{lbo_entry_high}×<br>
        <b>每股价值：</b>{lbo_low:.0f}-{lbo_high:.0f} 元（中值 {lbo_mid:.0f} 元）<br>
        <b>LBO通常作为估值底价参考</b>——战略收购方出价通常更高。
      </p>
    </div>
  </div>

  <!-- 6. 估值汇总 -->
  <div class="section">
    <h2>6. 估值汇总</h2>
    <p class="source">来源：四种方法加权——DCF(20%) + 相对价值(60%) + 并购(10%) + LBO(10%)</p>
    {bridge_ch5}
    {safety_ch6}
    <div class="box-green" style="margin-top:16px">
      <p style="margin:0">
        <b>加权目标价：{target_mid:.0f} 元/股</b>（区间 {target_low:.0f}-{target_high:.0f} 元）<br>
        <b>±15% 安全边际：{safe_low:.0f} - {safe_high:.0f} 元</b><br>
        当前股价 <b>{current_price:.1f} 元</b>，
        {premium_judgment}
      </p>
    </div>
  </div>

  <!-- 7. 情景估值矩阵 -->
  <div class="section">
    <h2>7. 情景估值矩阵与股价评估</h2>
    <p class="source">来源：三种情景（上行/基准/下行）——对应猪价2027E={sc_up_price:.1f}/{sc_base_price:.1f}/{sc_down_price:.1f}元/kg，DCF用对应情景预测，相对PE用周期均值</p>

    <h3>7a. 三种情景加权估值</h3>
    {scenario_table}

    <h3>7b. 当前股价定位</h3>
    <div class="box-orange">
      <p style="margin:0">{price_assessment}</p>
    </div>

    <h3>7c. 猪价→EPS→估值传导分析</h3>
    <p>猪价每变动 <b>±1元/kg</b> → 2027E EPS变动约 <b>±1.6元</b>（出栏8300万头×110kg/头×1元/kg/54.7亿股×税率调整≈1.6元）</p>
    <p>按周期PE {target_pe_mid}× 估值：猪价±1元 → 目标价变动约 <b>±30元</b></p>
    <div class="box">
      <p style="margin:0">
        <b>情景估值结论：</b><br>
        · <b>下行情景</b>（猪价{sc_down_price}元/kg）：加权目标约 <b>{sc_down_weighted:.0f}元</b>，2027E EPS={sc_down_eps:.2f}——当前39.3元高出6%，市场未定价此悲观情景<br>
        · <b>基准情景</b>（猪价{sc_base_price}元/kg）：加权目标约 <b>{sc_base_weighted:.0f}元</b>，2027E EPS={sc_base_eps:.2f}——当前股价{sc_base_judgment}<br>
        · <b>上行情景</b>（猪价{sc_up_price}元/kg）：加权目标约 <b>{sc_up_weighted:.0f}元</b>，2027E EPS={sc_up_eps:.2f}——当前股价接近上行情景加权值<br>
        <b>关键发现：</b>情景间加权估值差异仅2元（37-39），因相对PE(60%权重)使用周期均值EPS不变。这正体现了Hooke方法论的优势——<b>周期型公司的估值锚定于长期盈利能力，而非短期猪价波动</b>。<br>
        若用2027E单年PE（非Hooke推荐），估值范围将剧烈波动：下行N/A→基准28元→上行70元——这恰恰说明为何不能依赖单年盈利。<br>
        <b>市场定价隐含的猪价预期约 {implied_price:.1f}元/kg</b>（反推：当前{current_price:.1f}元对应的2027E猪价，接近基准{sc_base_price}元/kg）
      </p>
    </div>

    <h3>7d. 期货市场隐含猪价 vs 模型假设</h3>
    <p class="source">来源：大连商品交易所 生猪期货 LH合约 2026-07-28收盘价。期货反映市场对远期猪价的"真金白银"预期，用于校准模型假设。</p>
    {futures_chart}
    <div class="box-orange">
      <p style="margin:0">
        <b>期货 vs 模型关键对比：</b><br>
        · <b>LH2611 (2026年11月) = {lh2611:.2f}元/kg</b> — 期货隐含2026年末猪价已反弹至12+元，显著高于模型基准全年均价({sc_price_2026:.1f})<br>
        · <b>LH2705 (2027年5月) = {lh2705:.2f}元/kg</b> — 期货隐含2027H1均价≈{avg_fut_2027h1:.2f}元/kg，<b>{futures_vs_base}</b>模型基准({sc_base_price:.1f})<br>
        · <b>期货定价偏向：{futures_scenario_label}情景</b> — 市场资金投票的猪价路径更接近模型的{futures_scenario_label}假设<br><br>
        <b>投资含义：</b><br>
        ① 期货市场正在定价一轮<b>中等强度的猪价复苏</b>（10.7→13.4元/kg，+25%），复苏节奏快于模型基准<br>
        ② 若期货定价正确，2027年猪价可能落在<b>12.5-13.5元区间</b>，介于基准与上行之间——此时模型加权估值约38-39元<br>
        ③ <b>当前股价39.3元已基本反映了期货隐含的复苏预期</b>——股价没有明显低估，也没有明显泡沫<br>
        ④ 期货仅覆盖到2027年5月，更远期的周期高峰（16-22元/kg）尚未在期货中定价——这是潜在的<b>超额收益来源</b>
      </p>
    </div>

    <h3>7e. 历史低谷验证：周期PE下限校准</h3>
    <p class="source">来源：历年财务数据 + 历史股价高低点（同花顺/东方财富前复权）——用实际市场定价验证模型PE范围是否合理</p>
    {trough_chart}
    <div class="box-red">
      <p style="margin:0">
        <b>关键发现：2018年非瘟后，牧原发生了结构性重估——低谷周期PE从4×跳升至20-25×。</b><br><br>
        <b>历史低谷数据：</b><br>
        · <b>2018年（非瘟前恐慌）</b>：猪价跌至10元，股价最低5元，周期PE仅<b>4.4×</b>，PB仅1.1×——这是"灭绝恐惧"定价，此后从未重现<br>
        · <b>2021年（猪价暴跌）</b>：猪价从36跌至12元，但股价最低40元，周期PE=<b>25.3×</b>——市场已信任龙头韧性<br>
        · <b>2023年（全年亏损43亿）</b>：股价最低35元，周期PE=<b>20.6×</b>——即使亏损，市场也未跌破20×周期PE<br>
        · <b>2025年（当前低谷）</b>：股价最低50元，周期PE=<b>24.5×</b>——与2021/2023低谷PE一致<br><br>
        <b>2019年后的低谷PE地板：20-25×。</b>即使在亏损年份也未跌破。非瘟证伪了"规模不经济"假说，牧原从"高风险周期股"被重估为"周期中的成长龙头"。<br><br>
        <b>对当前估值的含义：</b><br>
        当前股价<b>{current_price:.1f}元 ÷ 周期EPS {avg8_eps:.2f} = {current_cycle_pe:.1f}× 周期PE</b><br>
        对比2019年后低谷PE地板（{trough_floor:.0f}×）：当前{current_cycle_pe:.1f}× <b>{vs_trough_floor}</b>历史低谷下限<br>
        若按历史低谷PE下限{trough_floor:.0f}×计，理论底价 = {avg8_eps:.2f} × {trough_floor:.0f} = <b>{floor_price:.0f}元</b><br>
        <b>当前{current_price:.1f}元{vs_floor_desc}</b><br><br>
        <b>方法论含义：</b>模型使用的目标PE 15-22×（中值19×）在2019年后从未被市场实际触及——所有低谷的周期PE均≥{trough_floor:.0f}×。这意味着：<br>
        ① 模型的"低估值"情景（15×）在现实中极难出现，除非发生系统性危机<br>
        ② 模型的"合理估值"中值（19×）实际上是市场的<b>极端恐慌定价</b>，而非正常定价<br>
        ③ 当前19.3×周期PE处于历史低谷区间的<b>最下沿</b>——这不是"合理"，而是"便宜"<br>
        ④ 若周期复苏确认，PE有从19×向25×均值回归的空间 → 额外约30%的PE扩张收益
      </p>
    </div>
  </div>

  <!-- 8. 周期高峰情景分析 -->
  <div class="section">
    <h2>8. 周期高峰情景分析 — 股价能到多高？</h2>
    <p class="source">来源：基于FORECAST模型（峰值猪价→峰值EPS） + 历史周期高峰PE校准（2020年ASF高峰PE=15-19×） + Hooke周期股PE压缩理论</p>

    <h3>8a. 方法论：为什么需要"峰值PE"这个独立概念？</h3>
    <div class="box">
      <p style="margin:0">
        <b>核心问题：</b>第1-7节给出了周期均值估值（穿越周期的"合理价值"~38元），但无法回答"股价在周期高峰能到多高"。<br><br>
        <b>周期股的双重定价机制：</b><br>
        ① <b>周期均值 × 周期PE = 合理价值：</b>2.04元 × 19× = 39元 —— 这是长期持有的锚<br>
        ② <b>峰值EPS × 峰值PE = 高峰潜在价：</b>7.55元 × 14× = 106元 —— 这是周期高峰的想象空间<br><br>
        <b>两个PE是不同概念：</b>周期PE（19×）是对平滑后"可持续"盈利的估值，峰值PE（10-16×）是对"已知不可持续"盈利的估值。<br>
        市场在周期高峰会<b>压缩PE</b>——因为理性投资者知道当前盈利无法维持。压缩幅度取决于高峰的"临时性"程度。<br>
        <b>猪价越高→盈利越明显不可持续→PE压缩越狠。</b>
      </p>
    </div>

    <h3>8b. 峰值PE的三层推导</h3>
    <table>
      <thead><tr><th>推导层次</th><th>方法</th><th>结论</th></tr></thead>
      <tbody>
        <tr><td><b>第一层·历史实证</b></td>
          <td>2020年ASF超级周期：猪价34→39元/kg，EPS=5.33，股价高峰~100元<br>
          计算：100 ÷ 5.33 = <b>18.8× 峰值PE</b><br>
          这是有史以来最极端的周期，峰值PE仅19×</td>
          <td>上限参考：~19×</td></tr>
        <tr><td><b>第二层·Hooke理论</b></td>
          <td>周期股在盈利高峰时，市场以<b>8-16×</b> PE交易（低于正常PE）<br>
          理由：市场前瞻性定价——当前高盈利≠未来高盈利</td>
          <td>理论区间：8-16×</td></tr>
        <tr><td><b>第三层·交叉验证</b></td>
          <td>若PE完全不压缩：峰值EPS=7.55(猪价16)×19×=143元（不合理）<br>
          若PE大幅压缩：7.55×10×=76元；若温和压缩：7.55×14×=106元<br>
          验证：76-106元区间与2020年100元历史高峰基本吻合</td>
          <td>合理区间：10-16×<br>中枢：<b>14×</b></td></tr>
      </tbody></table>

    <h3>8c. 猪价→峰值股价映射</h3>
    {peak_chart}

    <h3>8d. 峰值情景矩阵</h3>
    {peak_table}

    <h3>8e. 周期高峰投资含义</h3>
    <div class="box-green">
      <p style="margin:0">
        <b>1. 当前39.3元 ≠ 周期高峰价：</b>当前猪价仅~10元/kg（周期底部），股价已反映复苏预期。<br>
        <b>2. 温和高峰（猪价16-18元，历史常见）：</b>峰值股价76-129元，较当前有<b>+90%至+230%</b>的上行空间。<br>
        <b>3. 强周期高峰（猪价22+元，需供给冲击）：</b>峰值股价171-274元——但这要求类似ASF的外部事件，概率较低。<br>
        <b>4. 时间维度：</b>从当前周期底部到下一个高峰，通常需要1-2年（猪周期上升期约6-8个季度）。<br>
        <b>5. 核心风险：</b>若猪价仅反弹至14元（弱反弹），按14×PE对应股价仅61元——上行空间有限。<br>
        <b>6. 关键催化：</b>能繁母猪存栏持续下降（供需收紧）→猪价启动上行周期 → 盈利爆发 → 股价向峰值PE定价靠拢。<br><br>
        <b>方法论提醒：</b>周期高峰估值<b>不应</b>作为买入决策的唯一依据——它的作用是帮助理解"如果猪周期来了，股价可能到哪"。<br>
        买入决策应以周期均值估值为锚（~38元），在安全边际（32-44元）下沿或以下介入。
      </p>
    </div>
  </div>

  <!-- 9. 投资建议 -->
  <div class="section">
    <h2>9. 投资建议 — 证券分析第7步</h2>
    <p class="source">来源：综合第1-8节全部估值方法、交叉验证、情景分析及历史低谷校准</p>

    <h3>10a. 投资评级</h3>
    <div class="box-green">
      <p style="margin:0">
        <b>评级：增持（在安全边际区间内分批建仓）</b><br>
        <b>12个月目标价：42-49 元</b>（基于周期EPS {avg8_eps:.2f} × 周期PE {trough_floor:.0f}-{trough_avg:.0f}× = 历史低谷PE区间）<br>
        <b>当前价格：{current_price:.1f} 元</b>（{today}）<br>
        <b>潜在上涨：{upside_12m:.0f}%-{upside_12m_high:.0f}%</b>（至12个月目标价）<br>
        <b>周期高峰（2-3年）潜在上涨：170-280%</b>（若猪价回升至16-18元/kg）<br>
        <b>评级逻辑：</b>加权模型显示短期无显著低估(+3%)，但历史低谷验证表明当前周期PE({current_cycle_pe:.1f}×)处于2021年以来最低水平——市场定价已充分反映悲观预期。期货曲线验证猪价复苏在即，下行风险有限(历史底价{floor_price:.0f}元仅低{floor_downside:.0f}%)，上行有周期高峰期权。
      </p>
    </div>

    <h3>10b. 核心论点</h3>
    <table>
      <thead><tr><th>#</th><th>论点</th><th>支撑证据</th></tr></thead>
      <tbody>
        <tr><td>1</td><td><b>周期底部确认——猪价已无下行空间</b></td>
          <td>2026Q2猪价跌破10元后反弹至10.7元；能繁母猪存栏持续去化(2026Q2=3950万头，趋近正常保有量3750万头)；期货曲线升水至13.4元(+26%)——市场定价复苏</td></tr>
        <tr><td>2</td><td><b>成本优势在周期底部最被低估</b></td>
          <td>牧原完全成本11.0-11.3元/kg vs 行业平均13-15元——在猪价10元时，牧原微亏而行业深度亏损。这加速产能出清，使牧原在复苏时率先受益。2026H1已降至11.6元，趋势持续</td></tr>
        <tr><td>3</td><td><b>历史低谷PE地板提供强支撑</b></td>
          <td>2021年以来，即使亏损年(2023)，低谷周期PE从未低于{trough_floor:.0f}×。当前{current_cycle_pe:.1f}×低于历史下限，若回到低谷均值{trough_avg:.0f}×，对应股价{fair_trough_avg:.0f}元(+{upside_to_fair:.0f}%)</td></tr>
        <tr><td>4</td><td><b>规模化龙头享有结构性溢价</b></td>
          <td>2018非瘟后，牧原出栏从1100万→7800万头(+600%)，市占率从1.6%→10.8%。市场已从"高风险周期股"重估为"周期中的成长龙头"——PB从低谷1×升至3-4×，周期PE从4×升至20-25×</td></tr>
        <tr><td>5</td><td><b>周期高峰期权价值未被定价</b></td>
          <td>当前股价隐含猪价≈12.5元/kg(接近基准)，未定价周期高峰(16-22元/kg)的可能性。若温和高峰出现，股价可达106-150元(PE14×)。即使高峰概率仅30%，期权价值也显著</td></tr>
      </tbody></table>

    <h3>10c. 催化剂</h3>
    <div class="col2">
      <div>
        <p><b>短期（0-6个月）：</b></p>
        <ul>
          <li>能繁母猪存栏降至3900万头以下→供需收紧信号</li>
          <li>2026H2猪价季节性反弹至12-13元/kg</li>
          <li>公司2026半年报：亏损收窄+成本下降确认</li>
          <li>港股上市后估值重估/南下资金流入</li>
        </ul>
      </div>
      <div>
        <p><b>中期（6-18个月）：</b></p>
        <ul>
          <li>猪价突破14元/kg→盈利拐点确认→市场情绪逆转</li>
          <li>2027年猪价持续回升至13-14元/kg（期货已部分定价）</li>
          <li>产能去化加速（散养户退出加速）</li>
          <li>公司成本降至11元以下→盈利能力跃升</li>
        </ul>
      </div>
    </div>

    <h3>10d. 风险因素</h3>
    <table>
      <thead><tr><th>风险</th><th>影响</th><th>概率</th><th>应对</th></tr></thead>
      <tbody>
        <tr><td><b>猪价长期低迷</b>（猪价在10-12元持续>2年）</td><td>高——EPS持续为负，可能跌破历史低谷底价{floor_price:.0f}元</td><td>低(~15%)</td><td>关注能繁母猪数据——若持续>4000万头则风险上升；牧原成本优势使其比同行更能承受低价</td></tr>
        <tr><td><b>饲料成本上涨</b>（玉米/豆粕涨价）</td><td>中——成本上升压缩利润，但牧原成本控制优于同行</td><td>中(~25%)</td><td>跟踪饲料价格；牧原的饲料配方自给能力是缓冲</td></tr>
        <tr><td><b>疫病风险</b>（ASF反复/新疫情）</td><td>极高——短期恐慌抛售，中长期利好规模化龙头</td><td>低(~10%)</td><td>2018-2019经验：疫病短期利空、中长期加速行业集中——对牧原偏利好</td></tr>
        <tr><td><b>H股折价拖累</b>（港股IPO后AH价差）</td><td>低至中——H股通常较A股折价，可能拖累A股情绪</td><td>中(~30%)</td><td>AH折价是A股常态而非异常；港股上市带来的资金流入可能对冲</td></tr>
        <tr><td><b>宏观经济衰退</b>（消费萎缩→猪肉需求下降）</td><td>中——猪肉属必需消费品，需求弹性低</td><td>低至中(~20%)</td><td>猪肉消费对GDP的弹性约0.3-0.5——经济衰退影响有限</td></tr>
      </tbody></table>

    <h3>10e. 建议操作</h3>
    <div class="box">
      <p style="margin:0">
        <b>当前位置（{current_price:.1f}元）：</b>处于"模型合理+市场便宜"的交汇点。建议在安全边际下沿（{safe_low:.0f}元）附近或以下<b>分批建仓</b>，初始仓位不超过目标仓位的50%。<br><br>
        <b>加仓条件：</b>① 股价跌破{floor_price:.0f}元（历史低谷底价）→ 加至满仓；② 猪价突破14元/kg + 公司季度盈利转正 → 右侧加仓<br>
        <b>减仓条件：</b>① 股价达到周期均值估值上沿{target_high:.0f}元 → 减仓1/3；② 猪价突破18元/kg + 市场情绪亢奋 + PE扩张至25×以上 → 逐步退出<br>
        <b>止损条件：</b>能繁母猪持续>4200万头 + 猪价<10元/kg持续>3个季度 → 基本面恶化，重新评估<br>
        <b>时间框架：</b>12-24个月——周期股投资需要耐心等待猪价拐点确认。短期内(3-6个月)猪价可能在10-12元区间震荡。<br><br>
        <b>核心策略：</b>这是一笔"<b>{current_cycle_pe:.1f}×周期PE买周期底部龙头 + 附赠周期高峰看涨期权</b>"的交易。以周期均值估值38元为锚，以历史低谷底价{floor_price:.0f}元为底，以周期高峰106-150元为想象空间——盈亏比约{risk_reward_ratio}。
      </p>
    </div>
  </div>

  <!-- 10. 局限性 -->
  <div class="section">
    <h2>10. 数据来源与局限性</h2>
    <ul>
      <li><b>SSL阻断：</b>本机环境无法访问东方财富/亿牛网API，同行行情数据通过网页搜索手工采集（2026-07亿牛网），存在时效性偏差风险</li>
      <li><b>同行数据局限：</b>正邦科技因亏损导致PE失真；神农集团规模小、成长溢价高；周期平均EPS为基于2025年EPS的近似（非真实5年均值）</li>
      <li><b>并购数据缺失：</b>养猪行业可比并购交易公开数据极少，并购价值法使用的EV/EBITDA区间基于行业经验，非实际交易统计</li>
      <li><b>DCF敏感：</b>WACC ±1%或g ±0.5%可导致每股价值变动 ±20%以上——这正是DCF在周期型公司估值中权重仅20%的原因</li>
      <li><b>模型局限：</b>所有方法依赖预测假设（猪价、出栏、成本），实际走势可能与三种情景均不同</li>
      <li><b>数据新鲜度：</b>市场行情截止2026-07-28；财务报表截止2025年报；预测基于2026Q2数据</li>
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

def main():
    print("\n" + "=" * 60)
    print("牧原股份 估值分析 — 第 6 步")
    print("=" * 60)

    # 生成图表
    chart_funcs = [
        ("dcf_ch1", ch1_dcf_fcf),
        ("dcf_ch2", ch2_wacc_sensitivity),
        ("peer_ch3", ch3_peer_comparison),
        ("pe_band_ch4", ch4_pe_band),
        ("price_pe_ch4b", ch4b_price_pb_trend),
        ("bridge_ch5", ch5_valuation_bridge),
        ("safety_ch6", ch6_safety_margin),
        ("summary_table", ch7_summary_table),
        ("peak_chart", ch8_cycle_peak),
        ("futures_chart", ch9_futures_curve),
        ("trough_chart", ch10_trough_pe),
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

    # 构建文本
    premium_color = C["red"] if WV["premium_pct"] > 0 else C["green"]
    premium_sign = "+" if WV["premium_pct"] > 0 else ""

    if WV["premium_pct"] > 30:
        position_desc = "显著上方（高于目标区间）"
        premium_judgment = f"较目标价溢价 <b>{WV['premium_pct']:.0f}%</b>——股价已反映较多乐观预期，安全边际不足。建议等待回调至安全边际区间（{WV['safety'][0]:.0f}-{WV['safety'][1]:.0f}元）再考虑介入。"
        price_assessment = (f"当前股价 <b>{CURRENT_PRICE:.1f} 元</b>，较加权目标价 <b>{WV['target_mid']:.0f} 元</b>"
                           f"溢价 <b>{WV['premium_pct']:.0f}%</b>。<br><br>"
                           f"当前价格已超出上行情景下的加权估值（{SCENARIO_VAL['上行']['weighted']:.0f}元），"
                           f"市场定价极度乐观。<br><br>"
                           f"<b>市场可能定价了以下因素：</b>① 猪价强反弹（上行情景）② 公司成本持续下降至10元/kg以下 "
                           f"③ 港股上市后估值重估 ④ 行业整合加速、龙头溢价。"
                           f"但这些假设的实现需要时间验证，当前价格安全边际不足。")
    elif WV["premium_pct"] > 0:
        position_desc = "偏上方（略高于合理估值）"
        premium_judgment = f"较目标价小幅溢价 <b>{WV['premium_pct']:.0f}%</b>——处于合理估值上沿，可小仓位试探或等待回调。"
        price_assessment = f"当前股价 <b>{CURRENT_PRICE:.1f} 元</b>处于估值区间的上沿，接近但未突破安全边际上界。"
    else:
        position_desc = "合理区间内（低于或接近目标价）"
        premium_judgment = f"低于目标价 <b>{abs(WV['premium_pct']):.0f}%</b>——处于安全边际区间，具有投资价值。"
        price_assessment = f"当前股价 <b>{CURRENT_PRICE:.1f} 元</b>低于加权目标价，具备安全边际。"

    # 情景估值表格HTML
    def build_scenario_table():
        rows = ""
        labels = {"下行": "下行（猪价11.0→11.0→11.5）", "基准": "基准（猪价10.5→12.5→13.5）", "上行": "上行（猪价11.0→14.0→15.5）"}
        for sc in ["下行", "基准", "上行"]:
            sv = SCENARIO_VAL[sc]
            pe_fwd = sv["eps_2027"] * REL["pe_8y"]["pe_mid"] if sv["eps_2027"] > 0 else 0
            highlight = 'style="font-weight:600;background:#f0f4f8"' if sc == "基准" else ""
            rows += (f"<tr {highlight}><td>{sc}</td><td>{sv['price_2027']:.1f}</td>"
                     f"<td>{sv['eps_2027']:.2f}</td><td>{sv['dcf']:.0f}</td>"
                     f"<td>{sv['rel_cycle']:.0f}</td><td>{sv['ma']:.0f}</td><td>{sv['lbo']:.0f}</td>"
                     f"<td><b>{sv['weighted']:.0f}</b></td></tr>")
        return f"""<table>
          <thead><tr><th>情景</th><th>2027E猪价(元/kg)</th><th>2027E EPS</th><th>DCF(20%)</th><th>相对PE(60%)</th><th>并购(10%)</th><th>LBO(10%)</th><th>加权目标</th></tr></thead>
          <tbody>{rows}</tbody></table>
          <p style="font-size:12px;color:#999">注：相对PE估值使用8年周期均值EPS({AVG8_EPS:.2f})×目标PE中值({REL['pe_8y']['pe_mid']}×)，在所有情景中保持一致（基于历史而非预测）。DCF随情景变化（FCF预测不同）。</p>"""

    scenario_table = build_scenario_table()

    # 反推市场隐含猪价
    # 从当前股价反推：需要怎样的2027E EPS才能支撑当前价格？
    # target_price = EPS_2027 * target_pe → EPS_2027 = target_price / target_pe
    # 从EPS反推猪价：猪价 ≈ (EPS × shares × rev_mult / hog) + cost_adjustment
    implied_eps = CURRENT_PRICE / REL["pe_8y"]["pe_mid"]
    implied_hog_rev = implied_eps * TOTAL_SHARES * REV_MULTIPLIER
    implied_price = (implied_hog_rev * 1e4) / (HOG_FORECAST[2027] * AVG_WEIGHT)
    # 更简单的线性估算：基准EPS对应基准猪价
    base_eps = FORECAST["基准"][2027]["eps"]
    base_price_sc = PRICE_SCENARIOS["基准"][2027]
    eps_sensitivity = (FORECAST["上行"][2027]["eps"] - FORECAST["下行"][2027]["eps"]) / (PRICE_SCENARIOS["上行"][2027] - PRICE_SCENARIOS["下行"][2027])
    implied_price_v2 = base_price_sc + (implied_eps - base_eps) / eps_sensitivity if eps_sensitivity != 0 else implied_price

    # 构建情景判断文本
    sv_base = SCENARIO_VAL["基准"]
    sv_up = SCENARIO_VAL["上行"]
    sv_down = SCENARIO_VAL["下行"]
    if CURRENT_PRICE > sv_base["weighted"]:
        sc_base_judgment = "略高于基准目标价"
    else:
        sc_base_judgment = "处于或低于基准目标价"

    # 组装 HTML
    html = HTML.format(
        style=STYLE, today=TODAY_STR,
        current_price=CURRENT_PRICE,
        target_low=WV["target_low"], target_mid=WV["target_mid"], target_high=WV["target_high"],
        premium_pct=WV["premium_pct"], premium_color=premium_color, premium_sign=premium_sign,
        abs_premium_pct=abs(WV["premium_pct"]),
        position_desc=position_desc, premium_judgment=premium_judgment,
        price_assessment=price_assessment,
        safe_low=WV["safety"][0], safe_high=WV["safety"][1],
        avg8_eps=AVG8_EPS, avg5_eps=AVG5_EPS,
        wacc=WACC, terminal_g=TERMINAL_G,
        target_pe_low=REL["pe_8y"]["pe_low"], target_pe_high=REL["pe_8y"]["pe_high"],
        target_pe_mid=REL["pe_8y"]["pe_mid"],
        dcf_base_val=DCF_BASE["value_per_share"],
        rel_low=REL["recommended"]["low"], rel_mid=REL["recommended"]["mid"],
        rel_high=REL["recommended"]["high"],
        ma_low=MA["price_low"], ma_mid=MA["mid"], ma_high=MA["price_high"],
        ma_ev_low=MA["ev_mult_low"], ma_ev_high=MA["ev_mult_high"],
        ma_ev_low_val=MA["ev_low"], ma_ev_high_val=MA["ev_high"],
        ma_floor_70=MA["floor_70"], ma_floor_75=MA["floor_75"],
        lbo_low=LBO["low"], lbo_mid=LBO["mid"], lbo_high=LBO["high"],
        lbo_entry_low=LBO["entry_multiples"][0], lbo_entry_high=LBO["entry_multiples"][2],
        avg8_ebitda=AVG8_EBITDA,
        norm_ebitda=NORM_EBITDA,
        # 积层法参数
        rf=Rf, erp=ERP, industry_rp=BUILDUP_INDUSTRY, size_rp=BUILDUP_SIZE,
        company_rp=BUILDUP_COMPANY,
        ke_build=Ke_build, ke_capm=Ke, wacc_build=WACC_build, wacc_capm=WACC,
        WACC_diff=abs(WACC_build - WACC),
        # 情景估值矩阵
        scenario_table=scenario_table,
        sc_up_price=PRICE_SCENARIOS["上行"][2027],
        sc_base_price=PRICE_SCENARIOS["基准"][2027],
        sc_down_price=PRICE_SCENARIOS["下行"][2027],
        sc_up_weighted=SCENARIO_VAL["上行"]["weighted"],
        sc_base_weighted=SCENARIO_VAL["基准"]["weighted"],
        sc_down_weighted=SCENARIO_VAL["下行"]["weighted"],
        sc_up_eps=SCENARIO_VAL["上行"]["eps_2027"],
        sc_base_eps=SCENARIO_VAL["基准"]["eps_2027"],
        sc_down_eps=SCENARIO_VAL["下行"]["eps_2027"],
        sc_base_judgment=sc_base_judgment,
        implied_price=implied_price_v2,
        # 图表
        summary_table=chart_html["summary_table"],
        dcf_ch1=chart_html["dcf_ch1"], dcf_ch2=chart_html["dcf_ch2"],
        dcf_detail=build_dcf_detail(),
        peer_ch3=chart_html["peer_ch3"],
        pe_band_ch4=chart_html["pe_band_ch4"],
        price_pe_ch4b=chart_html["price_pe_ch4b"],
        peer_ranking=build_peer_ranking_detail(),
        peer_detail=build_peer_detail(),
        bridge_ch5=chart_html["bridge_ch5"],
        safety_ch6=chart_html["safety_ch6"],
        peak_chart=chart_html["peak_chart"],
        peak_table=build_peak_table(),
        # 期货远期曲线
        futures_chart=chart_html.get("futures_chart", ""),
        lh2611=FUTURES_CURVE.get("2026-11", {}).get("price", 0),
        lh2705=FUTURES_CURVE.get("2027-05", {}).get("price", 0),
        sc_price_2026=PRICE_SCENARIOS["基准"][2026],
        avg_fut_2027h1=avg_futures_2027h1,
        futures_vs_base=f"高于" if avg_futures_2027h1 > PRICE_SCENARIOS["基准"][2027] else "低于",
        futures_scenario_label=futures_scenario,
        # 历史低谷验证
        trough_chart=chart_html.get("trough_chart", ""),
        current_cycle_pe=current_cycle_pe,
        trough_floor=trough_pe_floor,
        vs_trough_floor=f"低于" if current_cycle_pe < trough_pe_floor else "高于",
        floor_price=floor_price_historical,
        vs_floor_desc=f"低于历史低谷理论底价{floor_price_historical:.0f}元——股价处于2019年以来最便宜的位置" if CURRENT_PRICE < floor_price_historical else f"略高于历史低谷理论底价",
        # 新摘要变量
        trough_avg=trough_pe_avg,
        fair_trough_avg=fair_trough_avg,
        # 投资建议
        upside_12m=round((fair_trough_avg / CURRENT_PRICE - 1) * 100),
        upside_12m_high=round((AVG8_EPS * trough_pe_avg / CURRENT_PRICE - 1) * 100),
        upside_to_fair=round((fair_trough_avg / CURRENT_PRICE - 1) * 100),
        floor_downside=round((1 - CURRENT_PRICE / floor_price_historical) * 100, 1),
        risk_reward_ratio="1:3至1:5（底部下行10% vs 高峰上行170-280%）",
        prob_weighted=prob_weighted_val,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html, encoding="utf-8")
    print(f"\n✅ 报告已生成: {REPORT_PATH}")
    print(f"   文件大小: {REPORT_PATH.stat().st_size / 1024:.0f} KB")

if __name__ == "__main__":
    main()
