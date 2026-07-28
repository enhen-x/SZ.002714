#!/usr/bin/env python3
"""根据已下载的财报 CSV 生成牧原股份财务可视化与时间线报告。"""

from __future__ import annotations

import argparse
import html
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError as exc:
    raise SystemExit("缺少依赖，请先执行: python -m pip install plotly pandas") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "财务分析报告.html"
TIMELINE_PATH = REPORTS_DIR / "财务状况时间线.csv"

COLORS = {
    "ink": "#202522",
    "muted": "#737970",
    "grid": "#dde0da",
    "red": "#b33a32",
    "green": "#23755b",
    "amber": "#b47719",
    "blue": "#316b83",
    "gray": "#8b9189",
}


def read_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"缺少数据文件: {path}\n请先运行 python scripts/fetch_financial_reports.py"
        )
    frame = pd.read_csv(path)
    frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"], errors="coerce")
    return frame.dropna(subset=["REPORT_DATE"])


def numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")


def load_financial_data() -> pd.DataFrame:
    indicators = read_csv("主要财务指标_按报告期.csv")
    balance = read_csv("资产负债表_按报告期.csv")
    profit = read_csv("利润表_按报告期.csv")
    cashflow = read_csv("现金流量表_按报告期.csv")

    indicator_columns = [
        "REPORT_DATE", "REPORT_DATE_NAME", "TOTALOPERATEREVE", "PARENTNETPROFIT",
        "TOTALOPERATEREVETZ", "PARENTNETPROFITTZ", "ROEJQ", "XSMLL", "XSJLL",
        "ZCFZL", "LD", "SD", "EPSJB",
    ]
    balance_columns = [
        "REPORT_DATE", "TOTAL_ASSETS", "TOTAL_LIABILITIES", "TOTAL_PARENT_EQUITY",
        "MONETARYFUNDS", "INVENTORY",
    ]
    profit_columns = ["REPORT_DATE", "OPERATE_PROFIT", "DEDUCT_PARENT_NETPROFIT"]
    cash_columns = [
        "REPORT_DATE", "NETCASH_OPERATE", "NETCASH_INVEST", "NETCASH_FINANCE",
        "CONSTRUCT_LONG_ASSET",
    ]

    data = indicators[[c for c in indicator_columns if c in indicators]].copy()
    for source, columns in [
        (balance, balance_columns), (profit, profit_columns), (cashflow, cash_columns)
    ]:
        data = data.merge(
            source[[c for c in columns if c in source]],
            on="REPORT_DATE",
            how="left",
            validate="one_to_one",
        )

    numeric(data, [c for c in data.columns if c not in {"REPORT_DATE", "REPORT_DATE_NAME"}])
    data["FREE_CASH_FLOW"] = data["NETCASH_OPERATE"] - data["CONSTRUCT_LONG_ASSET"]
    data["CASH_PROFIT_RATIO"] = data["NETCASH_OPERATE"] / data["PARENTNETPROFIT"]
    data["IS_ANNUAL"] = data["REPORT_DATE"].dt.month.eq(12)
    return data.sort_values("REPORT_DATE").reset_index(drop=True)


def value(row: pd.Series, key: str) -> float | None:
    number = row.get(key)
    return None if pd.isna(number) else float(number)


def fmt_number(number: float | None, suffix: str = "") -> str:
    if number is None or pd.isna(number):
        return "--"
    return f"{number:,.1f}{suffix}"


def fmt_money(number: float | None) -> str:
    if number is None or pd.isna(number):
        return "--"
    return f"{number / 1e8:,.1f}亿"


