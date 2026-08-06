# -*- coding: utf-8 -*-
"""
牧原股份综合证券分析研究报告 — 牧原股份 (SZ.002714)
证券分析八步流程 · 第8步：撰写研究报告

按《华尔街证券分析》标准八部分结构，综合前7步分析成果：
  1. 概述
  2. 宏观经济评述
  3. 相关股票市场前景
  4. 公司及其业务评述
  5. 财务分析
  6. 财务预测
  7. 评估方法的运用
  8. 投资建议
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
REPORT_PATH = REPORTS_DIR / "证券分析研究报告.html"
TODAY_STR = datetime.now().strftime("%Y-%m-%d")

# ==================== 颜色常量 ====================
C = {
    "blue": "#3498db", "red": "#c0392b", "green": "#27ae60",
    "orange": "#e67e22", "purple": "#8e44ad", "dark": "#2c3e50",
    "gray": "#7f8c8d", "teal": "#1abc9c", "midblue": "#2980b9",
    "darkgreen": "#1e8449", "gold": "#f39c12",
}
PLOTLY_TEMPLATE = "plotly_white"

# ==================== 数据加载 ====================

def safe_float(val, default=None):
    if val is None or (isinstance(val, float) and pd.isna(val)) or val == '':
        return default
    try: return float(val)
    except (ValueError, TypeError): return default

def load_csv(filename):
    path = DATA_DIR / filename
    if not path.exists(): return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    return df

def get_annual_rows(df, date_col="REPORT_DATE"):
    if df.empty: return pd.DataFrame()
    df = df.copy()
    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["_year"] = df["_date"].dt.year
    annual = df[df["_date"].dt.month == 12].copy()
    annual = annual.sort_values("_date").drop_duplicates(subset=["_year"], keep="last")
    return annual.sort_values("_year")

# 加载四大报表
df_income = load_csv("利润表_按报告期.csv")
df_balance = load_csv("资产负债表_按报告期.csv")
df_cashflow = load_csv("现金流量表_按报告期.csv")
df_indicator = load_csv("主要财务指标_按报告期.csv")

annual_income = get_annual_rows(df_income)
annual_balance = get_annual_rows(df_balance)
annual_cashflow = get_annual_rows(df_cashflow)
annual_indicator = get_annual_rows(df_indicator)

y_inc = annual_income["_year"].tolist()
y_bal = annual_balance["_year"].tolist()
y_cf = annual_cashflow["_year"].tolist()
common_years = sorted(set(y_inc) & set(y_bal) & set(y_cf))

def row_for_year(df_annual, year):
    rows = df_annual[df_annual["_year"] == year]
    return None if rows.empty else rows.iloc[0]

FIN = {}
for yr in common_years:
    inc = row_for_year(annual_income, yr)
    bal = row_for_year(annual_balance, yr)
    cf = row_for_year(annual_cashflow, yr)
    ind = row_for_year(annual_indicator, yr)
    if inc is None or bal is None or cf is None: continue
    d = {
        "revenue": safe_float(inc.get("TOTAL_OPERATE_INCOME"),0)/1e8,
        "operate_cost": safe_float(inc.get("OPERATE_COST"),0)/1e8,
        "sale_exp": safe_float(inc.get("SALE_EXPENSE"),0)/1e8,
        "manage_exp": safe_float(inc.get("MANAGE_EXPENSE"),0)/1e8,
        "rd_exp": safe_float(inc.get("RESEARCH_EXPENSE"),0)/1e8,
        "fin_exp": safe_float(inc.get("FINANCE_EXPENSE"),0)/1e8,
        "interest_exp": safe_float(inc.get("FE_INTEREST_EXPENSE"),0)/1e8,
        "op_profit": safe_float(inc.get("OPERATE_PROFIT"),0)/1e8,
        "total_profit": safe_float(inc.get("TOTAL_PROFIT"),0)/1e8,
        "net_profit": safe_float(inc.get("NETPROFIT"),0)/1e8,
        "parent_profit": safe_float(inc.get("PARENT_NETPROFIT"),0)/1e8,
        "eps": safe_float(inc.get("BASIC_EPS"),0),
        "total_assets": safe_float(bal.get("TOTAL_ASSETS"),0)/1e8,
        "total_liab": safe_float(bal.get("TOTAL_LIABILITIES"),0)/1e8,
        "total_equity": safe_float(bal.get("TOTAL_EQUITY"),0)/1e8,
        "short_loan": safe_float(bal.get("SHORT_LOAN"),0)/1e8,
        "long_loan": safe_float(bal.get("LONG_LOAN"),0)/1e8,
        "notes_payable": safe_float(bal.get("NOTE_PAYABLE"),0)/1e8,
        "ocf": safe_float(cf.get("NETCASH_OPERATE"),0)/1e8,
        "capex": safe_float(cf.get("CONSTRUCT_LONG_ASSET"),0)/1e8,
        "depreciation": (safe_float(cf.get("FA_IR_DEPR"),0)+safe_float(cf.get("USERIGHT_ASSET_AMORTIZE"),0))/1e8,
        "roe": safe_float(ind.get("ROEJQ"),0) if ind is not None else None,
    }
    rev = d["revenue"]
    d["gross_margin"] = (rev-d["operate_cost"])/rev*100 if rev>0 else 0
    d["net_margin"] = d["net_profit"]/rev*100 if rev>0 else 0
    d["interest_debt"] = d["short_loan"]+d["long_loan"]+d.get("notes_payable",0)
    d["ebit"] = d["total_profit"]+d["interest_exp"]
    d["ebitda"] = d["ebit"]+d.get("depreciation",0)
    d["debt_ratio"] = d["total_liab"]/d["total_assets"]*100 if d["total_assets"]>0 else 0
    FIN[yr] = d

SORTED_YEARS = sorted(FIN.keys())
LATEST = max(SORTED_YEARS)
print(f"财务数据: {SORTED_YEARS[0]}-{LATEST} ({len(SORTED_YEARS)}年)")

# ==================== 关键参数 ====================
TOTAL_SHARES = 54.7
CURRENT_PRICE = 39.3
CURRENT_MKT_CAP = CURRENT_PRICE * TOTAL_SHARES

CYCLE_8Y = [y for y in SORTED_YEARS if 2018 <= y <= 2025]
CYCLE_5Y = [y for y in SORTED_YEARS if 2021 <= y <= 2025]
AVG8_EPS = sum(FIN[yr]["eps"] for yr in CYCLE_8Y)/len(CYCLE_8Y)
AVG5_EPS = sum(FIN[yr]["eps"] for yr in CYCLE_5Y)/len(CYCLE_5Y)
AVG8_PARENT = sum(FIN[yr]["parent_profit"] for yr in CYCLE_8Y)/len(CYCLE_8Y)
AVG8_EBITDA = sum(FIN[yr]["ebitda"] for yr in CYCLE_8Y)/len(CYCLE_8Y)
CURRENT_PE_CYCLE = CURRENT_PRICE/AVG8_EPS

# 历史PE
HIST_PE = {}
for _, row in annual_indicator.iterrows():
    yr = int(row["_year"])
    if 2018 <= yr <= 2025:
        per_toi = safe_float(row.get("PER_TOI"),None)
        per_oi = safe_float(row.get("PER_OI"),None)
        eps = safe_float(row.get("EPSJB"),0)
        pe = per_toi if per_toi and per_toi<200 else (per_oi if per_oi and per_oi<200 else None)
        HIST_PE[yr] = {"pe": pe, "eps": eps, "is_loss": eps<0}

print(f"周期均值: 8Y EPS={AVG8_EPS:.2f}, 当前周期PE={CURRENT_PE_CYCLE:.1f}×")

# ==================== 预测模型参数 ====================
AVG_WEIGHT=110; REV_MULTIPLIER=1.16; NON_HOG_COST_RATE=0.90
INTEREST_RATE=0.035; TAX_RATE_LOW=0.0; TAX_RATE_HIGH=0.05
COST_RATES={"sale_rate":0.23,"manage_rate":0.92,"rd_rate":1.15}
_da_rates=[FIN[yr]["depreciation"]/FIN[yr]["revenue"] for yr in [2023,2024,2025] if yr in FIN and FIN[yr]["depreciation"]>0]
DA_RATE=sum(_da_rates)/len(_da_rates) if _da_rates else 0.10

HOG_FORECAST={2025:7798,2026:8100,2027:8300,2028:8500}
PRICE_SCENARIOS={
    "上行":{2025:14.4,2026:11.0,2027:14.0,2028:15.5},
    "基准":{2025:14.4,2026:10.5,2027:12.5,2028:13.5},
    "下行":{2025:14.4,2026:10.0,2027:11.0,2028:11.5},
}
COST_SCENARIOS={
    "上行":{2025:12.0,2026:11.5,2027:11.5,2028:11.3},
    "基准":{2025:12.0,2026:11.5,2027:11.3,2028:11.0},
    "下行":{2025:12.0,2026:11.8,2027:11.5,2028:11.3},
}

def project_ebit_eps(scenario, year):
    hog=HOG_FORECAST.get(year,8500)
    price=PRICE_SCENARIOS[scenario][year]
    cost=COST_SCENARIOS[scenario][year]  # 分情景成本（与 Step 5 财务预测一致）
    hog_rev=hog*AVG_WEIGHT*price/1e4
    total_rev=hog_rev*REV_MULTIPLIER
    hog_cost=hog*AVG_WEIGHT*cost/1e4
    non_hog_rev=total_rev-hog_rev
    non_hog_cost=non_hog_rev*NON_HOG_COST_RATE
    total_cost=hog_cost+non_hog_cost
    gp=total_rev-total_cost
    se=total_rev*COST_RATES["sale_rate"]/100
    me=total_rev*COST_RATES["manage_rate"]/100
    rd=total_rev*COST_RATES["rd_rate"]/100
    base_debt=FIN[LATEST]["interest_debt"]
    dr={2025:0,2026:25,2027:55,2028:85}
    net_debt=max(base_debt-dr.get(year,0),base_debt*0.6)
    ie=net_debt*INTEREST_RATE
    op=gp-se-me-rd-ie
    tp=op; ebit=tp+ie
    tax=tp*TAX_RATE_HIGH if tp>100 else tp*TAX_RATE_LOW
    tax=max(tax,0)
    np_val=tp-tax; pp=np_val*0.98; eps=pp/TOTAL_SHARES
    return ebit,eps,total_rev,ie,tp

FORECAST={}
for sc in ["基准","上行","下行"]:
    FORECAST[sc]={}
    for yr in [2025,2026,2027,2028]:
        ebit,eps,rev,ie,tp=project_ebit_eps(sc,yr)
        da=rev*DA_RATE
        FORECAST[sc][yr]={"ebit":ebit,"eps":eps,"revenue":rev,"ebitda":ebit+da}

# ==================== 估值参数 ====================
# 市场验证框架（来自第 6 步估值报告 §4-§5，旧四方法加权已删除）
# 成熟期（2022+，56个月）周期均值PE 分布：P25/P50/P75 = 21.1/23.9/26.4
FAIR_PE={"p25":21.1,"p50":23.9,"p75":26.4}
FAIR_VALUE={"low":AVG8_EPS*FAIR_PE["p25"],"mid":AVG8_EPS*FAIR_PE["p50"],"high":AVG8_EPS*FAIR_PE["p75"]}
# 峰值主模型：PB 3.9-4.3×（2025 成熟期峰值实测 4.25×）× 2028E BPS
PEAK_PB_LO,PEAK_PB_HI=3.9,4.3

# ── 2028E 峰值预测基础数据 ──
_qf_bps=pd.read_csv(ROOT/"data"/"主要财务指标_按单季度.csv",dtype=str)
_qf_bps["REPORT_DATE"]=pd.to_datetime(_qf_bps["REPORT_DATE"])
_qf_bps["BPS"]=pd.to_numeric(_qf_bps["BPS"],errors="coerce")
_q4=_qf_bps[_qf_bps["REPORT_DATE"].dt.month==12].sort_values("REPORT_DATE")
BPS_2025=float(_q4[_q4["REPORT_DATE"].dt.year==2025]["BPS"].iloc[0])
PEAK_BPS={sc:BPS_2025+sum(FORECAST[sc][yr]["eps"] for yr in [2026,2027,2028]) for sc in ["上行","基准","下行"]}
PEAK_PRICE={sc:(PEAK_BPS[sc]*PEAK_PB_LO,PEAK_BPS[sc]*PEAK_PB_HI) for sc in ["上行","基准","下行"]}
# 2028E 周期均值 EPS（滚动8年 2021-2028）
_hist_eps=[FIN[yr]["eps"] for yr in [2021,2022,2023,2024,2025]]
PEAK_CYC_EPS={sc:(sum(_hist_eps)+sum(FORECAST[sc][yr]["eps"] for yr in [2026,2027,2028]))/8 for sc in ["上行","基准","下行"]}

# ==================== 敏感性矩阵 ====================
# 基于视频"边际成本定价"框架：猪价×出栏量×成本 → 净利润敏感性
SENS_PRICES = [10, 11, 12, 13, 14, 15, 16, 17, 18]
SENS_HOGS = [7500, 8000, 8500, 9000]
SENS_COSTS = [10.5, 11.0, 11.5, 12.0, 12.5, 13.0]
SENS_BASE_COST = 11.6
SENS_BASE_HOG = 8000
SENS_WEIGHT = 125  # 均重 kg

def profit_simple(price, cost, hogs):
    """简化利润模型：亿"""
    return (price - cost) * SENS_WEIGHT * hogs / 10000

# 猪价×出栏量 矩阵（成本固定=11.6）
MATRIX_PRICE_HOG = {}
for p in SENS_PRICES:
    for h in SENS_HOGS:
        MATRIX_PRICE_HOG[(p, h)] = profit_simple(p, SENS_BASE_COST, h)

# 猪价×成本 矩阵（出栏固定=8000万）
MATRIX_PRICE_COST = {}
for p in SENS_PRICES:
    for c in SENS_COSTS:
        MATRIX_PRICE_COST[(p, c)] = profit_simple(p, c, SENS_BASE_HOG)

def ch8_sensitivity():
    """图表8: 猪价×出栏量→净利润 敏感性热力图"""
    z_hog = [[MATRIX_PRICE_HOG[(p, h)] for h in SENS_HOGS] for p in SENS_PRICES]
    z_cost = [[MATRIX_PRICE_COST[(p, c)] for c in SENS_COSTS] for p in SENS_PRICES]

    fig = make_subplots(rows=1, cols=2,
        subplot_titles=("猪价 × 出栏量 → 净利润（亿）<br><sub>完全成本=11.6元/kg, 均重=125kg</sub>",
                        "猪价 × 完全成本 → 净利润（亿）<br><sub>出栏量=8000万头, 均重=125kg</sub>"),
        horizontal_spacing=0.18)

    # 左图: 猪价×出栏量
    heat1 = go.Heatmap(
        z=z_hog, x=[f"{h}万" for h in SENS_HOGS], y=[f"{p}元" for p in SENS_PRICES],
        colorscale=[(0, "#c0392b"), (0.35, "#f5b7b1"), (0.45, "#fdebd0"),
                    (0.5, "#f7f7f7"), (0.55, "#d5f5e3"), (0.7, "#82e0aa"), (1, "#1e8449")],
        zmid=0, zmin=-300, zmax=800,
        text=[[f"{MATRIX_PRICE_HOG[(p, h)]:.0f}亿" for h in SENS_HOGS] for p in SENS_PRICES],
        texttemplate="%{text}", textfont={"size": 10, "color": "#1a1a1a"},
        colorbar=dict(title="净利润(亿)", x=0.455, len=0.85), showscale=True,
        hovertemplate="猪价=%{y}, 出栏=%{x}<br>净利润=%{z:.0f}亿<extra></extra>")

    # 右图: 猪价×成本
    heat2 = go.Heatmap(
        z=z_cost, x=[f"{c}元" for c in SENS_COSTS], y=[f"{p}元" for p in SENS_PRICES],
        colorscale=[(0, "#c0392b"), (0.35, "#f5b7b1"), (0.45, "#fdebd0"),
                    (0.5, "#f7f7f7"), (0.55, "#d5f5e3"), (0.7, "#82e0aa"), (1, "#1e8449")],
        zmid=0, zmin=-300, zmax=800,
        text=[[f"{MATRIX_PRICE_COST[(p, c)]:.0f}亿" for c in SENS_COSTS] for p in SENS_PRICES],
        texttemplate="%{text}", textfont={"size": 10, "color": "#1a1a1a"},
        colorbar=dict(title="净利润(亿)", x=1.01, len=0.85),
        hovertemplate="猪价=%{y}, 成本=%{x}<br>净利润=%{z:.0f}亿<extra></extra>")

    fig.add_trace(heat1, row=1, col=1)
    fig.add_trace(heat2, row=1, col=2)
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        font=dict(family="Microsoft YaHei,PingFang SC,sans-serif", size=11, color="#1a1a1a"),
        height=420, margin=dict(l=55, r=55, t=80, b=50),
        title=dict(text="利润敏感性矩阵 — 猪价·出栏量·成本三变量", x=0.02, y=0.98, font_size=14))
    fig.update_xaxes(title_text="", side="bottom")
    fig.update_yaxes(title_text="猪价（元/kg）", row=1, col=1)
    return fig

# ==================== 图表生成 ====================

def ch1_revenue_profit():
    """图表1: 营收与利润17年趋势"""
    yrs=list(range(2009,LATEST+1))
    revs=[FIN[yr]["revenue"] if yr in FIN else None for yr in yrs]
    profits=[FIN[yr]["parent_profit"] if yr in FIN else None for yr in yrs]
    fig=make_subplots(specs=[[{"secondary_y":True}]])
    fig.add_trace(go.Bar(x=yrs,y=revs,name="营业收入（亿）",marker_color=C["dark"],
        opacity=0.85,text=[f"{v:.0f}" if v else "" for v in revs],textfont_size=10,textposition="outside"),secondary_y=False)
    fig.add_trace(go.Scatter(x=yrs,y=profits,name="归母净利润（亿）",mode="lines+markers",
        line=dict(color=C["red"],width=2.5),marker_size=8),secondary_y=True)
    fig.update_layout(template=PLOTLY_TEMPLATE,title=dict(text="营业收入与归母净利润（2009-2025）",x=0.02,y=0.98,font_size=14),
        font=dict(family="Microsoft YaHei,PingFang SC,sans-serif",size=11,color="#1a1a1a"),
        height=380,margin=dict(l=55,r=55,t=80,b=50),hovermode="x unified",
        legend=dict(orientation="h",yanchor="bottom",y=1.05))
    fig.update_yaxes(title_text="营收（亿）",secondary_y=False)
    fig.update_yaxes(title_text="归母净利润（亿）",secondary_y=True)
    fig.add_hline(y=0,line_dash="solid",line_color="#ccc",line_width=1,secondary_y=True)
    return fig

def ch3_scenario_eps():
    """图表3: 三情景EPS预测 — 分组柱状图（视频研究建议：峰值PE取10-14x，预期管理）"""
    # 2025 实际 EPS（从财务数据直接取，不用模型算的 2.98）
    ACTUAL_2025_EPS = 2.88  # 155亿 / 54.7亿股

    yrs = [2026, 2027, 2028]
    yr_labels = ["2026E", "2027E", "2028E"]
    fig = go.Figure()

    colors_sc = {"上行": C["green"], "基准": C["midblue"], "下行": C["red"]}
    width = 0.25
    offsets = {"上行": -0.28, "基准": 0, "下行": 0.28}

    for sc in ["上行", "基准", "下行"]:
        eps_vals = [FORECAST[sc][yr]["eps"] for yr in yrs]
        fig.add_trace(go.Bar(
            x=yr_labels, y=eps_vals, name=sc,
            marker_color=colors_sc[sc], marker_line_color="white", marker_line_width=1,
            text=[f"{v:.2f}" for v in eps_vals], textfont_size=10, textposition="outside",
            width=width, offset=offsets[sc],
            hovertemplate=f"{sc}: %{{y:.2f}}元/股<extra></extra>"
        ))

    # 2025 实际 EPS 参考线（独立数据点，不属于预测）
    fig.add_hline(y=ACTUAL_2025_EPS, line_dash="dot", line_color="#7f8c8d", line_width=1.5,
        annotation=dict(text=f"2025实际 EPS={ACTUAL_2025_EPS}", font_size=10, font_color="#7f8c8d"))

    # 零线 + 8年均值线
    fig.add_hline(y=0, line_dash="solid", line_color="#ccc", line_width=1)
    fig.add_hline(y=AVG8_EPS, line_dash="dash", line_color=C["dark"],
        annotation=dict(text=f"8Y均值 EPS={AVG8_EPS:.2f}", font_size=10, font_color=C["dark"]))

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=dict(text="三种情景 EPS 预测（2026E-2028E）", x=0.02, y=0.98, font_size=14),
        font=dict(family="Microsoft YaHei,PingFang SC,sans-serif", size=11, color="#1a1a1a"),
        height=400, margin=dict(l=55, r=30, t=80, b=50), hovermode="x unified",
        yaxis_title="EPS（元/股）",
        legend=dict(orientation="h", yanchor="bottom", y=1.05),
        bargap=0.15, bargroupgap=0.1,
        plot_bgcolor="white",
    )
    return fig

def ch4_valuation_summary():
    """图表4: 市场验证估值汇总表（公平价值 + 2028 峰值预测）"""
    rows = [
        ["公平价值（周期均值PE）", f"AVG8_EPS {AVG8_EPS:.2f} × 成熟期PE {FAIR_PE['p25']:.1f}-{FAIR_PE['p75']:.1f}×",
         f"{FAIR_VALUE['low']:.0f}", f"{FAIR_VALUE['mid']:.0f}", f"{FAIR_VALUE['high']:.0f}"],
        ["2028 峰值·基准（PB模型）", f"BPS {PEAK_BPS['基准']:.1f} × PB {PEAK_PB_LO}-{PEAK_PB_HI}×",
         f"{PEAK_PRICE['基准'][0]:.0f}", f"{(PEAK_PRICE['基准'][0]+PEAK_PRICE['基准'][1])/2:.0f}", f"{PEAK_PRICE['基准'][1]:.0f}"],
        ["2028 峰值·上行（PB模型）", f"BPS {PEAK_BPS['上行']:.1f} × PB {PEAK_PB_LO}-{PEAK_PB_HI}×",
         f"{PEAK_PRICE['上行'][0]:.0f}", f"{(PEAK_PRICE['上行'][0]+PEAK_PRICE['上行'][1])/2:.0f}", f"{PEAK_PRICE['上行'][1]:.0f}"],
        ["2028 峰值·基准（周期PE交叉）", f"周期EPS {PEAK_CYC_EPS['基准']:.2f} × 23.8-25.8×",
         f"{PEAK_CYC_EPS['基准']*23.8:.0f}", f"{PEAK_CYC_EPS['基准']*24.8:.0f}", f"{PEAK_CYC_EPS['基准']*25.8:.0f}"],
    ]
    fig=go.Figure(data=[go.Table(
        header=dict(values=["<b>估值口径</b>","<b>核心参数</b>","<b>保守</b>","<b>中枢</b>","<b>乐观</b>"],
            fill_color=C["dark"],font=dict(color="white",size=12),height=34,align="center"),
        cells=dict(values=list(zip(*rows)),
            fill_color=[["white","#f8f9fa","#f8f9fa","#f8f9fa","#f0f4f8"]],
            font=dict(color="#1a1a1a",size=11),height=30,align="center"))])
    fig.update_layout(title=dict(text="市场验证估值汇总表（公平价值 + 2028 峰值预测）",x=0.02,y=0.98,font_size=14),
        font=dict(family="Microsoft YaHei,PingFang SC,sans-serif",size=11,color="#1a1a1a"),
        height=250,margin=dict(l=10,r=10,t=60,b=10))
    return fig

def ch5_pe_band():
    """图表5: PE Band 历史走势"""
    hist_yrs=sorted(HIST_PE.keys())
    actual_pe=[]
    for yr in hist_yrs:
        hp=HIST_PE[yr]
        if hp["is_loss"] or hp["pe"] is None: actual_pe.append(None)
        else: actual_pe.append(max(0.5,min(hp["pe"],80)))
    # 成熟期市场验证分布（2022+，56个月）：P10/P50/P90 = 19.1/23.9/29.3
    pe_lo,pe_mid,pe_hi=19,24,29
    x_left,x_right=hist_yrs[0]-0.5,hist_yrs[-1]+0.5
    fig=go.Figure()
    for y0,y1,color in [(0,pe_lo,"rgba(39,174,96,0.10)"),(pe_lo,pe_mid,"rgba(52,152,219,0.06)"),
        (pe_mid,pe_hi,"rgba(230,126,34,0.06)"),(pe_hi,55,"rgba(192,57,43,0.07)")]:
        fig.add_shape(type="rect",x0=x_left,x1=x_right,y0=y0,y1=y1,fillcolor=color,line_width=0,layer="below")
    for pe_val,color,label in [(pe_lo,C["green"],f"低估线 {pe_lo}×"),(pe_mid,C["orange"],f"合理线 {pe_mid}×"),(pe_hi,C["red"],f"高估线 {pe_hi}×")]:
        fig.add_shape(type="line",x0=x_left,x1=x_right,y0=pe_val,y1=pe_val,
            line=dict(color=color,width=1.5,dash="dash"),opacity=0.55)
        fig.add_annotation(x=hist_yrs[-1],y=pe_val,text=label,showarrow=False,
            font=dict(size=9,color=color),xanchor="right",yanchor="bottom")
    fig.add_trace(go.Scatter(x=hist_yrs,y=actual_pe,mode="lines+markers",
        line=dict(color=C["midblue"],width=2.8),marker=dict(size=11,color=C["midblue"],
        line=dict(color="white",width=2)),name="年末PE(TTM)",connectgaps=False))
    fig.add_trace(go.Scatter(x=hist_yrs,y=actual_pe,mode="lines",line=dict(color="rgba(0,0,0,0)",width=0),
        fill="tozeroy",fillcolor="rgba(41,128,185,0.07)",showlegend=False,connectgaps=False))
    # Current PE line
    fig.add_shape(type="line",x0=x_left,x1=x_right,y0=CURRENT_PE_CYCLE,y1=CURRENT_PE_CYCLE,
        line=dict(color=C["dark"],width=2),opacity=0.6)
    fig.add_annotation(x=hist_yrs[0],y=CURRENT_PE_CYCLE,text=f"当前周期PE {CURRENT_PE_CYCLE:.1f}×",
        showarrow=False,font=dict(size=10,color=C["dark"]),xanchor="left")
    for yr in hist_yrs:
        if yr in HIST_PE and HIST_PE[yr]["is_loss"]:
            fig.add_annotation(x=yr,y=2,text="<b>亏损</b>",showarrow=True,arrowhead=2,ay=-20,
                font=dict(size=10,color=C["red"]))
    fig.update_xaxes(tickmode="array",tickvals=hist_yrs,ticktext=[str(y) for y in hist_yrs],
        tickfont=dict(size=11,color="#333"),range=[x_left,x_right],
        showgrid=True,gridcolor="#f0f0f0",showline=True,linecolor="#ccc",linewidth=1,zeroline=False)
    fig.update_yaxes(title="PE 估值倍数",range=[0,50],dtick=5,tickfont=dict(size=11),
        showgrid=True,gridcolor="#f0f0f0",zeroline=False)
    fig.update_layout(template=PLOTLY_TEMPLATE,
        font=dict(family="Microsoft YaHei,PingFang SC,sans-serif",size=12,color="#1a1a1a"),
        title=dict(text="PE Band 历史估值区间（2018-2025）",x=0.02,y=0.98,font_size=14),
        height=420,legend=dict(orientation="h",yanchor="bottom",y=1.05),
        margin=dict(l=55,r=35,t=80,b=60),hovermode="x unified")
    return fig

def ch7_peak_scenarios():
    """图表7: 2028E 周期峰值预测 — 市场验证 PB 模型"""
    labels=["上行","基准","下行"]
    mids=[(PEAK_PRICE[sc][0]+PEAK_PRICE[sc][1])/2 for sc in labels]
    los=[PEAK_PRICE[sc][0] for sc in labels]
    his=[PEAK_PRICE[sc][1] for sc in labels]
    cyc_hi=[PEAK_CYC_EPS[sc]*25.8 for sc in labels]  # 周期PE峰值上限交叉（2025实测25.8×）
    fig=go.Figure()
    fig.add_trace(go.Bar(x=labels,y=mids,name="PB峰值模型（3.9-4.3×）",marker_color=C["midblue"],
        error_y=dict(type="data",symmetric=False,array=[h-m for m,h in zip(mids,his)],
                     arrayminus=[m-l for m,l in zip(mids,los)],color="#888",thickness=1.5,width=0.3),
        text=[f"{v:.0f}" for v in mids],textfont_size=12,textposition="outside"))
    fig.add_trace(go.Scatter(x=labels,y=cyc_hi,mode="markers",name="周期PE峰值交叉（25.8×）",
        marker=dict(color=C["orange"],size=10,symbol="diamond")))
    fig.add_hline(y=CURRENT_PRICE,line_dash="dash",line_color=C["red"],
        annotation=dict(text=f"当前股价 {CURRENT_PRICE}元",font_size=10,font_color=C["red"]))
    fig.add_hrect(y0=FAIR_VALUE["low"],y1=FAIR_VALUE["high"],fillcolor="rgba(46,204,113,0.08)",
        line_width=0,annotation=dict(text=f"公平价值带 {FAIR_VALUE['low']:.0f}-{FAIR_VALUE['high']:.0f}元",font_size=10))
    fig.update_layout(template=PLOTLY_TEMPLATE,
        title=dict(text="2028E 周期峰值股价预测 — 市场验证 PB 模型",x=0.02,y=0.98,font_size=14),
        font=dict(family="Microsoft YaHei,PingFang SC,sans-serif",size=11,color="#1a1a1a"),
        yaxis_title="峰值股价（元）",height=400,margin=dict(l=55,r=30,t=80,b=60),
        legend=dict(orientation="h",yanchor="bottom",y=1.05))
    return fig


# ==================== HTML 生成 ====================

def fmt_val(v): return f"{v:.0f}"
def fmt_p(v): return f"{v*100:.0f}%"

# Build scenario table rows
scenario_rows = ""
for sc in ["上行","基准","下行"]:
    sc_label = {"上行":"🟢 上行","基准":"🔵 基准","下行":"🔴 下行"}[sc]
    for yr in [2026,2027,2028]:
        f=FORECAST[sc][yr]
        eps_str=f"<td style='font-weight:600'>{f['eps']:.2f}</td>"
        if f['eps']<0: eps_str=f"<td style='color:#c0392b;font-weight:600'>{f['eps']:.2f}</td>"
        elif f['eps']>2: eps_str=f"<td style='color:#27ae60;font-weight:600'>{f['eps']:.2f}</td>"
        scenario_rows+=f"<tr><td>{sc_label}</td><td>{yr}E</td><td>{HOG_FORECAST.get(yr,'—')}万</td><td>{PRICE_SCENARIOS[sc][yr]}</td><td>{COST_SCENARIOS[sc][yr]}</td><td>{f['revenue']:.0f}</td>{eps_str}</tr>"

# Build risk matrix
risks_html="""<tr><td>猪价持续低迷</td><td style='color:#c0392b'>高</td><td>30%</td><td>去产能受阻、需求疲软，集团场硬扛不退</td><td>严控仓位、分批建仓，跟踪能繁月度变化</td></tr>
<tr><td>🆕 社交媒體/二次育肥干扰</td><td style='color:#e67e22'>中高</td><td>35%</td><td>抖音/快手博主鼓吹抄底→散养户压栏投机→人为延后出清</td><td>跟踪出栏均重+标肥价差，不信短期猪价反弹</td></tr>
<tr><td>饲料成本反弹</td><td style='color:#e67e22'>中</td><td>20%</td><td>南美天气、汇率贬值</td><td>跟踪豆粕/玉米期货，牧原低蛋白配方降依赖</td></tr>
<tr><td>疫情风险</td><td style='color:#e67e22'>中</td><td>15%</td><td>ASF或其他疫病复发</td><td>牧原全封闭模式天然防护</td></tr>
<tr><td>去化不彻底</td><td style='color:#f39c12'>中低</td><td>30%</td><td>PSY提升+头部扩产→供给始终不降→底部拉长</td><td>关注PSY效率提升对存栏下降的抵消</td></tr>
<tr><td>融资环境恶化</td><td style='color:#f39c12'>低</td><td>10%</td><td>信贷收紧、利率上行</td><td>OCF强劲、去杠杆趋势已现</td></tr>
<tr><td>管理层/治理风险</td><td style='color:#f39c12'>低</td><td>5%</td><td>关键人风险、战略失误</td><td>创始人深耕30年+二代接棒</td></tr>"""

# Summary cards
MACRO_CARDS = [
    ("GDP 同比", "4.70", "%"),
    ("制造业 PMI", "49.20", ""),
    ("CPI 同比", "1.00", "%"),
    ("LPR 1Y", "3.00", "%"),
    ("M2 同比", "8.00", "%"),
    ("生猪均价", "10.84", "元/kg"),
    ("能繁母猪", "3780", "万头"),
    ("猪粮比", "4.41", ""),
]
macro_cards_html = "".join(
    f'<div class="card"><div class="label">{label}</div><b>{val}</b><span class="unit">{unit}</span></div>'
    for label, val, unit in MACRO_CARDS)

# 2028 峰值情景表（市场验证 PB 主模型 + 交叉验证）
peak_scen_rows = ""
for sc in ["上行", "基准", "下行"]:
    lo, hi = PEAK_PRICE[sc]
    cyc_lo = PEAK_CYC_EPS[sc] * 23.8
    cyc_hi = PEAK_CYC_EPS[sc] * 25.8
    peak_scen_rows += (f"<tr><td><b>{sc}</b></td><td>{FORECAST[sc][2028]['eps']:.2f}</td>"
                       f"<td>{PEAK_BPS[sc]:.2f}</td><td>{PEAK_CYC_EPS[sc]:.2f}</td>"
                       f"<td style='font-weight:600'>{lo:.0f}-{hi:.0f}</td>"
                       f"<td>{cyc_lo:.0f}-{cyc_hi:.0f}</td></tr>")

# Charts dict
charts = {
    "ch1": ch1_revenue_profit(),
    "ch3": ch3_scenario_eps(),
    "ch4": ch4_valuation_summary(),
    "ch5": ch5_pe_band(),
    "ch7": ch7_peak_scenarios(),
    "ch8": ch8_sensitivity(),
}

def chart_div(chart_id, fig):
    json_str = fig.to_json()
    return f"""<div id="{chart_id}" class="plotly-graph-div" style="width:100%;"></div>
