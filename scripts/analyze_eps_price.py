# -*- coding: utf-8 -*-
"""验证 e^(EPS) × PE 模型能否拟合牧原股价

用户假设：股价 = e^(长期EPS + 短期EPS) × PE = e^(当期EPS) × PE
对数化：ln(股价) = ln(PE) + 当期EPS  →  回归 ln(P) = a + b·eps

检验三件事：
  1. 斜率 b 是否 ≈ 1（即模型形式成立）
  2. R² 多高（拟合优度）
  3. 隐含有效PE = exp(lnP - b·eps) 是否稳定（即 PE 是否接近常数）

口径处理（关键）：
  - 股价用「市值口径前复权」：前复权等值价 = 不复权价 × (当期股本/最新股本) = 市值/最新股本
  - 股本序列 = 归母净资产 ÷ BPS（期末口径自洽，规避送转/增发失真，无需除权记录）
  - EPS 用「净利润/最新股本」—— 与股价同口径
  - 两种盈利口径：TTM（滚动4季）与 单季年化（单季×4）
  - 两种对齐：同期（季末价 vs 当季盈利）与 滞后一期（下季末价 vs 当季盈利）
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

# ---------------------------------------------------------------- 1. 不复权日线（本地缓存，2014-2026）
df_daily = pd.read_csv(DATA / "牧原_日线股价.csv")
df_daily["date"] = pd.to_datetime(df_daily["date"])
print(f"  不复权日线: {df_daily['date'].min().date()} ~ {df_daily['date'].max().date()} 共 {len(df_daily)} 条")
print(f"  最新收盘: {df_daily['close'].iloc[-1]:.2f} 元")

# ---------------------------------------------------------------- 2. 股本序列（市值口径核心）
# 股本_t = 归母净资产_t ÷ BPS_t（期末口径自洽，无需除权记录）
bs = pd.read_csv(DATA / "资产负债表_按报告期.csv", dtype=str)
bs["REPORT_DATE"] = pd.to_datetime(bs["REPORT_DATE"])
bs["EQ"] = pd.to_numeric(bs["TOTAL_PARENT_EQUITY"], errors="coerce")
bs = bs[["REPORT_DATE", "EQ"]].dropna()

qf = pd.read_csv(DATA / "主要财务指标_按单季度.csv", dtype=str)
qf["REPORT_DATE"] = pd.to_datetime(qf["REPORT_DATE"])
qf["BPS"] = pd.to_numeric(qf["BPS"], errors="coerce")
qf = qf.sort_values("REPORT_DATE").reset_index(drop=True)   # 升序（原始文件为倒序）
qf["EQ"] = qf.merge(bs, on="REPORT_DATE", how="left")["EQ"]
qf["shares"] = qf["EQ"] / qf["BPS"]           # 各期期末总股本（股）
valid_shares = qf["shares"].dropna()
if len(valid_shares) < 40:
    raise SystemExit("股本反推数据不足，检查资产负债表/财务指标文件")
print(f"  股本反推: {len(valid_shares)} 期有效 | 最新 {valid_shares.iloc[-1]/1e8:.2f} 亿股 "
      f"（{qf.loc[valid_shares.index[-1], 'REPORT_DATE'].date()}） | "
      f"上市前最小 {valid_shares.min()/1e8:.2f} 亿股（{qf.loc[valid_shares.idxmin(), 'REPORT_DATE'].date()}）")

# ---------------------------------------------------------------- 3. 单季净利润 → TTM / 年化（统一当前股本口径）
SHARES = valid_shares.iloc[-1]                # 最新期股本作为统一口径除数
qf["NI"] = pd.to_numeric(qf["PARENTNETPROFIT"], errors="coerce")  # 单季归母净利润
qf = qf.sort_values("REPORT_DATE").reset_index(drop=True)
qf["NI_TTM"] = qf["NI"].rolling(4, min_periods=4).sum()
qf["eps_ttm"] = qf["NI_TTM"] / SHARES          # 每股（最新股本口径）
qf["eps_q_ann"] = qf["NI"] * 4 / SHARES        # 单季年化（最新股本口径）
# 当时口径: 用报表单季EPS滚动4季（当时摊薄口径，与不复权价同时代）
qf["eps_ttm_raw"] = pd.to_numeric(qf["EPSJB"], errors="coerce").rolling(4, min_periods=4).sum()
qf["quarter"] = qf["REPORT_DATE"].dt.to_period("Q")

# ---------------------------------------------------------------- 4. 价格对齐（统一股本口径）
df_daily["quarter"] = df_daily["date"].dt.to_period("Q")
qtr = df_daily.groupby("quarter")["close"].agg(
    last="last", avg="mean", max="max", min="min"
).reset_index()
qtr = qtr.merge(qf[["quarter", "eps_ttm", "eps_q_ann", "eps_ttm_raw", "NI_TTM", "shares"]], on="quarter", how="left")
# 前复权等值价 = 不复权价 × (当时股本/最新股本) = 市值/最新股本（送转/增发已隐式调整）
qtr["price_adj"] = qtr["last"] * qtr["shares"] / SHARES

# 过滤 2014Q1（上市）起、有盈利数据的季度
qtr = qtr[(qtr["quarter"] >= pd.Period("2014Q1", "Q")) & qtr["eps_ttm"].notna()].reset_index(drop=True)
n = len(qtr)
print(f"  有效季度样本: {n} 个（{qtr['quarter'].iloc[0]} ~ {qtr['quarter'].iloc[-1]}）")

# ---------------------------------------------------------------- 4. 回归工具
def ols(x, y):
    """普通最小二乘 y = a + b·x，返回 (b, a, r2, t_b, n)"""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    sxy = ((x - xm) * (y - ym)).sum()
    b = sxy / sxx if sxx != 0 else 0.0
    a = ym - b * xm
    resid = y - (a + b * x)
    ss_res = (resid ** 2).sum()
    ss_tot = ((y - ym) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
    # t 统计量（b 的标准误）
    dof = len(x) - 2
    se_b = np.sqrt(ss_res / dof / sxx) if dof > 0 and sxx > 0 else np.nan
    t_b = b / se_b if se_b and se_b > 0 else np.nan
    return b, a, r2, t_b, len(x)

def run_model(df, eps_col, label, lag=False, price_col="price_adj"):
    """对一种 EPS 口径跑回归。lag=True: 用下一季度末价格（市场提前定价）
    price_col: "price_adj"=市值口径（最新股本）| "last"=不复权价（当时口径）"""
    y = np.log(df[price_col].astype(float).values)
    x = df[eps_col].astype(float).values
    if lag:
        x = x[:-1]
        y = y[1:]
        label += "（滞后一期）"
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    b, a, r2, t_b, nn = ols(x, y)
    # 隐含有效PE: exp(lnP - b·eps)，即残差 e^(残差)
    resid = y - (a + b * x)
    pe_eff = np.exp(resid)
    pcts = {p: float(np.percentile(pe_eff, p)) for p in [10, 25, 50, 75, 90]}
    print(f"\n  ── {label} ──")
    print(f"    样本 n={nn} | 斜率 b={b:.4f} (t={t_b:.1f}) | 截距 a={a:.4f} | R²={r2:.3f}")
    print(f"    隐含有效PE分布: P10={pcts[10]:.1f} P25={pcts[25]:.1f} P50={pcts[50]:.1f} P75={pcts[75]:.1f} P90={pcts[90]:.1f}")
    return {"label": label, "b": b, "a": a, "r2": r2, "t": t_b, "n": nn,
            "pe_eff": pe_eff, "x": x, "y": y, "resid": resid, "pcts": pcts}

print("\n" + "=" * 60)
print("回归: ln(季度末股价) = a + b × eps")
print("=" * 60)

results = []
for eps_col, eps_label in [("eps_ttm", "TTM EPS（滚动4季）"), ("eps_q_ann", "单季年化 EPS（单季×4）")]:
    results.append(run_model(qtr, eps_col, eps_label, lag=False))
    results.append(run_model(qtr, eps_col, eps_label, lag=True))

# 不复权口径: 当时摊薄EPS vs 当时不复权价（市场当时真实看到的数字）
results.append(run_model(qtr, "eps_ttm_raw", "TTM EPS（当时摊薄口径）+ 不复权价", price_col="last"))
results.append(run_model(qtr, "eps_ttm_raw", "TTM EPS（当时摊薄口径）+ 不复权价（滞后一期）", lag=True, price_col="last"))

# 前瞻1期: 当期价格 vs 下一期TTM盈利（检验市场是否定价"预期"而非"当期"）
qtr["eps_ttm_lead"] = qtr["eps_ttm"].shift(-1)
results.append(run_model(qtr, "eps_ttm_lead", "TTM EPS（前瞻1期：下季盈利 vs 当季价格）"))

# 反推与绘图用「当期 TTM + 市值口径」模型（前瞻模型含未来信息，不用于反推）
best = next(r for r in results if r["label"] == "TTM EPS（滚动4季）")
print(f"\n  反推基准模型: {best['label']}  R²={best['r2']:.3f}  b={best['b']:.4f}")

# ---------------------------------------------------------------- 4b. 双因子检验: lnP = a + b1·eps + b2·猪价
hog = pd.read_csv(DATA / "生猪价格_季度.csv", dtype=str)
hog["季度"] = pd.PeriodIndex(hog["季度"], freq="Q")
hog["hog_price"] = pd.to_numeric(hog["季度均价_元每公斤"], errors="coerce")
qtr = qtr.merge(hog[["季度", "hog_price"]], left_on="quarter", right_on="季度", how="left")

def ols2(df_sub):
    """lnP = a + b1·eps_ttm + b2·hog_price"""
    Y = np.log(df_sub["price_adj"].astype(float).values)
    X1 = df_sub["eps_ttm"].astype(float).values
    X2 = df_sub["hog_price"].astype(float).values
    mask = ~np.isnan(X1) & ~np.isnan(X2) & np.isfinite(Y)
    X = np.column_stack([np.ones(mask.sum()), X1[mask], X2[mask]])
    Y = Y[mask]
    beta, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    ss_res = (resid ** 2).sum()
    ss_tot = ((Y - Y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot
    # t 值
    dof = len(Y) - 3
    sigma2 = ss_res / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    tvals = beta / se
    return beta, tvals, r2, len(Y)

b2, t2, r2_2f, n2 = ols2(qtr)
print("\n" + "=" * 60)
print("双因子模型: ln(股价) = a + b1·eps_ttm + b2·猪价季均")
print("=" * 60)
print(f"  样本 n={n2} | b1(eps)={b2[1]:.4f} (t={t2[1]:.1f}) | b2(猪价)={b2[2]:.4f} (t={t2[2]:.1f}) | R²={r2_2f:.3f}")
print(f"  （对比单因子 TTM: R²=0.251）→ 猪价因子带来的 R² 增量 = {r2_2f - best['r2']:.3f}")

# ---------------------------------------------------------------- 5. 反推: 给定 eps → 理论价
print("\n" + "=" * 60)
print("反推: 理论股价 = exp(a + b × eps)   （最佳模型）")
print("=" * 60)
a, b = best["a"], best["b"]

# 动态取各年度实际净利润（统一最新股本口径）
qf2 = qf.copy()
qf2["year"] = qf2["REPORT_DATE"].dt.year
year_ni = qf2.groupby("year")["NI"].sum() / SHARES      # 年度 EPS（元/股）
cur_eps = float(qtr["eps_ttm"].iloc[-1])                # 当前 TTM eps
y2023 = float(year_ni.get(2023, -0.74))
y2024 = float(year_ni.get(2024, 3.10))
y2025 = float(year_ni.get(2025, 2.68))
y2020 = float(year_ni.get(2020, 4.75))

scen = [
    (-2.0,  "深度亏损期 (eps=-2)"),
    (y2023, f"2023年实际 ({y2023:.2f})"),
    (0.0,   "盈亏平衡 (eps=0)"),
    (cur_eps, f"当前 TTM ({cur_eps:.2f}, 2026Q1)"),
    (2.0,   "长期中枢 eps=2"),
    (y2025, f"2025年实际 ({y2025:.2f})"),
    (y2024, f"2024年实际 ({y2024:.2f})"),
    (y2020, f"2020年峰值 ({y2020:.2f})"),
]
p_cur = float(df_daily["close"].iloc[-1])               # 当前最新价（最新期无除权，不复权=复权）
print(f"  当前实际股价: {p_cur:.1f} 元")
for e, lbl in scen:
    print(f"  {lbl:<28} → 理论价 {np.exp(a + b * e):6.1f} 元")

# 当前价格隐含的 eps（解 exp(a+b·eps)=P）
import scipy.optimize as so
eps_impl = so.brentq(lambda e: np.exp(a + b * e) - p_cur, -10, 10)
print(f"\n  当前价 {p_cur:.1f} 元 → 市场隐含定价 eps = {eps_impl:.2f} 元/股"
      f"（当前实际 TTM ≈{cur_eps:.2f}，隐含偏离 {(eps_impl-cur_eps)/abs(cur_eps)*100:+.0f}%）")

# ---------------------------------------------------------------- 6. 绘图
import plotly.graph_objects as go
from plotly.subplots import make_subplots

qlabels = qtr["quarter"].astype(str).tolist()
colors_eps = qtr["eps_ttm"].astype(float).values

fig1 = go.Figure()
x, y = best["x"], best["y"]
xs = np.linspace(x.min() - 0.2, x.max() + 0.2, 100)
fig1.add_trace(go.Scatter(x=x, y=y, mode="markers", name="季度观测",
                          marker=dict(size=8, color=colors_eps[:len(x)],
                                      colorscale="RdYlGn", showscale=True,
                                      colorbar=dict(title="TTM EPS", thickness=12))))
fig1.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines", name=f"拟合 lnP = {a:.2f} + {b:.2f}·eps  (R²={best['r2']:.2f})",
                          line=dict(color="#e67e22", width=2.5)))
fig1.add_trace(go.Scatter(x=xs, y=xs + np.log(5.6), mode="lines", name="参考: ln(e^eps×5.6)", line=dict(color="#999", dash="dot", width=1)))
fig1.update_layout(title=f"ln(股价) vs EPS — 验证 e^eps × PE 模型（{best['label']}）",
                   xaxis_title="每股盈利 eps（元，当前股本口径）", yaxis_title="ln(季度末前复权股价)",
                   template="plotly_white", height=480,
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))

# 图2: 实际 vs 模型（统一股本口径价）
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=qlabels, y=qtr["price_adj"].values, mode="lines+markers", name="实际季末价（市值口径）", line=dict(color="#2c3e50", width=2)))
fig2.add_trace(go.Scatter(x=qlabels[:len(y)], y=np.exp(a + b * x), mode="lines", name=f"模型拟合（R²={best['r2']:.2f}）", line=dict(color="#e67e22", width=2)))
fig2.add_trace(go.Scatter(x=qlabels, y=[p_cur]*n, mode="lines", name=f"当前价 {p_cur:.1f}", line=dict(color="#c0392b", dash="dash", width=1)))
fig2.update_layout(title="实际股价 vs e^eps×PE 模型拟合 — 市值口径（统一最新股本）", yaxis_title="元",
                   template="plotly_white", height=480,
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))

# 图3: 隐含有效PE 时序
fig3 = go.Figure()
pe_eff_series = best["pe_eff"]
fig3.add_trace(go.Scatter(x=qlabels[:len(pe_eff_series)], y=pe_eff_series, mode="lines+markers",
                          name="隐含有效PE = P/e^eps", line=dict(color="#1abc9c", width=2)))
for p, c in [(10, "#bbb"), (50, "#e67e22"), (90, "#bbb")]:
    fig3.add_hline(y=best["pcts"][p], line_dash="dot", line_color=c, annotation_text=f"P{p}% = {best['pcts'][p]:.1f}")
fig3.update_layout(title="隐含有效PE = 股价 ÷ e^eps（残差 e^(lnP−b·eps)）— 检验 PE 是否稳定",
                   yaxis_title="隐含有效PE (×)", template="plotly_white", height=480,
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))

# ---------------------------------------------------------------- 7. HTML 报告
def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

rows = ""
for r in results:
    rows += (f"<tr><td>{esc(r['label'])}</td><td>{r['n']}</td><td>{r['b']:.4f}</td>"
             f"<td>{r['t']:.1f}</td><td>{r['r2']:.3f}</td>"
             f"<td>{r['pcts'][25]:.1f}</td><td>{r['pcts'][50]:.1f}</td><td>{r['pcts'][75]:.1f}</td></tr>")
rows += (f"<tr style='background:#fdf2e9'><td><b>双因子（eps_ttm + 猪价季均）</b></td><td>{n2}</td>"
         f"<td>{b2[1]:.4f}（eps）</td><td>{t2[1]:.1f}</td><td><b>{r2_2f:.3f}</b></td>"
         f"<td colspan='3'>猪价系数 {b2[2]:.4f}（t={t2[2]:.1f}）</td></tr>")

scen_rows = ""
for e, lbl in scen:
    scen_rows += f"<tr><td>{esc(lbl)}</td><td>{e:.2f}</td><td>{np.exp(a + b * e):.1f}</td></tr>"

html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>e^(EPS)×PE 模型拟合验证 — 牧原股份</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
body{font-family:"Microsoft YaHei",sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#1a1a1a}
h1{font-size:22px}h2{font-size:17px;margin-top:36px;color:#2c3e50}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
th,td{border:1px solid #ddd;padding:7px 10px;text-align:center}
th{background:#2c3e50;color:#fff;font-weight:600}
tr:nth-child(even){background:#f8fafc}
.badge{display:inline-block;padding:3px 12px;border-radius:12px;font-size:13px;font-weight:600}
.good{background:#e8f8f0;color:#16a085}.bad{background:#fdecea;color:#c0392b}.warn{background:#fef9e7;color:#b7950b}
.note{border-left:3px solid #3498db;background:#f8fafc;padding:10px 16px;margin:16px 0;font-size:13px;line-height:1.7;color:#555}
</style></head><body>
<h1>验证：股价 ≈ e^(长期EPS + 短期EPS) × PE（对数线性价格模型）</h1>
<p style="color:#666">牧原股份 002714.SZ ｜ 数据：本地日线 × 季度财报（市值口径统一股本）｜ 2014Q1–2026Q1</p>

<h2>一、模型与口径</h2>
<p>用户假设：<b>股价 = e^(长期EPS + 短期EPS) × PE = e^(当期EPS) × PE</b>，取对数 → <b>ln(股价) = ln(PE) + EPS</b></p>
<div class="note">
<b>为什么 e^ 变换是关键：</b>传统 PE×EPS 在亏损期（EPS&lt;0）失效——股价不可能为负，但 EPS 可以为负。
e^EPS 恒正，把"可负的盈利"映射为"恒正的估值因子"：亏损越深，e^eps 越小但永远 &gt;0，股价随之压缩但不会崩为零。
这正是猪周期股需要的数学结构。<br>
<b>口径统一（市值口径）：</b>历史市值连续（送转/增发时股价除权与股本扩张恰好抵消），
故「市值口径价 = 不复权价 × 当期股本/最新股本 = 市值/最新股本」，股本由归母净资产÷BPS 逐期反推，
无需除权记录；每股盈利 = 净利润/最新股本。两者同口径，规避送转/增发导致的失真。
</div>

<h2>二、回归结果（lnP = a + b·eps）</h2>
<table>
<tr><th>口径</th><th>n</th><th>斜率 b</th><th>t 值</th><th>R²</th><th>隐含PE P25</th><th>P50</th><th>P75</th></tr>
""" + rows + """
</table>
<div class="note">
<b>检验判据：</b>① 斜率 b 是否≈1（等于1 → 模型形式 P = e^eps × 常数PE 成立；小于1 → 市场给高盈利更低的倍数，PE 本身随盈利反周期变化）；
② R² 越高拟合越好；③ 隐含有效PE 的分位区间越窄 → PE 越稳定。<br><br>
<b>口径对比（第 5、6 行）：</b>「当时摊薄口径 + 不复权价」是市场当时真实看到的数字组合，
斜率 b≈0.045、R²≈0.08——即使剔除 6 个送转除权季度后依然不变（b=0.043），
说明并非除权失真，而是<b>市场在无股本扰动的季度里也不按当期 EPS 定价</b>。
市值口径（最新股本换算）对模型最有利（b=0.34、R²=0.25），即便如此模型仍不成立——
两种口径结论一致：<b>当期 EPS 最多解释 1/4 的价格变动</b>。
</div>

<h2>三、反推：不同盈利水平 → 模型理论股价</h2>
<table>
<tr><th>情景</th><th>eps（元/股，当前股本口径）</th><th>理论股价（元）</th></tr>
""" + scen_rows + """
</table>
<p>当前实际股价 <b>""" + f"{p_cur:.1f}" + """ 元</b>，对应市场隐含定价 eps = """ + f"{eps_impl:.2f}" + """ 元/股（当前实际 TTM ≈ """ + f"{cur_eps:.2f}" + """）</p>

<h2>四、图形</h2>
<div id="fig1"></div>
<div id="fig2"></div>
<div id="fig3"></div>

<p style="color:#999;font-size:12px;margin-top:30px">生成: 2026-08-04 ｜ 仅供研究，不构成投资建议</p>
<script>
const f1 = """ + fig1.to_json() + """;
const f2 = """ + fig2.to_json() + """;
const f3 = """ + fig3.to_json() + """;
Plotly.newPlot("fig1", f1.data, f1.layout, {responsive:true, displayModeBar:false});
Plotly.newPlot("fig2", f2.data, f2.layout, {responsive:true, displayModeBar:false});
Plotly.newPlot("fig3", f3.data, f3.layout, {responsive:true, displayModeBar:false});
</script>
</body></html>
"""
out = REPORTS / "eps价格拟合验证.html"
out.write_text(html, encoding="utf-8")
print(f"\n  报告已生成: {out}（{out.stat().st_size//1024} KB）")