def period_assessment(row: pd.Series) -> tuple[int, str, str, str]:
    score = 0
    positives: list[str] = []
    concerns: list[str] = []
    revenue_yoy = value(row, "TOTALOPERATEREVETZ")
    profit_yoy = value(row, "PARENTNETPROFITTZ")
    profit = value(row, "PARENTNETPROFIT")
    roe = value(row, "ROEJQ")
    gross_margin = value(row, "XSMLL")
    debt_ratio = value(row, "ZCFZL")
    current_ratio = value(row, "LD")
    operating_cash = value(row, "NETCASH_OPERATE")
    free_cash = value(row, "FREE_CASH_FLOW")

    if revenue_yoy is not None:
        score += 1 if revenue_yoy >= 10 else (-1 if revenue_yoy < 0 else 0)
        (positives if revenue_yoy >= 10 else concerns if revenue_yoy < 0 else positives).append(
            f"营收同比{revenue_yoy:+.1f}%"
        )
    if profit is not None:
        score += 1 if profit > 0 else -2
        (positives if profit > 0 else concerns).append("保持盈利" if profit > 0 else "归母净利润亏损")
    if profit_yoy is not None:
        score += 1 if profit_yoy >= 10 else (-1 if profit_yoy < 0 else 0)
        if abs(profit_yoy) < 1000:
            (positives if profit_yoy >= 10 else concerns if profit_yoy < 0 else positives).append(
                f"净利润同比{profit_yoy:+.1f}%"
            )
    if roe is not None:
        score += 1 if roe >= 12 else (-1 if roe < 0 else 0)
        (positives if roe >= 12 else concerns if roe < 0 else positives).append(f"ROE {roe:.1f}%")
    if gross_margin is not None:
        score += 1 if gross_margin >= 15 else (-1 if gross_margin < 8 else 0)
        if gross_margin < 8:
            concerns.append(f"毛利率仅{gross_margin:.1f}%")
    if debt_ratio is not None:
        score += 1 if debt_ratio < 55 else (-1 if debt_ratio >= 65 else 0)
        (positives if debt_ratio < 55 else concerns if debt_ratio >= 65 else positives).append(
            f"资产负债率{debt_ratio:.1f}%"
        )
    if current_ratio is not None:
        score += 1 if current_ratio >= 1 else (-1 if current_ratio < 0.7 else 0)
        if current_ratio < 1:
            concerns.append(f"流动比率{current_ratio:.2f}")
    if operating_cash is not None:
        score += 1 if operating_cash > 0 else -1
        (positives if operating_cash > 0 else concerns).append(
            "经营现金流为正" if operating_cash > 0 else "经营现金流为负"
        )
    if free_cash is not None:
        score += 1 if free_cash > 0 else -1
        (positives if free_cash > 0 else concerns).append(
            "自由现金流为正" if free_cash > 0 else "自由现金流为负"
        )

    if score >= 6:
        status, css_class = "稳健", "healthy"
    elif score >= 2:
        status, css_class = "改善", "improving"
    elif score >= -1:
        status, css_class = "承压", "pressured"
    else:
        status, css_class = "风险关注", "risk"
    summary_parts = positives[:2] + concerns[:2]
    return score, status, css_class, "；".join(summary_parts) or "有效指标不足"


def add_assessments(data: pd.DataFrame) -> pd.DataFrame:
    assessed = data.copy()
    results = assessed.apply(period_assessment, axis=1, result_type="expand")
    results.columns = ["SCORE", "STATUS", "STATUS_CLASS", "SUMMARY"]
    return pd.concat([assessed, results], axis=1)


def base_layout(fig: go.Figure, title: str, subtitle: str) -> None:
    fig.update_layout(
        title={"text": f"{title}<br><sup>{subtitle}</sup>", "x": 0, "xanchor": "left"},
        height=430,
        margin={"l": 58, "r": 38, "t": 85, "b": 52},
        paper_bgcolor="#f6f5f0",
        plot_bgcolor="#f6f5f0",
        font={"family": "Microsoft YaHei UI, sans-serif", "color": COLORS["ink"], "size": 12},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.05, "x": 1, "xanchor": "right"},
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["grid"], tickformat="%Y")
    fig.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["gray"])


def line_trace(x: pd.Series, y: pd.Series, name: str, color: str, suffix: str = "") -> go.Scatter:
    return go.Scatter(
        x=x,
        y=y,
        name=name,
        mode="lines+markers",
        line={"color": color, "width": 2.5},
        marker={"size": 6, "color": "#f6f5f0", "line": {"color": color, "width": 2}},
        hovertemplate=f"%{{y:,.1f}}{suffix}<extra>{name}</extra>",
    )