<script>window.PLOTLYENV=window.PLOTLYENV||{{}};if(document.getElementById("{chart_id}")){{Plotly.newPlot("{chart_id}",{json_str},{{responsive:true,displayModeBar:false}});}}</script>"""

all_charts_html = "\n".join(chart_div(cid, fig) for cid, fig in charts.items())

report_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>证券分析研究报告 — 牧原股份 (002714.SZ)</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;margin:0;background:#fff;color:#1a1a1a;font-size:15px;line-height:1.7}}
.header{{border-bottom:1px solid #e0e0e0;padding:36px 40px 28px;background:#fafafa}}
.header h1{{margin:0;font-size:24px;font-weight:600;letter-spacing:.5px}}
.header .sub{{color:#999;margin-top:8px;font-size:13px}}
.header .disclaimer{{color:#bbb;font-size:11px;margin-top:12px;line-height:1.5}}
.container{{max-width:900px;margin:0 auto;padding:32px 24px 80px}}
.section{{padding:0;margin:40px 0}}
.section h2{{font-size:17px;font-weight:600;padding-bottom:8px;border-bottom:2px solid #2c3e50;margin:0 0 16px;color:#2c3e50}}
.section h3{{font-size:14px;font-weight:600;color:#555;margin:18px 0 8px}}
.section p,.section li{{font-size:14px;line-height:1.8;color:#444}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0}}
th,td{{border-bottom:1px solid #eee;padding:8px 12px;text-align:left;vertical-align:top}}
th{{font-weight:500;color:#888;font-size:12px;letter-spacing:.3px}}
.source{{font-size:11px;color:#bbb;margin-bottom:8px}}
.box{{border-left:3px solid #3498db;padding:12px 18px;margin:16px 0;background:#f8fafc}}
.box-red{{border-left:3px solid #c0392b;padding:12px 18px;margin:16px 0;background:#fef5f5}}
.box-green{{border-left:3px solid #27ae60;padding:12px 18px;margin:16px 0;background:#f5fdf7}}
.box-orange{{border-left:3px solid #e67e22;padding:12px 18px;margin:16px 0;background:#fefaf5}}
.col2{{display:grid;grid-template-columns:1fr 1fr;gap:32px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1px;margin:0 0 24px;border:1px solid #e8e8e8}}
.card{{background:#fafafa;padding:14px 16px;text-align:center}}
.card .label{{font-size:11px;color:#999;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
.card b{{font-size:18px;font-weight:500;color:#1a1a1a}}
.card .unit{{font-size:10px;color:#aaa;margin-left:2px}}
.rec-badge{{display:inline-block;padding:3px 12px;border-radius:3px;font-size:13px;font-weight:600;letter-spacing:.5px}}
.rec-buy{{background:#27ae60;color:#fff}}
.rec-hold{{background:#f39c12;color:#fff}}
.rec-sell{{background:#c0392b;color:#fff}}
.page-break{{border:none;border-top:2px dashed #e0e0e0;margin:48px 0}}
@media(max-width:680px){{.col2,.cards{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="header">
  <h1>证券分析研究报告 — 牧原股份 (002714.SZ)</h1>
  <div class="sub">八步流程综合报告 · {TODAY_STR} · 数据截至2026年7月末 · 基于格雷厄姆/多德与胡克方法论</div>
  <div class="disclaimer">⚠ 免责声明：本报告仅供学习研究参考，不构成任何投资建议。任何投资决策应基于投资者自身的独立判断。<br>
  数据来源标注于各部分末尾，详细溯源见 data/sources/SOURCES.md。</div>
</div>
<div class="container">

<!-- ==================== 第一部分：概述 ==================== -->
<div class="section">
  <h2>一、概述</h2>

  <div class="box-green">
    <p style="margin:0">
      <b>投资建议：<span style="font-size:18px;color:#27ae60">增持</span></b> &nbsp;|&nbsp;
      <b>当前股价：<span style="font-size:18px">{CURRENT_PRICE} 元</span></b>（{TODAY_STR}）&nbsp;|&nbsp;
      <b>12个月目标价：<span style="font-size:18px;color:#2980b9">43 – 54 元</span></b>&nbsp;|&nbsp;
      <b>潜在上涨：<span style="color:#27ae60">+9% – +37%</span></b>
    </p>
  </div>

  <h3>估值摘要</h3>
  <p>采用<b>市场验证</b>的周期型公司估值框架（第 6 步估值报告 §4-§5）：完整周期平均盈利 × 成熟期市场实测倍数。旧四方法加权（DCF/相对/并购/LBO）未经市场检验，已删除。</p>
  <table>
    <tr><th>估值口径</th><th>核心参数</th><th>保守</th><th>中枢</th><th>乐观</th></tr>
    <tr><td>公平价值（周期均值PE）</td><td>AVG8_EPS {AVG8_EPS:.2f} × 成熟期PE {FAIR_PE['p25']:.1f}-{FAIR_PE['p75']:.1f}×</td><td>{fmt_val(FAIR_VALUE['low'])} 元</td><td style='font-weight:600'>{fmt_val(FAIR_VALUE['mid'])} 元</td><td>{fmt_val(FAIR_VALUE['high'])} 元</td></tr>
    <tr><td>2028 峰值·基准（PB模型）</td><td>BPS {PEAK_BPS['基准']:.1f} × PB {PEAK_PB_LO}-{PEAK_PB_HI}×</td><td>{fmt_val(PEAK_PRICE['基准'][0])} 元</td><td style='font-weight:600'>{fmt_val((PEAK_PRICE['基准'][0]+PEAK_PRICE['基准'][1])/2)} 元</td><td>{fmt_val(PEAK_PRICE['基准'][1])} 元</td></tr>
    <tr><td>2028 峰值·上行（PB模型）</td><td>BPS {PEAK_BPS['上行']:.1f} × PB {PEAK_PB_LO}-{PEAK_PB_HI}×</td><td>{fmt_val(PEAK_PRICE['上行'][0])} 元</td><td style='font-weight:600'>{fmt_val((PEAK_PRICE['上行'][0]+PEAK_PRICE['上行'][1])/2)} 元</td><td>{fmt_val(PEAK_PRICE['上行'][1])} 元</td></tr>
    <tr style='background:#f0f4f8'><td><b>交叉验证</b></td><td colspan='4'>周期PE 峰值 23.8-25.8× → 基准 36-39 元（下限）｜ 视频峰值利润法 60-100 元（区间参照，不用于计算）</td></tr>
  </table>
  <p style="font-size:12px;color:#888">当前价格 {CURRENT_PRICE} 元 &lt; 公平价值下沿 {fmt_val(FAIR_VALUE['low'])} 元 → 处于成熟期估值分布最低十分位，安全边际充分。</p>

  <h3>核心论点</h3>
  <ol>
    <li><b>成本护城河持续加深</b>：完全成本 2025 年末 11.3 元/kg、2026Q2 约 11.6 元/kg，为上市猪企最低，较行业平均低 1-2 元/kg——在周期低谷意味着比别人少亏、比别人多活。现金成本仅约 7.3-7.4 元/kg（扣除折旧），当前猪价 10.5 元仍高于现金成本 → 牧原不亏现金，可以硬扛。</li>
    <li><b>周期低谷已近底部</b>：能繁母猪 3780 万头（正常保有量 100.8%），产能去化加速（Q2 -3.2%）。猪粮比 4.41 处于重度亏损区间（<5:1），行业性亏损不可能无限持续。淘汰母猪折价率约 60%（vs 深度去化阈值 50%），去化仍在进行中。</li>
    <li><b>当前估值处于成熟期最低十分位</b>：周期 PE 19.3×（≈成熟期 P10 19.1×），市场验证的公平价值带 43-54 元，当前 39.3 元低于下沿——"模型合理 + 市场便宜"交汇。</li>
    <li><b>周期高峰期权价值显著</b>：市场验证的 PB 峰值模型（3.9-4.3×）显示 2028 周期峰值基准情景 66-73 元（+68%~+85%）、上行情景 87-96 元（+121%~+144%）。</li>
    <li><b>财务安全垫充足</b>：经营现金流 301 亿（2025），利息覆盖 7.2 倍，有息负债进入去杠杆通道——能安然度过周期底部。</li>
  </ol>

  <h3>主要风险</h3>
  <p>猪价持续低迷（30%）、社交媒体/二次育肥干扰（35%）、去化不彻底（30%）、饲料成本反弹（20%）、疫病复发（15%）、融资环境恶化（10%）、管理层风险（5%）。详见第八部分风险矩阵。</p>

  <p class="source">来源：第1-7步分析成果综合。估值参数详见 data/sources/SOURCES.md。</p>
</div>

<hr class="page-break">

<!-- ==================== 第二部分：宏观经济评述 ==================== -->
<div class="section">
  <h2>二、宏观经济评述</h2>
  <p class="source">来源：国家统计局、中国人民银行、农业农村部、海关总署、行情宝。完整数据溯源见第1步报告。</p>

  <div class="cards">{macro_cards_html}</div>

  <div class="box-red">
    <h3 style="margin-top:0">核心判断：短空长多，拐点待 Q4 确认</h3>
    <p style="margin:0">
      ① <b>产能去化加速但拐点未确认</b>：能繁母猪 2026Q2 末 3780 万头（同比 -6.5%、环比 -3.2%），为正常保有量 3750 万头的 100.8%，重回绿色区间上沿。<br>
      ② <b>猪价 7 月现首个回升信号</b>（6 月 9.57 → 7 月 10.84 元，环比 +13.3%），但仍处重度亏损区（猪粮比 4.41，预警线 5:1）。<br>
      ③ <b>成本端与融资端均处有利环境</b>：豆粕创两年新低（2818 元/吨）、人民币升值降低进口大豆成本、利率下行减轻财务负担。<br>
      ④ <b>宏观底 + 周期底双重确认尚需时间</b>：周期拐点时点需 2026Q4 前持续验证。
    </p>
  </div>

  <h3>关键宏观驱动因素</h3>
  <div class="col2">
    <div>
      <h3>供给端（核心）</h3>
      <ul>
        <li>能繁母猪存栏 → 领先 10 个月出栏量</li>
        <li>当前 3780 万头，同比 -6.5%，去化方向确定</li>
        <li>但绝对值仍接近正常保有量上限</li>
        <li>规模化率提升（73%）改变周期斜率——去化更慢、底部更长</li>
      </ul>
    </div>
    <div>
      <h3>成本端 + 融资端</h3>
      <ul>
        <li>玉米 ~2380 元/吨、豆粕 2818（两年新低）</li>
        <li>人民币汇率升值 3.4% → 进口大豆成本降低</li>
        <li>LPR 1Y=3.00%，5Y=3.50%——历史低位</li>
        <li>M2 同比 8.0%——流动性充裕</li>
      </ul>
    </div>
  </div>
  <div class="col2">
    <div>
      <h3>需求端</h3>
      <ul>
        <li>GDP ~4.7%——猪肉消费弹性低，总量平稳</li>
        <li>CPI ~1.0%——低通胀环境压制猪价上行空间</li>
        <li>猪肉进口 2026H1 同比 -12%——外部竞争压力减轻</li>
      </ul>
    </div>
    <div>
      <h3>对牧原的具体影响</h3>
      <ul>
        <li>饲料成本下行 → 放大成本优势（比别人赚得更多 / 亏得更少）</li>
        <li>利率下行 → 财务费用降低（有息负债 ~570 亿，每降 0.5pp 省 ~2.9 亿/年）</li>
        <li>进口减少 → 国内供给压力减轻</li>
      </ul>
    </div>
  </div>

  <p class="source">数据来源：国家统计局（GDP/CPI/PPI/能繁）、中国人民银行（LPR/M2/汇率）、海关总署（进口）、行情宝（猪价）。详见第1步报告与 data/sources/ 目录。</p>
</div>

<hr class="page-break">

<!-- ==================== 第三部分：相关股票市场前景 ==================== -->
<div class="section">
  <h2>三、相关股票市场前景</h2>

  <p>养猪板块属于<b>农林牧渔</b>行业，在 A 股中属于<b>中小市值防御性+周期性板块</b>。当前板块核心特征：</p>

  <div class="col2">
    <div>
      <h3>板块表现</h3>
      <ul>
        <li>2025年生猪养殖指数整体下行——猪价下行周期压制板块情绪</li>
        <li>板块内部分化严重：成本低的龙头（牧原）vs 成本高的跟随者（正邦）走势分化</li>
        <li>资金对养猪股的定价已从"猪价预期"转向"成本差异+资产负债表质量"</li>
      </ul>
    </div>
    <div>
      <h3>估值周期</h3>
      <ul>
        <li>养猪股 PE 在猪价低谷期"看起来贵"（EPS 低），在猪价高峰期"看起来便宜"（EPS 高）</li>
        <li>这正是周期股投资的本质：<b>高 PE 买入、低 PE 卖出</b></li>
        <li>当前牧原周期 PE=19.3×——处于2021年以来最低水平</li>
        <li>如果周期规律成立，当前是"高PE买入"阶段</li>
      </ul>
    </div>
  </div>

  <div class="box">
    <p style="margin:0"><b>关键市场信号：</b>生猪期货 LH2701=12.70 元/kg（2026-07-28）——期货市场用"真金白银"投票，预期 2027 年 1 月猪价回升至 ~12.7 元/kg。这是目前可见的、最可靠的市场一致预期。但这仍低于牧原成本（11.0-11.5 元/kg 可覆盖、但盈利微薄），意味着期货市场 <b>尚未定价周期大幅反转</b>——如果反转到来，股价弹性将较大。</p>
  </div>

  <p class="source">来源：板块分析基于 Wind/东方财富行业指数观察，期货数据来自大连商品交易所 2026-07-28 收盘价。</p>
</div>

<hr class="page-break">

<!-- ==================== 第四部分：公司及其业务评述 ==================== -->
<div class="section">
  <h2>四、公司及其业务评述</h2>

  <h3>4.1 业务模式</h3>
  <p>牧原股份是中国最大的生猪养殖企业，2025 年出栏 <b>7,798 万头</b>（全国出栏占比 10.8%），采用<b>"自繁自养"全链条一体化模式</b>——从饲料加工、种猪育种、商品猪养殖到屠宰加工全程自主掌控。</p>

  <table>
    <tr><th></th><th>牧原模式（自繁自养）</th><th>温氏模式（公司+农户）</th></tr>
    <tr><td>资产轻重</td><td>重资产（自有猪舍）</td><td>轻资产（农户提供猪舍）</td></tr>
    <tr><td>成本控制</td><td style='color:#27ae60'>精细化管理，成本更低</td><td>受农户执行差异拖累，成本偏高</td></tr>
    <tr><td>扩张速度</td><td>慢（需要建猪场）</td><td>快（签约农户即可）</td></tr>
    <tr><td>生物安全</td><td style='color:#27ae60'>全封闭，易统一管控</td><td>分散，难统一标准</td></tr>
    <tr><td>代表企业</td><td style='font-weight:600'>牧原股份</td><td>温氏股份</td></tr>
  </table>

  <h3>4.2 核心竞争优势</h3>
  <div class="box-green">
    <p style="margin:0">
      <b>成本领先是第一护城河。</b>牧原完全成本 11.3 元/kg 为上市猪企最低（温氏 12.2、神农 12.5、新希望 12.7、正邦 13.3）。<br>
      成本优势来源：① 自繁自养全链条管控；② 饲料配方自主（"玉米+豆粕"替代配方降本）；③ 智能猪舍设计（通风/温控/饲喂）；④ 育种体系（种猪性能行业领先）；⑤ 规模效应（采购议价能力）。
    </p>
  </div>

  <h3>4.3 产能规模</h3>
  <table>
    <tr><th>指标</th><th>数据</th><th>说明</th></tr>
    <tr><td>年产能</td><td style='font-weight:600'>9,000 万头</td><td>已建成猪舍产能上限（2025年末）</td></tr>
    <tr><td>能繁母猪</td><td style='font-weight:600'>323 万头</td><td>2025年末存栏，可支撑年出栏 ~7,500 万头</td></tr>
    <tr><td>2025 实际出栏</td><td style='font-weight:600'>7,798 万头</td><td>产能利用率 ~87%——仍有一定释放空间但增速放缓</td></tr>
    <tr><td>2026H1 出栏</td><td style='font-weight:600'>3,862 万头</td><td>同比 +7.5%，全年预计 8,100 万头</td></tr>
    <tr><td>屠宰产能</td><td style='font-weight:600'>~2,000 万头/年</td><td>向下游延伸——从"卖猪"到"卖肉"</td></tr>
  </table>

  <h3>4.4 管理层评估</h3>
  <ul>
    <li><b>创始人秦英林</b>：深耕养猪 30 年+，技术出身，行业理解深厚。持有公司约 38% 股份（含一致行动人），利益高度一致。</li>
    <li><b>战略定力</b>：逆周期扩张的历史证明——2019-2021 年行业最困难时大规模扩产，奠定了今天的龙头地位。</li>
    <li><b>当前战略</b>：从"规模扩张"转向"质量提升"——降本增效、去杠杆、向下游延伸。</li>
    <li><b>⚠ 二代接棒过渡期风险</b>：秦牧原（32岁）2024年起担任副总裁，核心高管团队年轻化（平均不到35岁）。接棒时点恰逢深度亏损期——考验年轻管理层独立应对危机的能力。历史上有不少企业在代际交接期间出现战略失误。治理机制正从"创始人决策"向"系统化治理"转型中，尚需时间验证。</li>
  </ul>

  <p class="source">来源：公司年报（2024-2025）、投资者交流纪要、猪易网/博亚和讯行业数据。详见第3步公司分析报告。</p>
</div>

<hr class="page-break">

<!-- ==================== 第五部分：财务分析 ==================== -->
<div class="section">
  <h2>五、财务分析</h2>

  <h3>5.1 营收与利润趋势</h3>
  {chart_div("ch1", charts["ch1"])}
  <p>牧原营收从 2009 年的 4 亿增长至 2025 年的 1,441 亿，增长超 360 倍。利润剧烈波动——这是周期型公司的本质特征：<b>利润波动不代表经营有问题，而是行业特性</b>。</p>
  <p><b>2026H1 最新</b>：猪价 10.5 元/kg 远低于完全成本 11.6 元/kg，头均亏损约 121 元，牧原 Q1 亏损 12.15 亿（温氏 Q1 亏损 10.70 亿），H1 预估亏损 57-67 亿。但经营现金流保持正值——亏利润不亏现金。</p>

  <h3>5.2 关键财务指标</h3>
  <table>
    <tr><th>指标</th><th>2025</th><th>2024</th><th>2023</th><th>周期均值 (2018-25)</th><th>近5年均值</th></tr>
    <tr><td>营业收入（亿）</td><td>1,441</td><td>1,379</td><td>1,109</td><td>—</td><td>—</td></tr>
    <tr><td>归母净利润（亿）</td><td>155</td><td>179</td><td>-43</td><td style='font-weight:600'>104</td><td style='font-weight:600'>99</td></tr>
    <tr><td>毛利率 %</td><td>17.8</td><td>19.2</td><td>3.1</td><td>22.0</td><td>14.9</td></tr>
    <tr><td>净利率 %</td><td>11.0</td><td>13.0</td><td>-3.8</td><td>10.5</td><td>6.2</td></tr>
    <tr><td>ROE %</td><td>20.6</td><td>26.8</td><td>-6.4</td><td style='font-weight:600'>23.2</td><td>14.1</td></tr>
    <tr><td>资产负债率 %</td><td>54.2</td><td>57.4</td><td>61.8</td><td>—</td><td>—</td></tr>
    <tr><td>经营现金流（亿）</td><td style='color:#27ae60'>301</td><td style='color:#27ae60'>342</td><td>161</td><td>—</td><td>—</td></tr>
    <tr><td>利息覆盖倍数</td><td>7.2</td><td>8.9</td><td>-0.6</td><td>—</td><td>—</td></tr>
    <tr><td>EPS（元）</td><td>2.88</td><td>3.31</td><td>-0.78</td><td style='font-weight:600'>2.04</td><td style='font-weight:600'>1.83</td></tr>
  </table>

  <div class="box">
    <p style="margin:0"><b>公司分类：周期型公司。</b>盈利高度依赖猪价周期，估值不能使用当年利润，而应使用<b>完整周期平均盈利</b>（8 年均 EPS = 2.04 元）。当前周期 PE = 39.3/2.04 = <b>19.3×</b>。</p>
  </div>

  <h3>5.3 会计质量审查</h3>
  <ul>
    <li><b>生物资产计价</b>：消耗性生物资产按成本计量（而非公允价值），且周转快（~6个月出栏），减值风险可控。</li>
    <li><b>折旧政策</b>：猪舍按 10-20 年直线折旧——与行业一致，但猪舍实际使用寿命可能更长（隐含资产"隐藏价值"）。</li>
    <li><b>OCF/净利润 = 1.9（2025）</b>——利润质量高，"银行里的现金难以造假"。</li>
    <li><b>审计意见</b>：标准无保留意见（中兴华会计师事务所）。</li>
  </ul>

  <p class="source">来源：牧原股份历年年报（2009-2025），通过 akshare 东方财富接口拉取。详见第4步财务分析报告。</p>
</div>

<hr class="page-break">

<!-- ==================== 第六部分：财务预测 ==================== -->
<div class="section">
  <h2>六、财务预测</h2>

  <h3>6.1 核心假设</h3>
  <div class="box">
    <p style="margin:0">
      <b>方法论</b>：猪价驱动模型——出栏量 × 均价 → 营收 → 毛利 → EBIT → EPS。预测期 2026E-2028E，三种情景（Hooke 七步骤框架）。<br>
      <b>预测锚定</b>：① 能繁母猪产能去化趋势（领先指标）；② 生猪期货远期曲线（市场定价）；③ 牧原降本趋势（2025=12.0 → 2026H1=11.6 → 2028E=11.0）。
    </p>
  </div>
  <table>
    <tr><th>参数</th><th>2025（实际）</th><th>2026E</th><th>2027E</th><th>2028E</th><th>核心依据</th></tr>
    <tr><td>出栏量（万头）</td><td>7,798</td><td>8,100</td><td>8,300</td><td>8,500</td><td>产能上限 9,000 万头 + 战略降速</td></tr>
    <tr><td>猪价 — 上行</td><td>14.4</td><td>11.0</td><td>14.0</td><td>15.5</td><td>需求意外 + 供给快速去化</td></tr>
    <tr><td>猪价 — 基准</td><td>14.4</td><td style='color:#c0392b'>10.5</td><td>12.5</td><td>13.5</td><td>产能缓降 + 季节性复苏</td></tr>
    <tr><td>猪价 — 下行</td><td>14.4</td><td style='color:#c0392b'>10.0</td><td>11.0</td><td>11.5</td><td>去化停滞 + 需求疲软</td></tr>
    <tr><td>完全成本（元/kg）</td><td>12.0</td><td>11.5</td><td>11.3</td><td>11.0</td><td>降本趋势外推 + 饲料下行</td></tr>
  </table>

  <h3>6.2 三情景预测</h3>
  {chart_div("ch3", charts["ch3"])}
  <table>
    <tr><th>情景</th><th>年份</th><th>出栏(万头)</th><th>猪价</th><th>成本</th><th>营收(亿)</th><th>EPS(元)</th></tr>
    {scenario_rows}
  </table>

  <div class="box-orange">
    <p style="margin:0"><b>期货市场验证</b>：大商所 LH 合约（2026-08-03 收盘）——LH2701=12.32、LH2705=13.00 元/kg。期货隐含 2027H1 均价 ≈ 12.3-12.9 元/kg，偏向<b>"基准偏上"</b>情景。期货市场提供了相对独立的定价锚点。</p>
  </div>

  <p class="source">来源：预测模型基于第4步财务数据 + 公司出栏/成本公告 + 国家统计局能繁数据 + 大商所期货行情。详见第5步财务预测报告。</p>
</div>

<hr class="page-break">

<!-- ==================== 第七部分：评估方法的运用 ==================== -->
<div class="section">
  <h2>七、评估方法的运用</h2>

  <h3>7.1 估值模型选择 — 成熟期市场验证（第 6 步估值报告 §4）</h3>
  <p>用成熟期（2022-01 至今，56 个月）真实市场数据对比四种候选模型，选出市场实际使用的估值锚。旧框架的 DCF/相对价值/并购/LBO 加权法未经市场检验，已全部弃用：</p>
  <table>
    <tr><th>候选模型</th><th>成熟期分布（P25-P75）</th><th>稳定性 IQR/中位</th><th>拟合误差 MAD</th><th>全程可定义</th><th>判定</th></tr>
    <tr><td>周期均值PE（股价/8Y均值EPS）</td><td>21.1-26.4×</td><td>0.19-0.22</td><td>8.7-11.9%</td><td>✅</td><td style='font-weight:600'>公平价值主模型</td></tr>
    <tr><td>PB（股价/BPS）</td><td>3.1-3.9×</td><td>0.23-0.24</td><td>10.5-12.0%</td><td>✅</td><td style='font-weight:600'>峰值预测主模型</td></tr>
    <tr><td>PS（市值/TTM营收）</td><td>1.7-2.1×</td><td>0.22</td><td>11.3%</td><td>✅</td><td>旁证</td></tr>
    <tr><td>PE(TTM)</td><td>盈利期 12.5-21.3×</td><td>4.25</td><td>亏损期无定义</td><td>❌</td><td style='color:#c0392b'>否决</td></tr>
  </table>

  <h3>7.2 公平价值 — 周期均值PE（市场验证）</h3>
  <p>使用完整周期平均盈利（8Y EPS = {AVG8_EPS:.2f} 元），而非当年利润——周期型公司估值的基本纪律：</p>
  <div class="box">
    <p style="margin:0"><b>市场验证的公平价值（成熟期 2022+，56 个月实测）：</b><br>
    成熟期市场对牧原周期均值 PE 的实际支付区间：P25-P75 = 21.1-26.4×（P50 23.9×、P10-P90 19.1-29.3×）——旧假设 15-22× 与视频的 12-16× 均低于市场真实水平，已弃用。<br>
    公平价值 = AVG8_EPS {AVG8_EPS:.2f} × 21.1-26.4× = <b>{fmt_val(FAIR_VALUE['low'])}-{fmt_val(FAIR_VALUE['high'])} 元</b>（中枢 {fmt_val(FAIR_VALUE['mid'])} 元）。<br>
    当前周期 PE = 19.3× ≈ 成熟期 P10（19.1×）——<b>当前价格处于成熟期估值分布最低十分位，低于公平价值下沿</b>。</p>
  </div>

  <h3>7.3 PE Band 历史估值区间</h3>
  {chart_div("ch5", charts["ch5"])}
  <p>2023 年（亏损年份）PE 无意义（折线断开）。当前周期 PE=19.3×——处于成熟期分布<b>最低十分位（P10≈19.1×）</b>。</p>

  <h3>7.4 交叉验证（不重新计算，仅参照）</h3>
  <div class="box">
    <p style="margin:0"><b>① 周期PE 峰值（市场验证下限）</b>：2028E 周期均值 EPS × 23.8-25.8×（2025 峰值实测）→ 基准 36-39 元、上行 52-56 元——因 8 年窗口吞入 2026 年创纪录亏损而偏低，仅作下限参照。<br>
    <b>② 视频峰值利润法（60-100 元）</b>：与本项目 PB 峰值预测（66-96 元）区间基本一致，但其"峰值 EPS × PE"存在双重周期化问题、倍数未经市场校准，仅作定性参照，不用于本项目计算。<br>
    <b>③ 峰值 EPS × PE 模型已否决</b>：周期股峰值盈利对应的 PE 天然被压缩（2025 峰值 trailing PE 仅 21×），且上行情景隐含 ROE 28% 超成熟期历史（20-25%），该口径会系统性高估。</p>
  </div>

  <h3>7.5 市场验证估值汇总</h3>
  {chart_div("ch4", charts["ch4"])}

  <h3>7.6 周期高峰估值 — 2028 峰值预测（市场验证）</h3>
  <p>公平价值回答"现在值多少钱"，峰值预测回答"周期反转后能涨到多少"。<b>主模型：PB × 成熟期峰值倍数（3.9-4.3×，校准自 2025 年峰值实测 4.25×）</b>，作用于财务预测滚动出的 2028E BPS。</p>
  <table>
    <tr><th>情景</th><th>2028E EPS</th><th>2028E BPS</th><th>2028E 周期EPS(8Y)</th><th>PB峰值价（主）</th><th>周期PE峰值交叉（下限）</th></tr>
    {peak_scen_rows}
  </table>
  {chart_div("ch7", charts["ch7"])}
  <p style="font-size:12px;color:#888">PB 峰值模型：2025 年成熟期峰值实测 PB 4.25×（年度高点 59.68/BPS 14.04）与 3.96×（2025-08 月度收盘 55.0/BPS 13.89）→ 取 3.9-4.3×。周期PE 峰值交叉 = 2028E 周期均值 EPS × 23.8-25.8×。</p>

  <h3>7.7 历史低谷 PE 验证</h3>
  <div class="box-red">
    <p style="margin:0">
      <b>市场验证交叉检验：</b><br>
      ① 公平价值（周期均值PE 21-26×）= <b>43-54 元</b> → 当前 39.3 元 = <b style="color:#27ae60">低于下沿约 -9%，市场略低估</b><br>
      ② 当前周期 PE 19.3× ≈ 成熟期 P10（19.1×）= <b style="color:#c0392b">市场定价处于成熟期最低十分位</b><br>
      ③ 期货市场隐含 2027H1 ≈ 12.3-12.9 元/kg → 偏向基准偏上 = <b>复苏预期温和，尚未定价反转</b><br>
      ④ PE 倍数争议已由市场数据裁决：成熟期市场实际支付 21-26×（P25-P75），视频的 10× 与旧假设 12-16× 均被证伪——市场从未在成熟期用 12-16× 定价牧原。<br>
      <b>综合：当前价格低于市场验证的公平价值下沿，处于成熟期分布最低十分位——安全边际较充分，适合分批建仓；2028 周期峰值（基准 66-73 / 上行 87-96 元）提供上行弹性。</b>
    </p>
  </div>

  <h3>7.8 边际成本定价：猪价的"引力锚"</h3>
  <div class="box">
    <p style="margin:0"><b>核心理论（源自微观经济学 + B站视频研究的实地调研）</b>：<br>
    猪价不是由行业平均成本决定的，也不是由最低成本企业（如牧原）决定的，而是由<b>满足需求所需最后一批产能的边际成本</b>决定的。换句话说——市场需要的最后一头猪，是由成本最高的那批养殖户生产出来的，他们的成本才是猪价的长期均衡锚。</p>
  </div>
  <div class="col2">
    <div>
      <h3>边际成本推导</h3>
      <table>
        <tr><th>产能层级</th><th>完全成本</th><th>占供给比</th><th>当前状态</th></tr>
        <tr><td>牧原（成本最低）</td><td style='color:#27ae60'>11.3-11.6</td><td>~11%</td><td>盈利（现金层面）</td></tr>
        <tr><td>集团场（温氏/新希望等）</td><td>12.0-13.0</td><td>~30%</td><td>亏损</td></tr>
        <tr><td>规模场</td><td>13.0-14.5</td><td>~30%</td><td>深度亏损</td></tr>
        <tr><td style='color:#c0392b'><b>边际产能（散户）</b></td><td style='color:#c0392b;font-weight:600'>~14.7</td><td style='color:#c0392b'><b>最后10%</b></td><td style='color:#c0392b'>严重失血→退出</td></tr>
      </table>
    </div>
    <div>
      <h3>均衡猪价推导</h3>
      <p>边际成本 14.7 元/kg + 合理利润（吸引其继续养殖）→ 长期均衡猪价 ≈ <b style='font-size:18px;color:#2980b9'>15 元/kg</b></p>
      <ul>
        <li><b>高于 15 元</b>：边际产能盈利→扩产→供给增加→猪价回落</li>
        <li><b>低于 15 元</b>：边际产能亏损→退出→供给减少→猪价回升</li>
        <li><b>当前 10.5 元</b>：远低于均衡锚 → 去化是确定性的方向</li>
      </ul>
      <p style="font-size:12px;color:#888">数据来源：视频UP主实地调研。边际成本数据会随饲料价格/防疫成本/PSY变化而动态调整，需持续跟踪。</p>
    </div>
  </div>
  <div class="box-orange">
    <p style="margin:0"><b>⚠ 均衡价非精确值</b>：15 元是基于当前饲料/防疫/PSY 条件的估算。随着散户加速退出（边际供给者变为规模场）、PSY 提升、饲料成本下行，长期均衡价可能缓慢下移至 13.5-14.5 元/kg。但至少未来 1-2 年内，均衡锚显著高于当前猪价——<b>回归引力持续存在</b>。</p>
  </div>

  <h3>7.9 利润敏感性矩阵</h3>
  <p>基于简化利润模型：<b>净利润 = (猪价 − 完全成本) × 均重 × 出栏量</b>。以下两张热力图揭示猪价、出栏量、成本三变量对利润的交互影响：</p>
  {chart_div("ch8", charts["ch8"])}

  <div class="box-green">
    <p style="margin:0"><b>敏感性速算（源自视频研究）：</b><br>
    ① <b>猪价每变动 ±1 元/kg</b> → 净利润变动 <b>±100 亿</b>（在 8000 万头出栏下）<br>
    ② <b>成本每变动 ±0.1 元/kg</b> → 净利润变动 <b>±10 亿</b><br>
    ③ <b>出栏量每变动 ±500 万头</b> → 净利润变动 ±(猪价-成本)×125×500/10000<br>
    三个杠杆中，<b>猪价是决定性变量</b>——成本管理和出栏增长是"加分项"，但猪价方向决定了利润的<b>正负号</b>。</p>
  </div>
  <p style="font-size:12px;color:#888">上表为简化模型（不考虑屠宰、饲料、非 hog 业务、利息、税）。实际 EPS 需通过完整财务模型导出（见 §6.2）。</p>

  <h3>7.10 峰值利润估值法（视频方法交叉验证）</h3>
  <p>B站深度分析视频用「峰值利润 × PE 10-15×」估算周期回归价值 <b>60-100 元</b>。本项目<b>不采用该模型计算</b>（"峰值 EPS × PE"存在双重周期化问题，且倍数未经市场校准），仅作为定性参照——其 60-100 元区间与市场验证的 PB 峰值预测（基准 66-73 / 上行 87-96 元）基本一致，互相印证"周期反转后股价显著高于当前"的判断。</p>

  <div class="box">
    <p style="margin:0"><b>两套方法的关系——互补而非矛盾：</b><br>
    ① <b>周期均值法（项目主框架，市场验证）</b>：AVG8_EPS 2.04 × 成熟期 PE 21-26× → 公平价值 <b>43-54 元</b>。这是"正常化"价值，已内嵌所有低谷年份。<br>
    ② <b>峰值预测（项目主模型，市场验证）</b>：PB 3.9-4.3× × 2028E BPS → 基准 <b>66-73 元</b> / 上行 <b>87-96 元</b>。这回答"周期回归后能涨到多少"。<br>
    ③ <b>视频峰值利润法</b>（峰值利润 × PE 10-15× → 60-100 元）与项目 PB 峰值预测（66-96 元）区间基本一致，但视频倍数未经市场校准。<br>
    ④ <b>公平价值 43-54 元到峰值 66-96 元的差距</b> ≈ +50%~+120%——这正是周期股投资的本质：<b>在周期底部以低于正常化价值的价格买入，等待周期回归后获利</b>。</p>
  </div>

  <p class="source">来源：边际成本数据源自B站UP主实地调研（2026年中），敏感性模型为简化公式。峰值利润法源自B站视频研究（BV1vrNR6hEmL）。详见 reports/牧原深度分析估值对比.md。</p>
</div>

<hr class="page-break">

<!-- ==================== 第八部分：投资建议 ==================== -->
<div class="section">
  <h2>八、投资建议</h2>

  <h3>8.1 投资推荐</h3>
  <div class="box-green">
    <p style="margin:0">
      <b>评级：<span style="font-size:20px">增持</span></b><br>
      <b>当前股价：</b>{CURRENT_PRICE} 元（{TODAY_STR}）<br>
      <b>12 个月目标价：43 – 54 元</b>（潜在上涨 +9% – +37%）
      <span style="font-size:12px;color:#888;">（注：目标价基于成熟期市场验证框架——周期均值 PE 21-26× × AVG8_EPS 2.04。旧四方法加权与 12-16× 等主观倍数未经市场检验，已弃用。详见第七部分）</span><br>
      <b>目标价推导：</b>成熟期公平价值带 43-54 元（周期均值 PE 21.1-26.4× × 2.04，中枢约 49 元）→ <b>综合目标区间 43-54 元</b><br>
      <b>情景分析：</b>若猪价持续低迷（下行情景，概率 20%）→ 2028E BPS 10.59 × PB 3.0-3.5 = 32-37 元；若温和复苏（基准，概率 50%）→ 公平价值 43-54 元、2028 峰值 66-73 元；若强反转（上行，概率 30%）→ 2028 峰值 87-96 元。当前 39.3 元低于公平价值下沿——安全边际较充分，建议分批建仓。</p>
  </div>
    </p>
  </div>

  <h3>8.2 核心论点（投资逻辑链）</h3>
  <ol>
    <li><b>周期位置有利</b>：猪价处于重度亏损区（猪粮比 4.41），能繁母猪去化方向确定（Q2 -3.2%）。边际成本定价框架显示当前猪价 10.5 元远低于均衡锚 15 元——回归引力持续存在。周期型公司的买入时机往往在最悲观时——但需接受底部可能进一步拉长（集团场主导的周期变形）。</li>
    <li><b>成本护城河在低谷期被放大</b>：当全行业亏损时，成本最低者活到最后——现金成本仅 7.3 元/kg vs 猪价 10.5 元 → 牧原不亏现金、可硬扛；竞争对手的现金在流失。敏感性矩阵显示：猪价每涨 1 元，利润增 100 亿——成本优势的杠杆效应在周期上行时会被极度放大。2026 年行业性亏损将是牧原市场份额进一步提升的窗口。</li>
    <li><b>估值保护充分</b>：19.3× 周期 PE ≈ 成熟期 P10（最低十分位），公平价值 43-54 元、当前价格低于下沿约 9%。市场验证的峰值预测（基准 66-73 / 上行 87-96 元）显示当前价格反映的是周期底部定价，尚未计入反转预期。</li>
    <li><b>催化剂逐渐积累</b>：能繁持续去化 → 淘汰母猪折价率下降 → 猪价拐点 → 盈利反转——未来 6-12 个月多条催化剂可能兑现。关键跟踪指标：能繁月度变化 + 淘汰母猪折价率。</li>
    <li><b>周期高峰期权存在但需管理预期</b>：市场验证的 PB 峰值模型给出 2028 峰值基准 66-73 元、上行 87-96 元。需注意：本轮反转高度大概率低于上一轮超级周期（集团场产能弹性大，猪价反弹后供给恢复快），且峰值 PB 存在递减趋势（2022 过渡期 5.1× → 2025 成熟期 4.25×）——保守取基准情景 66-73 元作为峰值参考。</li>
  </ol>

  <h3>8.3 催化剂</h3>
  <div class="col2">
    <div>
      <h3>短期催化剂（0-6 个月）</h3>
      <ul>
        <li>2026Q3 能繁母猪进一步去化数据</li>
        <li>猪价季节性反弹（秋冬消费旺季）</li>
        <li>2026 半年报/三季报——市场检验公司成本控制进展</li>
        <li>生猪期货 LH 合约价格变动——反映市场预期调整</li>
      </ul>
    </div>
    <div>
      <h3>中期催化剂（6-12 个月）</h3>
      <ul>
        <li>能繁母猪降至 3700 万头以下（正式跌破正常保有量）</li>
        <li>2027 年猪价拐点确认——周期反转信号</li>
        <li>公司盈利由负转正——EPS 从亏损到微利</li>
        <li>去杠杆加速——有息负债降至 500 亿以下</li>
      </ul>
    </div>
  </div>

  <h3>8.4 风险矩阵</h3>
  <table>
    <tr><th>风险因素</th><th>影响程度</th><th>概率</th><th>触发条件</th><th>应对措施</th></tr>
    {risks_html}
  </table>

  <h3>8.5 操作建议</h3>
  <table>
    <tr><th>操作</th><th>价格区间</th><th>仓位建议</th><th>逻辑</th></tr>
    <tr><td style='color:#27ae60'>✓ 分批建仓</td><td>35-40 元</td><td>达到目标仓位的 50%</td><td>低于公平价值下沿 43 元——估值保护充分</td></tr>
    <tr><td style='color:#2980b9'>✓ 加仓</td><td>30-35 元</td><td>加至目标仓位的 80%</td><td>猪价进一步下跌导致市场恐慌——但去化逻辑反而加强</td></tr>
    <tr><td style='color:#f39c12'>— 持有</td><td>40-55 元</td><td>维持仓位</td><td>处于公平价值带（43-54 元）内，等待催化剂兑现</td></tr>
    <tr><td style='color:#e67e22'>⚠ 减仓</td><td>55-70 元</td><td>减至 50%</td><td>接近基准周期峰值（66-73 元）——周期股应在高估值时兑现</td></tr>
    <tr><td style='color:#c0392b'>✗ 止损</td><td>&lt; 25 元</td><td>清仓</td><td>若跌破意味着猪周期逻辑或公司基本面出现结构性恶化</td></tr>
  </table>

  <div class="box">
    <p style="margin:0"><b>持仓策略说明：</b>周期型公司的投资不适合"一次性建仓"——最佳策略是<b>分批、反向、有纪律</b>。在周期低谷（高 PE、低盈利）逐步买入，在周期高峰（低 PE、高盈利）逐步卖出。当前处于"高 PE 买入"窗口——如果相信周期必然回归，这个窗口不会永远敞开。</p>
  </div>

  <p class="source">投资建议综合前 7 步分析成果，使用多重交叉验证降低单一方法偏差。所有数据来源详见各分步报告及 data/sources/SOURCES.md。</p>
</div>

<hr class="page-break">

<!-- ==================== 附录：数据来源与方法论 ==================== -->
<div class="section">
  <h2>附录：关键数据来源与方法论声明</h2>

  <h3>数据来源</h3>
  <ul>
    <li><b>财务数据</b>：牧原股份历年年报（2009-2025），通过 akshare 东方财富接口拉取，缓存于 data/ 目录</li>
    <li><b>宏观数据</b>：国家统计局（GDP/CPI/PPI/能繁母猪）、中国人民银行（LPR/M2/汇率）、海关总署（进口数据）</li>
    <li><b>行业数据</b>：行情宝/搜猪网（猪价）、农业农村部（产能调控）、猪易网/博亚和讯（成本对比）</li>
    <li><b>期货数据</b>：大连商品交易所 LH 合约（2026-07-28 收盘价）</li>
    <li><b>同行行情</b>：亿牛网（eniu.com），2026-07 手工采集（本机 SSL 阻断）</li>
  </ul>

  <h3>方法论</h3>
  <p>本报告遵循《证券分析》（格雷厄姆 & 多德，1934）与《华尔街证券分析》（胡克，第2版）的系统性方法论框架。自上而下八步流程：宏观经济评述 → 行业分析 → 公司分析 → 财务分析 → 财务预测 → 估值 → 投资建议 → 研究报告。</p>

  <h3>关键局限性</h3>
  <ol>
    <li>猪价预测是估值最大的不确定性来源——生猪期货仅覆盖未来 ~12 个月，长期判断依赖产能趋势推断</li>
    <li>周期均值 EPS 假设"未来周期与过去 8 年相似"——如果行业结构性变化（如规模化导致周期消失），这一假设将不成立</li>
    <li>同行可比数据为手工采集（本机 SSL 阻断），可能存在滞后</li>
    <li>估值基于成熟期市场实测倍数——若行业结构变化导致市场定价逻辑改变（如规模化率进一步上升、猪周期趋平），倍数假设将不成立</li>
    <li>估值结果是"近似值范围"而非精确数字——60-70% 时间做出正确预测已属超常</li>
  </ol>

  <p style="font-size:12px;color:#bbb;margin-top:24px">
    报告日期：{TODAY_STR} · 数据截至 2026-07-28（除特别标注外）· 本报告仅供学习研究参考，不构成投资建议<br>
    完整数据来源索引：data/sources/SOURCES.md · 路线图：ROADMAP.md
  </p>
</div>

</div>
</body>
</html>"""

# ==================== 写入报告 ====================
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text(report_html, encoding="utf-8")
print(f"\n✅ 综合研究报告已生成: {REPORT_PATH}")
print(f"   文件大小: {REPORT_PATH.stat().st_size/1024:.0f} KB")
print(f"   图表数量: {len(charts)} 张")
print(f"   报告结构: 8 部分标准结构")