def build_charts(data: pd.DataFrame, chart_period: str) -> list[str]:
    chart_data = data if chart_period == "all" else data[data["IS_ANNUAL"]]
    period_note = "全部报告期（累计口径）" if chart_period == "all" else "年报口径，保证跨年可比"
    x = chart_data["REPORT_DATE"]
    figures: list[go.Figure] = []

    scale = make_subplots(specs=[[{"secondary_y": True}]])
    scale.add_trace(line_trace(x, chart_data["TOTALOPERATEREVE"] / 1e8, "营业收入", COLORS["blue"], "亿"), secondary_y=False)
    scale.add_trace(line_trace(x, chart_data["PARENTNETPROFIT"] / 1e8, "归母净利润", COLORS["red"], "亿"), secondary_y=True)
    scale.update_yaxes(title_text="营业收入（亿元）", secondary_y=False)
    scale.update_yaxes(title_text="归母净利润（亿元）", secondary_y=True)
    base_layout(scale, "规模与利润", period_note)
    figures.append(scale)

    profitability = go.Figure()
    for column, name, color in [
        ("XSMLL", "毛利率", COLORS["amber"]),
        ("XSJLL", "净利率", COLORS["green"]),
        ("ROEJQ", "加权ROE", COLORS["red"]),
    ]:
        profitability.add_trace(line_trace(x, chart_data[column], name, color, "%"))
    profitability.update_yaxes(title_text="百分比（%）")
    base_layout(profitability, "盈利质量", period_note)
    figures.append(profitability)

    solvency = make_subplots(specs=[[{"secondary_y": True}]])
    solvency.add_trace(line_trace(x, chart_data["ZCFZL"], "资产负债率", COLORS["red"], "%"), secondary_y=False)
    solvency.add_trace(line_trace(x, chart_data["LD"], "流动比率", COLORS["blue"]), secondary_y=True)
    solvency.add_trace(line_trace(x, chart_data["SD"], "速动比率", COLORS["amber"]), secondary_y=True)
    solvency.update_yaxes(title_text="资产负债率（%）", secondary_y=False)
    solvency.update_yaxes(title_text="流动性比率", secondary_y=True)
    base_layout(solvency, "偿债与流动性", period_note)
    figures.append(solvency)

    cash = go.Figure()
    cash.add_trace(line_trace(x, chart_data["NETCASH_OPERATE"] / 1e8, "经营现金流", COLORS["green"], "亿"))
    cash.add_trace(line_trace(x, chart_data["FREE_CASH_FLOW"] / 1e8, "自由现金流", COLORS["red"], "亿"))
    cash.add_hline(y=0, line_width=1, line_color=COLORS["gray"])
    cash.update_yaxes(title_text="亿元")
    base_layout(cash, "现金创造能力", f"自由现金流 = 经营现金流 - 购建长期资产现金；{period_note}")
    figures.append(cash)

    structure = go.Figure()
    for column, name, color in [
        ("TOTAL_ASSETS", "总资产", COLORS["blue"]),
        ("TOTAL_LIABILITIES", "总负债", COLORS["red"]),
        ("TOTAL_PARENT_EQUITY", "归母权益", COLORS["green"]),
    ]:
        structure.add_trace(line_trace(x, chart_data[column] / 1e8, name, color, "亿"))
    structure.update_yaxes(title_text="亿元")
    base_layout(structure, "资产与资本结构", period_note)
    figures.append(structure)

    blocks: list[str] = []
    for index, figure in enumerate(figures):
        blocks.append(
            figure.to_html(
                full_html=False,
                include_plotlyjs=True if index == 0 else False,
                config={"displaylogo": False, "responsive": True, "locale": "zh-CN"},
            )
        )
    return blocks


def metric_html(label: str, display: str, detail: str, tone: str = "") -> str:
    return f"""
      <div class="metric {tone}">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(display)}</strong>
        <small>{html.escape(detail)}</small>
      </div>"""


def timeline_html(data: pd.DataFrame) -> str:
    items: list[str] = []
    for _, row in data.sort_values("REPORT_DATE", ascending=False).iterrows():
        annual = "true" if row["IS_ANNUAL"] else "false"
        details = [
            ("营收", fmt_money(value(row, "TOTALOPERATEREVE"))),
            ("归母净利", fmt_money(value(row, "PARENTNETPROFIT"))),
            ("ROE", fmt_number(value(row, "ROEJQ"), "%")),
            ("毛利率", fmt_number(value(row, "XSMLL"), "%")),
            ("负债率", fmt_number(value(row, "ZCFZL"), "%")),
            ("经营现金流", fmt_money(value(row, "NETCASH_OPERATE"))),
        ]
        detail_html = "".join(
            f"<span><b>{html.escape(label)}</b>{html.escape(display)}</span>" for label, display in details
        )
        items.append(f"""
        <article class="timeline-item {row['STATUS_CLASS']}" data-annual="{annual}">
          <div class="timeline-date">
            <time>{html.escape(str(row['REPORT_DATE_NAME']))}</time>
            <span>{row['REPORT_DATE']:%Y-%m-%d}</span>
          </div>
          <div class="timeline-marker"></div>
          <div class="timeline-body">
            <div class="timeline-title"><strong>{row['STATUS']}</strong><span>评分 {int(row['SCORE']):+d}</span></div>
            <p>{html.escape(str(row['SUMMARY']))}</p>
            <div class="timeline-metrics">{detail_html}</div>
          </div>
        </article>""")
    return "\n".join(items)


def build_report(data: pd.DataFrame, chart_period: str) -> str:
    latest = data.iloc[-1]
    latest_annual = data[data["IS_ANNUAL"]].iloc[-1]
    chart_blocks = build_charts(data, chart_period)
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    metrics = "".join([
        metric_html("营业收入", fmt_money(value(latest, "TOTALOPERATEREVE")), f"同比 {fmt_number(value(latest, 'TOTALOPERATEREVETZ'), '%')}", "blue"),
        metric_html("归母净利润", fmt_money(value(latest, "PARENTNETPROFIT")), f"同比 {fmt_number(value(latest, 'PARENTNETPROFITTZ'), '%')}", "red" if value(latest, "PARENTNETPROFIT") < 0 else "green"),
        metric_html("加权 ROE", fmt_number(value(latest, "ROEJQ"), "%"), f"最新年报 {fmt_number(value(latest_annual, 'ROEJQ'), '%')}", "amber"),
        metric_html("资产负债率", fmt_number(value(latest, "ZCFZL"), "%"), f"流动比率 {fmt_number(value(latest, 'LD'))}", "blue"),
        metric_html("自由现金流", fmt_money(value(latest, "FREE_CASH_FLOW")), f"经营现金流 {fmt_money(value(latest, 'NETCASH_OPERATE'))}", "green" if value(latest, "FREE_CASH_FLOW") > 0 else "red"),
    ])
    charts = "\n".join(f'<section class="chart-band">{block}</section>' for block in chart_blocks)
    timeline = timeline_html(data)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>牧原股份财务脉络</title>
  <style>
    :root {{ --paper:#f6f5f0; --ink:#202522; --muted:#737970; --line:#d7dad3; --red:#b33a32; --green:#23755b; --amber:#b47719; --blue:#316b83; }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:"Microsoft YaHei UI","Microsoft YaHei",sans-serif; letter-spacing:0; }}
    header {{ border-bottom:1px solid var(--ink); padding:46px max(24px,calc((100vw - 1180px)/2)) 30px; }}
    .eyebrow {{ display:flex; justify-content:space-between; gap:20px; color:var(--muted); font-size:12px; }}
    h1 {{ margin:22px 0 8px; font-family:"STZhongsong","SimSun",serif; font-size:clamp(36px,6vw,74px); font-weight:500; line-height:1; }}
    .subtitle {{ margin:0; color:var(--muted); font-size:15px; }}
    .wrap {{ width:min(1180px,calc(100% - 48px)); margin:0 auto; }}
    .metric-strip {{ display:grid; grid-template-columns:repeat(5,1fr); border-bottom:1px solid var(--ink); }}
    .metric {{ min-width:0; padding:25px 18px 22px 0; border-right:1px solid var(--line); }}
    .metric + .metric {{ padding-left:18px; }} .metric:last-child {{ border-right:0; }}
    .metric span,.metric small {{ display:block; color:var(--muted); font-size:11px; }}
    .metric strong {{ display:block; margin:9px 0 7px; font-family:"STZhongsong","SimSun",serif; font-size:24px; white-space:nowrap; }}
    .metric.red strong {{ color:var(--red); }} .metric.green strong {{ color:var(--green); }} .metric.amber strong {{ color:var(--amber); }} .metric.blue strong {{ color:var(--blue); }}
    .section-head {{ display:flex; align-items:end; justify-content:space-between; gap:24px; padding:62px 0 18px; border-bottom:1px solid var(--ink); }}
    h2 {{ margin:0; font-family:"STZhongsong","SimSun",serif; font-size:30px; font-weight:500; }}
    .section-head p {{ max-width:600px; margin:0; color:var(--muted); font-size:12px; line-height:1.7; text-align:right; }}
    .chart-band {{ padding:12px 0 4px; border-bottom:1px solid var(--line); overflow:hidden; }}
    .controls {{ display:flex; gap:0; border:1px solid var(--ink); }}
    .controls button {{ appearance:none; border:0; border-right:1px solid var(--ink); background:transparent; color:var(--ink); padding:8px 13px; cursor:pointer; font:12px inherit; }}
    .controls button:last-child {{ border-right:0; }} .controls button.active {{ background:var(--ink); color:var(--paper); }}
    .timeline {{ padding:24px 0 70px; }}
    .timeline-item {{ display:grid; grid-template-columns:125px 24px 1fr; min-height:142px; }}
    .timeline-date {{ padding-top:18px; text-align:right; }} .timeline-date time {{ display:block; font-family:"STZhongsong","SimSun",serif; font-size:17px; }} .timeline-date span {{ color:var(--muted); font-size:10px; }}
    .timeline-marker {{ position:relative; margin:0 11px; border-left:1px solid var(--line); }}
    .timeline-marker::before {{ content:""; position:absolute; top:23px; left:-5px; width:9px; height:9px; background:var(--paper); border:2px solid var(--blue); border-radius:50%; }}
    .timeline-item.healthy .timeline-marker::before {{ border-color:var(--green); }} .timeline-item.risk .timeline-marker::before {{ border-color:var(--red); }} .timeline-item.pressured .timeline-marker::before {{ border-color:var(--amber); }}
    .timeline-body {{ padding:16px 0 24px 22px; border-bottom:1px solid var(--line); }}
    .timeline-title {{ display:flex; align-items:center; gap:10px; }} .timeline-title strong {{ font-size:17px; }} .timeline-title span {{ color:var(--muted); font-size:10px; }}
    .healthy .timeline-title strong {{ color:var(--green); }} .risk .timeline-title strong {{ color:var(--red); }} .pressured .timeline-title strong {{ color:var(--amber); }}
    .timeline-body p {{ margin:8px 0 12px; line-height:1.7; }}
    .timeline-metrics {{ display:flex; flex-wrap:wrap; gap:8px 22px; color:var(--muted); font-size:11px; }} .timeline-metrics b {{ margin-right:5px; color:var(--ink); font-weight:500; }}
    .method {{ margin-bottom:55px; padding:22px 0; border-top:1px solid var(--ink); border-bottom:1px solid var(--ink); color:var(--muted); font-size:11px; line-height:1.8; }}
    footer {{ padding:25px 0 40px; border-top:1px solid var(--ink); color:var(--muted); font-size:11px; }}
    @media (max-width:800px) {{
      header {{ padding-top:28px; }} .eyebrow {{ flex-direction:column; gap:4px; }}
      .wrap {{ width:min(100% - 28px,1180px); }} .metric-strip {{ grid-template-columns:repeat(2,1fr); }}
      .metric {{ border-bottom:1px solid var(--line); }} .metric:nth-child(even) {{ border-right:0; }} .metric:last-child {{ grid-column:1/-1; }}
      .section-head {{ align-items:flex-start; flex-direction:column; }} .section-head p {{ text-align:left; }}
      .timeline-item {{ grid-template-columns:86px 20px 1fr; }} .timeline-body {{ padding-left:12px; }} .timeline-metrics {{ gap:6px 14px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="eyebrow"><span>财务数据观察 / SZ.002714</span><span>数据截至 {latest['REPORT_DATE']:%Y-%m-%d}</span></div>
    <h1>牧原股份财务脉络</h1>
    <p class="subtitle">从规模、盈利、偿债与现金流，追踪一家周期型养殖企业的财务状态。</p>
  </header>
  <main class="wrap">
    <section class="metric-strip">{metrics}</section>
    <div class="section-head"><h2>关键指标变化</h2><p>默认使用年报口径绘图，避免累计一季报、中报与全年数据直接比较造成误读。可通过脚本参数切换为全部报告期。</p></div>
    {charts}
    <div class="section-head">
      <div><h2>财务状况时间线</h2></div>
      <div class="controls"><button class="active" data-filter="all">全部报告期</button><button data-filter="annual">仅年报</button></div>
    </div>
    <section class="timeline" id="timeline">{timeline}</section>
    <aside class="method"><strong>判定口径：</strong>状态由营收与利润增长、盈利与 ROE、毛利率、资产负债率、流动比率、经营现金流和自由现金流等指标机械评分得出。“稳健”≥6 分，“改善”2—5 分，“承压”-1—1 分，“风险关注”≤-2 分。该结果用于快速筛查，不构成投资建议；季度数据为年初至报告期的累计值。</aside>
  </main>
  <footer><div class="wrap">AkShare / 东方财富财报数据 · 报告生成于 {generated}</div></footer>
  <script>
    document.querySelectorAll('.controls button').forEach(button => {{
      button.addEventListener('click', () => {{
        document.querySelectorAll('.controls button').forEach(item => item.classList.remove('active'));
        button.classList.add('active');
        const annualOnly = button.dataset.filter === 'annual';
        document.querySelectorAll('.timeline-item').forEach(item => {{
          item.hidden = annualOnly && item.dataset.annual !== 'true';
        }});
      }});
    }});
  </script>
</body>
</html>"""


def save_timeline(data: pd.DataFrame) -> None:
    columns = {
        "REPORT_DATE": "报告日期", "REPORT_DATE_NAME": "报告期", "STATUS": "财务状态",
        "SCORE": "评分", "SUMMARY": "状态摘要", "TOTALOPERATEREVE": "营业收入",
        "PARENTNETPROFIT": "归母净利润", "TOTALOPERATEREVETZ": "营收同比_%",
        "PARENTNETPROFITTZ": "归母净利润同比_%", "ROEJQ": "加权ROE_%",
        "XSMLL": "毛利率_%", "XSJLL": "净利率_%", "ZCFZL": "资产负债率_%",
        "LD": "流动比率", "SD": "速动比率", "NETCASH_OPERATE": "经营现金流",
        "FREE_CASH_FLOW": "自由现金流",
    }
    output = data[[c for c in columns if c in data]].rename(columns=columns).sort_values("报告日期", ascending=False)
    temp_path = TIMELINE_PATH.with_suffix(".csv.tmp")
    output.to_csv(temp_path, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    temp_path.replace(TIMELINE_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成牧原股份财务可视化分析报告")
    parser.add_argument(
        "--chart-period", choices=["annual", "all"], default="annual",
        help="折线图使用年报（annual）或全部报告期累计数据（all）",
    )
    args = parser.parse_args()
    try:
        data = add_assessments(load_financial_data())
    except (FileNotFoundError, KeyError, pd.errors.ParserError) as exc:
        raise SystemExit(f"读取财报数据失败: {exc}") from exc
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_report(data, args.chart_period), encoding="utf-8")
    save_timeline(data)
    print(f"已生成 HTML 报告: {REPORT_PATH}")
    print(f"已生成时间线数据: {TIMELINE_PATH}")
    print(f"覆盖 {len(data)} 个报告期，最新报告期为 {data.iloc[-1]['REPORT_DATE']:%Y-%m-%d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
