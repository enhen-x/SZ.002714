#!/usr/bin/env python3
"""拉取生猪价格并分析猪周期与牧原股份单季度经营状况的相关性。"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import time
import warnings
from datetime import datetime
from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
RAW_PATH = DATA_DIR / "行情宝生猪指数_原始.json"
DAILY_PATH = DATA_DIR / "生猪价格_历史.csv"
QUARTERLY_PATH = DATA_DIR / "生猪价格_季度.csv"
MERGED_PATH = REPORTS_DIR / "猪周期与经营指标_季度.csv"
CORR_PATH = REPORTS_DIR / "猪周期相关性.csv"
REPORT_PATH = REPORTS_DIR / "猪周期与牧原经营分析.html"
META_PATH = DATA_DIR / "生猪价格_数据说明.json"
STOCK_PATH = DATA_DIR / "牧原股份股价_后复权.csv"
STOCK_RAW_PATH = DATA_DIR / "牧原股份股价_腾讯原始.json"
STOCK_CORR_PATH = REPORTS_DIR / "股价_猪价_营收相关性.csv"
TARGET_PATH = REPORTS_DIR / "股价情景目标价.csv"

PRICE_URL = "https://hqb.nxin.com/pigindex/getPigIndexChart.shtml?regionId=0"

COLORS = {
    "ink": "#1f2421", "paper": "#f4f2eb", "muted": "#74776f",
    "green": "#2c7358", "red": "#b83b31", "amber": "#bb7a17",
    "blue": "#2f6c89", "grid": "#d9dbd4", "violet": "#73536e",
}

METRICS = {
    "毛利率_%": "毛利率",
    "净利率_%": "净利率",
    "单季归母净利润_亿元": "归母净利润",
    "营收同比_%": "营收同比",
    "单季经营现金流_亿元": "经营现金流",
}


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    temp.replace(path)


def normalize_akshare_price(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"日期", "指数", "预售均价", "成交均价"}
    if not required.issubset(frame.columns):
        raise ValueError(f"AkShare 生猪行情字段异常: {list(frame.columns)}")
    output = frame.copy()
    keep = ["日期", "指数", "4个月均线", "6个月均线", "12个月均线", "预售均价", "成交均价", "成交均重"]
    output = output[[c for c in keep if c in output]].copy()
    output["日期"] = pd.to_datetime(output["日期"], errors="coerce")
    for column in keep[1:]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output.dropna(subset=["日期", "成交均价"])


def parse_raw_price(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("data") or []
    if not records:
        raise ValueError("行情宝原始响应中没有价格数据")
    columns = ["日期", "指数", "4个月均线", "6个月均线", "12个月均线", "预售均价", "成交均价", "成交均重"]
    frame = pd.DataFrame(records, columns=columns)
    frame["日期"] = pd.to_datetime(frame["日期"], unit="ms", errors="coerce") + pd.Timedelta(hours=8)
    for column in columns[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["日期", "成交均价"])


def fetch_with_curl() -> pd.DataFrame:
    executable = shutil.which("curl") or shutil.which("curl.exe")
    if not executable:
        raise RuntimeError("未找到系统 curl，无法使用 TLS 后备通道")
    temp_path = RAW_PATH.with_suffix(".json.tmp")
    completed = subprocess.run(
        [executable, "-k", "-L", "--fail", "--silent", "--show-error",
         "--max-time", "60", PRICE_URL, "-o", str(temp_path)],
        check=False,
    )
    if completed.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"curl 返回状态码 {completed.returncode}")
    temp_path.replace(RAW_PATH)
    return parse_raw_price(RAW_PATH)


def fetch_price(retries: int, allow_cache: bool) -> tuple[pd.DataFrame, str, str | None]:
    errors: list[str] = []
    for attempt in range(1, retries + 1):
        try:
            print(f"[AkShare] 拉取行情宝生猪价格指数，第 {attempt}/{retries} 次...")
            frame = ak.index_hog_spot_price()
            if frame.empty:
                raise RuntimeError("接口返回空数据")
            return normalize_akshare_price(frame), "AkShare / 行情宝全国生猪成交均价", None
        except Exception as exc:
            errors.append(f"AkShare: {type(exc).__name__}: {exc}")
            if attempt < retries:
                time.sleep(2 * attempt)

    try:
        print("[后备通道] 使用系统 curl 请求同一行情宝公开接口...")
        return fetch_with_curl(), "行情宝全国生猪成交均价（curl TLS 后备）", "; ".join(errors)
    except Exception as exc:
        errors.append(f"curl: {type(exc).__name__}: {exc}")

    if allow_cache and DAILY_PATH.exists():
        cached = pd.read_csv(DAILY_PATH)
        cached["日期"] = pd.to_datetime(cached["日期"], errors="coerce")
        print("[缓存] 联网更新失败，使用已有日度数据")
        return cached, "本地缓存", "; ".join(errors)
    raise RuntimeError("所有猪价数据通道均失败：" + "; ".join(errors))


def normalize_stock(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"日期", "开盘", "收盘", "最高", "最低", "成交量"}
    if not required.issubset(frame.columns):
        raise ValueError(f"股价字段异常: {list(frame.columns)}")
    output = frame[["日期", "开盘", "收盘", "最高", "最低", "成交量"]].copy()
    output["日期"] = pd.to_datetime(output["日期"], errors="coerce")
    for column in ["开盘", "收盘", "最高", "最低", "成交量"]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output.dropna(subset=["日期", "收盘"]).sort_values("日期").drop_duplicates("日期")


def fetch_stock_with_tencent() -> tuple[pd.DataFrame, float]:
    executable = shutil.which("curl") or shutil.which("curl.exe")
    if not executable:
        raise RuntimeError("未找到系统 curl")
    all_rows: list[list[str]] = []
    raw_payloads: list[dict[str, object]] = []
    current_price: float | None = None
    current_year = datetime.now().year
    for start_year in range(2014, current_year + 1, 2):
        end_year = min(start_year + 1, current_year)
        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31" if end_year < current_year else datetime.now().strftime("%Y-%m-%d")
        url = (
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
            f"param=sz002714,day,{start_date},{end_date},640,hfq"
        )
        temp_path = DATA_DIR / f".stock-{start_year}.json.tmp"
        completed = subprocess.run(
            [executable, "-k", "--http1.1", "-L", "--retry", "2", "--retry-all-errors",
             "--fail", "--silent", "--show-error", "--max-time", "60", url, "-o", str(temp_path)],
            check=False,
        )
        if completed.returncode != 0:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"腾讯股价接口 {start_year}-{end_year} 返回状态码 {completed.returncode}")
        payload = json.loads(temp_path.read_text(encoding="utf-8"))
        temp_path.unlink(missing_ok=True)
        stock_data = payload.get("data", {}).get("sz002714", {})
        rows = stock_data.get("hfqday") or stock_data.get("day") or []
        if not rows:
            raise RuntimeError(f"腾讯股价接口 {start_year}-{end_year} 返回空数据")
        all_rows.extend(rows)
        raw_payloads.append({"start": start_date, "end": end_date, "rows": rows})
        quote = stock_data.get("qt", {}).get("sz002714", [])
        if len(quote) > 3:
            current_price = float(quote[3])
    STOCK_RAW_PATH.write_text(json.dumps(raw_payloads, ensure_ascii=False), encoding="utf-8")
    frame = pd.DataFrame([row[:6] for row in all_rows], columns=["日期", "开盘", "收盘", "最高", "最低", "成交量"])
    if current_price is None:
        raise RuntimeError("腾讯行情未返回最新实际交易价")
    return normalize_stock(frame), current_price


def fetch_stock(retries: int, allow_cache: bool) -> tuple[pd.DataFrame, str, str | None, float]:
    errors: list[str] = []
    for attempt in range(1, retries + 1):
        try:
            print(f"[AkShare] 拉取牧原股份后复权股价，第 {attempt}/{retries} 次...")
            frame = ak.stock_zh_a_hist(
                symbol="002714", period="daily", start_date="20140101",
                end_date=datetime.now().strftime("%Y%m%d"), adjust="hfq", timeout=30,
            )
            raw_frame = ak.stock_zh_a_hist(
                symbol="002714", period="daily", start_date=datetime.now().strftime("%Y0101"),
                end_date=datetime.now().strftime("%Y%m%d"), adjust="", timeout=30,
            )
            if frame.empty or raw_frame.empty:
                raise RuntimeError("接口返回空数据")
            return normalize_stock(frame), "AkShare / 东方财富后复权行情", None, float(raw_frame.iloc[-1]["收盘"])
        except Exception as exc:
            errors.append(f"AkShare: {type(exc).__name__}: {exc}")
            if attempt < retries:
                time.sleep(2 * attempt)
    try:
        print("[后备通道] 分段拉取腾讯证券后复权行情...")
        frame, current_price = fetch_stock_with_tencent()
        return frame, "腾讯证券后复权行情（AkShare TLS 后备）", "; ".join(errors), current_price
    except Exception as exc:
        errors.append(f"腾讯: {type(exc).__name__}: {exc}")
    if allow_cache and STOCK_PATH.exists():
        cached = pd.read_csv(STOCK_PATH)
        cached["日期"] = pd.to_datetime(cached["日期"], errors="coerce")
        cached_meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {}
        current_price = cached_meta.get("current_stock_price")
        if current_price is None:
            raise RuntimeError("股价缓存缺少最新实际交易价")
        return cached, "本地股价缓存", "; ".join(errors), float(current_price)
    raise RuntimeError("所有股价数据通道均失败：" + "; ".join(errors))


def prepare_stock_data(daily: pd.DataFrame) -> pd.DataFrame:
    daily = normalize_stock(daily)
    daily["季度"] = daily["日期"].dt.to_period("Q").astype(str)
    quarterly = daily.groupby("季度", as_index=False).agg(
        季末后复权收盘价=("收盘", "last"),
        季内最高价=("最高", "max"),
        季内最低价=("最低", "min"),
    )
    quarterly["报告日期"] = pd.PeriodIndex(quarterly["季度"], freq="Q").end_time.normalize()
    quarterly["股价季度收益_%"] = quarterly["季末后复权收盘价"].pct_change() * 100
    quarterly["股价年度收益_%"] = quarterly["季末后复权收盘价"].pct_change(4) * 100
    return quarterly


def prepare_price_data(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = daily.copy().sort_values("日期").drop_duplicates("日期", keep="last")
    numeric_columns = [c for c in daily.columns if c != "日期"]
    for column in numeric_columns:
        daily[column] = pd.to_numeric(daily[column], errors="coerce")
    daily = daily[daily["成交均价"] > 0].copy()
    daily["价格_元每公斤"] = daily["成交均价"]
    daily["季度"] = daily["日期"].dt.to_period("Q").astype(str)

    quarterly = daily.groupby("季度", as_index=False).agg(
        季度均价_元每公斤=("价格_元每公斤", "mean"),
        季末价格_元每公斤=("价格_元每公斤", "last"),
        季内最高_元每公斤=("价格_元每公斤", "max"),
        季内最低_元每公斤=("价格_元每公斤", "min"),
        交易日数=("日期", "count"),
    )
    quarterly["报告日期"] = pd.PeriodIndex(quarterly["季度"], freq="Q").end_time.normalize()
    quarterly["猪价环比_%"] = quarterly["季度均价_元每公斤"].pct_change() * 100
    quarterly["猪价同比_%"] = quarterly["季度均价_元每公斤"].pct_change(4) * 100
    quarterly["四季均线"] = quarterly["季度均价_元每公斤"].rolling(4, min_periods=2).mean()
    quarterly["猪周期阶段"] = quarterly.apply(classify_cycle, axis=1)
    return daily, quarterly


def classify_cycle(row: pd.Series) -> str:
    price, moving, qoq = row["季度均价_元每公斤"], row["四季均线"], row["猪价环比_%"]
    if pd.isna(qoq) or pd.isna(moving):
        return "观察期"
    if qoq >= 5 and price >= moving:
        return "上行期"
    if qoq <= -5 and price < moving:
        return "下行期"
    return "高位震荡" if price >= moving else "低位筑底"


def read_report(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"缺少 {path}，请先运行 python scripts/fetch_financial_reports.py"
        )
    frame = pd.read_csv(path)
    frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"], errors="coerce")
    return frame.dropna(subset=["REPORT_DATE"])


def cumulative_to_quarter(frame: pd.DataFrame, column: str) -> pd.Series:
    ordered = frame.sort_values("REPORT_DATE").copy()
    result = pd.Series(index=ordered.index, dtype=float)
    for _, group in ordered.groupby(ordered["REPORT_DATE"].dt.year):
        values = pd.to_numeric(group[column], errors="coerce")
        result.loc[group.index] = values.diff().fillna(values)
    return result.reindex(frame.index)


def prepare_financial_data() -> pd.DataFrame:
    single = read_report("主要财务指标_按单季度.csv")
    cash = read_report("现金流量表_按报告期.csv")
    single_columns = [
        "REPORT_DATE", "SEASON_LABEL", "TOTALOPERATEREVE", "PARENTNETPROFIT",
        "TOTALOPERATEREVETZ", "PARENTNETPROFITTZ", "GROSS_PROFIT_RATIO",
        "NET_PROFIT_RATIO", "ROE_DILUTED",
    ]
    financial = single[[c for c in single_columns if c in single]].copy()
    cash["单季经营现金流"] = cumulative_to_quarter(cash, "NETCASH_OPERATE")
    cash["单季资本开支"] = cumulative_to_quarter(cash, "CONSTRUCT_LONG_ASSET")
    cash["单季自由现金流"] = cash["单季经营现金流"] - cash["单季资本开支"]
    financial = financial.merge(
        cash[["REPORT_DATE", "单季经营现金流", "单季自由现金流"]],
        on="REPORT_DATE", how="left", validate="one_to_one",
    )
    financial = financial.rename(columns={
        "REPORT_DATE": "报告日期", "SEASON_LABEL": "报告期",
        "TOTALOPERATEREVE": "单季营业收入", "PARENTNETPROFIT": "单季归母净利润",
        "TOTALOPERATEREVETZ": "营收同比_%", "PARENTNETPROFITTZ": "归母净利润同比_%",
        "GROSS_PROFIT_RATIO": "毛利率_%", "NET_PROFIT_RATIO": "净利率_%",
        "ROE_DILUTED": "摊薄ROE_%",
    })
    for column in financial.columns:
        if column not in {"报告日期", "报告期"}:
            financial[column] = pd.to_numeric(financial[column], errors="coerce")
    financial["单季营业收入_亿元"] = financial["单季营业收入"] / 1e8
    financial["单季归母净利润_亿元"] = financial["单季归母净利润"] / 1e8
    financial["单季经营现金流_亿元"] = financial["单季经营现金流"] / 1e8
    financial["单季自由现金流_亿元"] = financial["单季自由现金流"] / 1e8
    return financial.sort_values("报告日期")


def strength(coefficient: float) -> str:
    absolute = abs(coefficient)
    if absolute >= 0.7:
        return "强"
    if absolute >= 0.4:
        return "中等"
    if absolute >= 0.2:
        return "弱"
    return "很弱"


def correlations(merged: pd.DataFrame) -> pd.DataFrame:
    results: list[dict[str, object]] = []
    for metric_column, metric_label in METRICS.items():
        for lag in range(5):
            pairs = pd.DataFrame({
                "price": merged["季度均价_元每公斤"].shift(lag),
                "metric": merged[metric_column],
            }).dropna()
            if len(pairs) < 8:
                continue
            pearson = pairs["price"].corr(pairs["metric"], method="pearson")
            spearman = pairs["price"].corr(pairs["metric"], method="spearman")
            results.append({
                "经营指标": metric_label, "猪价领先季度数": lag,
                "Pearson相关系数": pearson, "Spearman相关系数": spearman,
                "样本数": len(pairs), "相关强度": strength(pearson),
            })
    return pd.DataFrame(results)


def stock_driver_correlations(merged: pd.DataFrame) -> pd.DataFrame:
    drivers = {
        "猪价环比_%": "猪价环比",
        "猪价同比_%": "猪价同比",
        "营收同比_%": "营收同比",
        "毛利率_%": "毛利率",
    }
    results: list[dict[str, object]] = []
    for column, label in drivers.items():
        for lag in range(-4, 5):
            pairs = pd.DataFrame({
                "driver": merged[column].shift(lag),
                "return": merged["股价季度收益_%"],
            }).dropna()
            if len(pairs) < 12:
                continue
            coefficient = pairs["driver"].corr(pairs["return"])
            if lag > 0:
                relation = f"{label}领先股价{lag}季"
            elif lag < 0:
                relation = f"股价领先{label}{-lag}季"
            else:
                relation = "同期"
            results.append({
                "驱动指标": label, "季度位移": lag, "关系说明": relation,
                "Pearson相关系数": coefficient,
                "Spearman相关系数": pairs["driver"].corr(pairs["return"], method="spearman"),
                "样本数": len(pairs), "相关强度": strength(coefficient),
            })
    return pd.DataFrame(results)


def target_price_scenarios(
    merged: pd.DataFrame, current_price: float
) -> tuple[pd.DataFrame, dict[str, float]]:
    model = pd.DataFrame({
        "stock_return": merged["季末后复权收盘价"].shift(-4) / merged["季末后复权收盘价"] - 1,
        "pork_change": merged["季度均价_元每公斤"].shift(-4) / merged["季度均价_元每公斤"] - 1,
        "revenue_growth": merged["营收同比_%"].shift(-4) / 100,
    }).dropna()
    if len(model) < 20:
        raise ValueError(f"目标价模型样本不足: {len(model)}")
    x = np.column_stack([np.ones(len(model)), model["pork_change"], model["revenue_growth"]])
    y = model["stock_return"].to_numpy()
    coefficients = np.linalg.lstsq(x, y, rcond=None)[0]
    fitted = x @ coefficients
    residual_std = float(np.sqrt(np.sum((y - fitted) ** 2) / max(len(y) - x.shape[1], 1)))
    total_variance = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1 - float(np.sum((y - fitted) ** 2)) / total_variance if total_variance else np.nan

    assumptions = [
        ("保守", 0.10, 0.05),
        ("基准", 0.20, 0.15),
        ("乐观", 0.30, 0.25),
    ]
    rows: list[dict[str, object]] = []
    for name, pork_change, revenue_growth in assumptions:
        predicted_return = float(coefficients @ np.array([1, pork_change, revenue_growth]))
        low_return = predicted_return - residual_std
        high_return = predicted_return + residual_std
        rows.append({
            "情景": name, "未来一年猪价涨幅_%": pork_change * 100,
            "未来一年营收增速_%": revenue_growth * 100,
            "预计股价收益_%": predicted_return * 100,
            "统计目标价_元": max(0, current_price * (1 + predicted_return)),
            "目标价下沿_元": max(0, current_price * (1 + low_return)),
            "目标价上沿_元": max(0, current_price * (1 + high_return)),
        })
    stats = {
        "intercept": float(coefficients[0]), "pork_beta": float(coefficients[1]),
        "revenue_beta": float(coefficients[2]), "residual_std": residual_std,
        "r_squared": r_squared, "sample_size": float(len(model)),
    }
    return pd.DataFrame(rows), stats


def regression_stats(merged: pd.DataFrame, metric: str, lag: int) -> tuple[float, float, int]:
    pairs = pd.DataFrame({
        "x": merged["季度均价_元每公斤"].shift(lag), "y": merged[metric]
    }).dropna()
    if len(pairs) < 8:
        return float("nan"), float("nan"), len(pairs)
    slope, intercept = np.polyfit(pairs["x"], pairs["y"], 1)
    predicted = slope * pairs["x"] + intercept
    denominator = ((pairs["y"] - pairs["y"].mean()) ** 2).sum()
    r_squared = 1 - ((pairs["y"] - predicted) ** 2).sum() / denominator if denominator else np.nan
    return float(slope), float(r_squared), len(pairs)


def figure_layout(fig: go.Figure, title: str, subtitle: str, height: int = 430) -> None:
    fig.update_layout(
        title={"text": f"{title}<br><sup>{subtitle}</sup>", "x": 0, "xanchor": "left"},
        height=height, margin={"l": 58, "r": 48, "t": 88, "b": 52},
        paper_bgcolor=COLORS["paper"], plot_bgcolor=COLORS["paper"],
        font={"family": "Microsoft YaHei UI, sans-serif", "color": COLORS["ink"]},
        hovermode="x unified", legend={"orientation": "h", "y": 1.04, "x": 1, "xanchor": "right"},
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["grid"])
    fig.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["muted"])


def trace(x: pd.Series, y: pd.Series, name: str, color: str, suffix: str = "") -> go.Scatter:
    return go.Scatter(
        x=x, y=y, name=name, mode="lines+markers",
        line={"color": color, "width": 2.5},
        marker={"size": 6, "color": COLORS["paper"], "line": {"color": color, "width": 2}},
        hovertemplate=f"%{{y:,.2f}}{suffix}<extra>{name}</extra>",
    )


def build_figures(merged: pd.DataFrame, corr: pd.DataFrame) -> list[str]:
    x = merged["报告日期"]
    figures: list[go.Figure] = []

    price = go.Figure()
    price.add_trace(trace(x, merged["季度均价_元每公斤"], "季度均价", COLORS["red"], "元/公斤"))
    price.add_trace(trace(x, merged["四季均线"], "四季均线", COLORS["ink"], "元/公斤"))
    figure_layout(price, "猪价周期", "行情宝全国生猪成交均价，周度数据聚合为季度均价")
    price.update_yaxes(title_text="元/公斤")
    figures.append(price)

    market = make_subplots(specs=[[{"secondary_y": True}]])
    market.add_trace(trace(x, merged["季度均价_元每公斤"], "生猪价格", COLORS["red"], "元/公斤"), secondary_y=False)
    market.add_trace(trace(x, merged["季末后复权收盘价"], "牧原后复权股价", COLORS["blue"], "元"), secondary_y=True)
    market.update_yaxes(title_text="生猪价格（元/公斤）", secondary_y=False)
    market.update_yaxes(title_text="牧原后复权股价（元）", secondary_y=True)
    figure_layout(market, "猪价与股价趋势", "季度末后复权收盘价用于计算跨期收益并避免早期前复权负值")
    figures.append(market)

    return_cycle = go.Figure()
    return_cycle.add_trace(go.Bar(
        x=x, y=merged["股价季度收益_%"], name="股价季度收益",
        marker_color=np.where(merged["股价季度收益_%"] >= 0, COLORS["red"], COLORS["green"]),
        hovertemplate="%{y:.1f}%<extra>股价季度收益</extra>",
    ))
    return_cycle.add_trace(trace(x, merged["猪价环比_%"], "猪价环比", COLORS["ink"], "%"))
    return_cycle.update_yaxes(title_text="季度变化（%）")
    figure_layout(return_cycle, "市场预期与猪价变化", "股价可能提前交易周期反转，因此同时检查领先与滞后相关")
    figures.append(return_cycle)

    revenue_stock = go.Figure()
    revenue_stock.add_trace(go.Bar(
        x=x, y=merged["股价季度收益_%"], name="股价季度收益",
        marker_color=COLORS["blue"], opacity=.72,
        hovertemplate="%{y:.1f}%<extra>股价季度收益</extra>",
    ))
    revenue_stock.add_trace(trace(x, merged["营收同比_%"], "营收同比", COLORS["amber"], "%"))
    revenue_stock.update_yaxes(title_text="百分比（%）")
    figure_layout(revenue_stock, "股价与营收增长", "营收受猪价与出栏量共同驱动；股价通常交易未来而非已披露数字")
    figures.append(revenue_stock)

    margin = make_subplots(specs=[[{"secondary_y": True}]])
    margin.add_trace(trace(x, merged["季度均价_元每公斤"], "生猪价格", COLORS["red"], "元/公斤"), secondary_y=False)
    margin.add_trace(trace(x, merged["毛利率_%"], "毛利率", COLORS["green"], "%"), secondary_y=True)
    margin.add_trace(trace(x, merged["净利率_%"], "净利率", COLORS["blue"], "%"), secondary_y=True)
    margin.update_yaxes(title_text="生猪价格（元/公斤）", secondary_y=False)
    margin.update_yaxes(title_text="利润率（%）", secondary_y=True)
    figure_layout(margin, "价格向盈利的传导", "牧原股份单季度口径；价格与利润率共振通常比营收更明显")
    figures.append(margin)

    operations = make_subplots(specs=[[{"secondary_y": True}]])
    operations.add_trace(trace(x, merged["季度均价_元每公斤"], "生猪价格", COLORS["red"], "元/公斤"), secondary_y=False)
    operations.add_trace(trace(x, merged["单季归母净利润_亿元"], "归母净利润", COLORS["green"], "亿元"), secondary_y=True)
    operations.add_trace(trace(x, merged["单季经营现金流_亿元"], "经营现金流", COLORS["violet"], "亿元"), secondary_y=True)
    operations.update_yaxes(title_text="生猪价格（元/公斤）", secondary_y=False)
    operations.update_yaxes(title_text="亿元", secondary_y=True)
    figure_layout(operations, "价格与经营结果", "利润和现金流同时受成本、出栏量、套保与产能利用率影响")
    figures.append(operations)

    pivot = corr.pivot(index="经营指标", columns="猪价领先季度数", values="Pearson相关系数")
    heatmap = go.Figure(go.Heatmap(
        z=pivot.values, x=[f"领先 {int(v)} 季" for v in pivot.columns], y=pivot.index,
        zmin=-1, zmax=1, colorscale=[[0, COLORS["blue"]], [0.5, "#f4f2eb"], [1, COLORS["red"]]],
        text=np.round(pivot.values, 2), texttemplate="%{text}", colorbar={"title": "Pearson"},
        hovertemplate="%{y}<br>%{x}<br>相关系数 %{z:.3f}<extra></extra>",
    ))
    figure_layout(heatmap, "滞后相关矩阵", "领先 1 季表示用上一季度猪价解释本季度经营指标；红为正相关，蓝为负相关", 390)
    figures.append(heatmap)

    best_margin = corr[corr["经营指标"] == "毛利率"].iloc[
        corr[corr["经营指标"] == "毛利率"]["Pearson相关系数"].abs().argmax()
    ]
    lag = int(best_margin["猪价领先季度数"])
    scatter_data = pd.DataFrame({
        "price": merged["季度均价_元每公斤"].shift(lag),
        "margin": merged["毛利率_%"], "period": merged["季度"],
    }).dropna()
    slope, intercept = np.polyfit(scatter_data["price"], scatter_data["margin"], 1)
    line_x = np.linspace(scatter_data["price"].min(), scatter_data["price"].max(), 100)
    scatter = go.Figure()
    scatter.add_trace(go.Scatter(
        x=scatter_data["price"], y=scatter_data["margin"], text=scatter_data["period"],
        mode="markers", name="季度样本", marker={"size": 10, "color": COLORS["red"], "opacity": .75},
        hovertemplate="%{text}<br>猪价 %{x:.2f}元/公斤<br>毛利率 %{y:.2f}%<extra></extra>",
    ))
    scatter.add_trace(go.Scatter(
        x=line_x, y=slope * line_x + intercept, mode="lines", name="线性拟合",
        line={"color": COLORS["ink"], "width": 2, "dash": "dash"},
    ))
    scatter.update_xaxes(title_text=f"猪价（元/公斤，领先 {lag} 季）")
    scatter.update_yaxes(title_text="毛利率（%）")
    figure_layout(scatter, "猪价与毛利率散点", "每个点代表一个财报季度；拟合线用于描述样本关系，不是预测模型")
    figures.append(scatter)

    blocks: list[str] = []
    for index, fig in enumerate(figures):
        blocks.append(fig.to_html(
            full_html=False, include_plotlyjs=True if index == 0 else False,
            config={"displaylogo": False, "responsive": True, "locale": "zh-CN"},
        ))
    return blocks


def fmt(value: float, suffix: str = "", digits: int = 2) -> str:
    return "--" if pd.isna(value) else f"{value:,.{digits}f}{suffix}"


def build_report(
    merged: pd.DataFrame,
    corr: pd.DataFrame,
    stock_corr: pd.DataFrame,
    scenarios: pd.DataFrame,
    model_stats: dict[str, float],
    current_stock_price: float,
    source: str,
    stock_source: str,
) -> str:
    best_rows = corr.loc[corr.groupby("经营指标")["Pearson相关系数"].apply(lambda s: s.abs().idxmax())].copy()
    best_rows = best_rows.sort_values("Pearson相关系数", key=lambda s: s.abs(), ascending=False)
    margin_row = best_rows[best_rows["经营指标"] == "毛利率"].iloc[0]
    profit_row = best_rows[best_rows["经营指标"] == "归母净利润"].iloc[0]
    margin_slope, margin_r2, margin_n = regression_stats(merged, "毛利率_%", int(margin_row["猪价领先季度数"]))
    latest = merged.iloc[-1]
    best_stock_rows = stock_corr.loc[
        stock_corr.groupby("驱动指标")["Pearson相关系数"].apply(lambda s: s.abs().idxmax())
    ].sort_values("Pearson相关系数", key=lambda s: s.abs(), ascending=False)
    pork_stock_row = best_stock_rows[best_stock_rows["驱动指标"] == "猪价环比"].iloc[0]
    revenue_stock_row = best_stock_rows[best_stock_rows["驱动指标"] == "营收同比"].iloc[0]
    base_scenario = scenarios[scenarios["情景"] == "基准"].iloc[0]
    expected_direction = "偏上行" if base_scenario["预计股价收益_%"] > 0 else "偏下行"

    if abs(margin_row["Pearson相关系数"]) >= 0.7:
        conclusion = "样本内，猪价与牧原盈利能力呈强相关"
    elif abs(margin_row["Pearson相关系数"]) >= 0.4:
        conclusion = "样本内，猪价与牧原盈利能力呈中等相关"
    else:
        conclusion = "样本内，猪价与牧原盈利能力相关性有限"

    summary_cards = f"""
      <div class="signal"><span>核心判断</span><strong>{html.escape(conclusion)}</strong><small>以毛利率最强滞后关系判断</small></div>
      <div class="signal"><span>毛利率最强相关</span><strong>{margin_row['Pearson相关系数']:+.2f}</strong><small>猪价领先 {int(margin_row['猪价领先季度数'])} 季 · n={int(margin_row['样本数'])}</small></div>
      <div class="signal"><span>净利润最强相关</span><strong>{profit_row['Pearson相关系数']:+.2f}</strong><small>猪价领先 {int(profit_row['猪价领先季度数'])} 季 · n={int(profit_row['样本数'])}</small></div>
      <div class="signal"><span>基准情景方向</span><strong>{expected_direction}</strong><small>猪价 +20% · 营收 +15%</small></div>
      <div class="signal"><span>12个月统计目标价</span><strong>{base_scenario['统计目标价_元']:.2f}元</strong><small>当前 {current_stock_price:.2f}元 · 区间 {base_scenario['目标价下沿_元']:.2f}—{base_scenario['目标价上沿_元']:.2f}</small></div>"""

    best_table_rows = "".join(
        f"<tr><td>{html.escape(str(row['经营指标']))}</td><td>{int(row['猪价领先季度数'])} 季</td>"
        f"<td class={'positive' if row['Pearson相关系数'] >= 0 else 'negative'}>{row['Pearson相关系数']:+.3f}</td>"
        f"<td>{row['Spearman相关系数']:+.3f}</td><td>{html.escape(str(row['相关强度']))}</td><td>{int(row['样本数'])}</td></tr>"
        for _, row in best_rows.iterrows()
    )

    phase = merged.groupby("猪周期阶段", as_index=False).agg(
        季度数=("季度", "count"), 平均猪价=("季度均价_元每公斤", "mean"),
        平均毛利率=("毛利率_%", "mean"), 平均净利率=("净利率_%", "mean"),
        平均归母净利润=("单季归母净利润_亿元", "mean"),
    ).sort_values("平均猪价", ascending=False)
    phase_rows = "".join(
        f"<tr><td><i class='phase-dot {html.escape(str(row['猪周期阶段']))}'></i>{html.escape(str(row['猪周期阶段']))}</td>"
        f"<td>{int(row['季度数'])}</td><td>{row['平均猪价']:.2f}</td><td>{row['平均毛利率']:.1f}%</td>"
        f"<td>{row['平均净利率']:.1f}%</td><td>{row['平均归母净利润']:.1f}亿</td></tr>" for _, row in phase.iterrows()
    )

    stock_corr_rows = "".join(
        f"<tr><td>{html.escape(str(row['驱动指标']))}</td><td>{html.escape(str(row['关系说明']))}</td>"
        f"<td class={'positive' if row['Pearson相关系数'] >= 0 else 'negative'}>{row['Pearson相关系数']:+.3f}</td>"
        f"<td>{row['Spearman相关系数']:+.3f}</td><td>{int(row['样本数'])}</td></tr>"
        for _, row in best_stock_rows.iterrows()
    )
    scenario_rows = "".join(
        f"<tr><td>{html.escape(str(row['情景']))}</td><td>+{row['未来一年猪价涨幅_%']:.0f}%</td>"
        f"<td>+{row['未来一年营收增速_%']:.0f}%</td><td>{row['预计股价收益_%']:+.1f}%</td>"
        f"<td><strong>{row['统计目标价_元']:.2f}元</strong></td>"
        f"<td>{row['目标价下沿_元']:.2f}—{row['目标价上沿_元']:.2f}元</td></tr>"
        for _, row in scenarios.iterrows()
    )

    timeline_rows = "".join(
        f"<tr><td>{html.escape(str(row['季度']))}</td><td>{html.escape(str(row['猪周期阶段']))}</td>"
        f"<td>{row['季度均价_元每公斤']:.2f}</td><td>{fmt(row['猪价同比_%'], '%', 1)}</td>"
        f"<td>{fmt(row['毛利率_%'], '%', 1)}</td><td>{fmt(row['净利率_%'], '%', 1)}</td>"
        f"<td>{fmt(row['单季归母净利润_亿元'], '亿', 1)}</td><td>{fmt(row['股价季度收益_%'], '%', 1)}</td>"
        f"<td>{fmt(row['季末后复权收盘价'], '元', 2)}</td></tr>"
        for _, row in merged.sort_values("报告日期", ascending=False).iterrows()
    )
    charts = "".join(f'<section class="chart">{block}</section>' for block in build_figures(merged, corr))
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>猪周期 × 牧原经营 × 股价</title>
<style>
:root{{--paper:#f4f2eb;--ink:#1f2421;--muted:#74776f;--line:#d4d6cf;--red:#b83b31;--green:#2c7358;--blue:#2f6c89;--amber:#bb7a17}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei UI","Microsoft YaHei",sans-serif;letter-spacing:0}}
.shell{{width:min(1180px,calc(100% - 48px));margin:auto}} header{{padding:44px 0 26px;border-bottom:1px solid var(--ink)}}
.meta{{display:flex;justify-content:space-between;color:var(--muted);font-size:11px}} h1{{margin:22px 0 10px;font:500 clamp(38px,6vw,72px)/1 "STZhongsong","SimSun",serif}}
.lead{{max-width:760px;margin:0;color:var(--muted);line-height:1.7;font-size:14px}} .signals{{display:grid;grid-template-columns:1.45fr repeat(4,1fr);border-bottom:1px solid var(--ink)}}
.signal{{min-width:0;padding:24px 18px;border-right:1px solid var(--line)}}.signal:first-child{{padding-left:0}}.signal:last-child{{border:0}}
.signal span,.signal small{{display:block;color:var(--muted);font-size:10px}}.signal strong{{display:block;margin:10px 0 8px;font:500 19px/1.35 "STZhongsong","SimSun",serif}}
.section-head{{display:flex;justify-content:space-between;align-items:end;gap:28px;padding:58px 0 17px;border-bottom:1px solid var(--ink)}} h2{{margin:0;font:500 30px/1 "STZhongsong","SimSun",serif}}
.section-head p{{max-width:660px;margin:0;text-align:right;color:var(--muted);font-size:11px;line-height:1.7}}.chart{{padding:10px 0;border-bottom:1px solid var(--line);overflow:hidden}}
.tables{{display:grid;grid-template-columns:1fr 1fr;gap:38px;margin:22px 0 12px}} table{{width:100%;border-collapse:collapse;font-size:12px}}caption{{padding:0 0 12px;text-align:left;font:500 18px "STZhongsong","SimSun",serif}}
th{{color:var(--muted);font-weight:400;text-align:left}}th,td{{padding:10px 8px;border-bottom:1px solid var(--line);white-space:nowrap}}th:first-child,td:first-child{{padding-left:0}}.positive{{color:var(--red)}}.negative{{color:var(--blue)}}
.phase-dot{{display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:var(--blue)}}.phase-dot.上行期{{background:var(--red)}}.phase-dot.下行期{{background:var(--green)}}.phase-dot.高位震荡{{background:var(--amber)}}
.timeline-wrap{{overflow-x:auto;margin:18px 0 46px}}.timeline-table{{min-width:820px}}.note{{padding:20px 0;margin:18px 0 54px;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);color:var(--muted);font-size:11px;line-height:1.8}}
footer{{border-top:1px solid var(--ink);padding:24px 0 38px;color:var(--muted);font-size:10px}}
@media(max-width:800px){{.shell{{width:calc(100% - 28px)}}.meta{{flex-direction:column;gap:4px}}.signals{{grid-template-columns:1fr 1fr}}.signal:nth-child(2){{border-right:0}}.signal:first-child{{padding-left:18px}}.section-head{{align-items:flex-start;flex-direction:column}}.section-head p{{text-align:left}}.tables{{grid-template-columns:1fr;gap:28px;overflow-x:auto}}}}
</style></head><body><div class="shell">
<header><div class="meta"><span>周期研究 / SZ.002714</span><span>联合样本 {merged['报告日期'].min():%Y-%m-%d} — {merged['报告日期'].max():%Y-%m-%d}</span></div><h1>猪周期 × 经营 × 股价</h1><p class="lead">把全国生猪成交均价、牧原单季度经营指标和后复权股价放在同一时间轴，检验市场如何交易周期，并用明确的猪价与营收假设估算情景目标价。</p></header>
<section class="signals">{summary_cards}</section>
<div class="section-head"><h2>周期与经营共振</h2><p>价格采用行情宝全国生猪成交均价，覆盖 2015 年以来多个完整周期；公司指标使用单季度口径。</p></div>{charts}
<div class="section-head"><h2>股价联动与目标价</h2><p>相关性使用季度后复权收益率，避免分红送转和早期前复权负值造成失真；目标价是未来一年猪价和营收情景的历史回归结果，不是基本面估值。</p></div>
<div class="tables"><table><caption>股价最强领先/滞后关系</caption><thead><tr><th>驱动指标</th><th>时序关系</th><th>Pearson</th><th>Spearman</th><th>n</th></tr></thead><tbody>{stock_corr_rows}</tbody></table>
<table><caption>12个月情景目标价</caption><thead><tr><th>情景</th><th>猪价</th><th>营收</th><th>股价收益</th><th>目标价</th><th>残差区间</th></tr></thead><tbody>{scenario_rows}</tbody></table></div>
<div class="note"><strong>如何理解“猪肉涨价后股价怎么走”：</strong>历史最强关系为“{html.escape(str(pork_stock_row['关系说明']))}”，Pearson={pork_stock_row['Pearson相关系数']:+.3f}；营收关系为“{html.escape(str(revenue_stock_row['关系说明']))}”，Pearson={revenue_stock_row['Pearson相关系数']:+.3f}。基准情景假设未来一年猪价上涨20%、营收增长15%，模型方向为<strong>{expected_direction}</strong>，统计目标价 {base_scenario['统计目标价_元']:.2f} 元。模型 R²={model_stats['r_squared']:.2f}，n={int(model_stats['sample_size'])}，残差标准差={model_stats['residual_std']:.1%}，区间较宽正是周期股不确定性的真实反映。<br><strong>股价数据源：</strong>{html.escape(stock_source)}；当前价取 {current_stock_price:.2f} 元。后复权价只用于收益计算，目标价以最新实际交易价为基准。</div>
<div class="section-head"><h2>统计结论</h2><p>每项指标展示绝对值最大的 0—4 季领先关系。领先期是在样本中择优，存在多重比较偏差，不能直接用于预测。</p></div>
<div class="tables"><table><caption>最强滞后相关</caption><thead><tr><th>经营指标</th><th>猪价领先</th><th>Pearson</th><th>Spearman</th><th>强度</th><th>n</th></tr></thead><tbody>{best_table_rows}</tbody></table>
<table><caption>周期阶段均值</caption><thead><tr><th>阶段</th><th>季度</th><th>猪价</th><th>毛利率</th><th>净利率</th><th>净利润</th></tr></thead><tbody>{phase_rows}</tbody></table></div>
<div class="note"><strong>毛利率敏感度：</strong>在毛利率最强相关的领先 {int(margin_row['猪价领先季度数'])} 季口径下，单变量线性拟合显示猪价每提高 1 元/公斤，毛利率平均变化 {margin_slope:+.2f} 个百分点，R²={margin_r2:.2f}，n={margin_n}。这只是样本描述；饲料成本、非洲猪瘟、产能、出栏结构、会计减值和公司成本下降都会改变传导幅度。<br><strong>数据源：</strong>{html.escape(source)}。成交均价比终端猪肉零售价更贴近养殖企业销售端，但仍不等于牧原自身商品猪结算价。</div>
<div class="section-head"><h2>逐季对照</h2><p>用同一时间轴查看周期位置与经营结果，便于识别价格上行是否已经传导到报表。</p></div>
<div class="timeline-wrap"><table class="timeline-table"><thead><tr><th>季度</th><th>周期阶段</th><th>猪价</th><th>猪价同比</th><th>毛利率</th><th>净利率</th><th>归母净利</th><th>股价收益</th><th>季末复权价</th></tr></thead><tbody>{timeline_rows}</tbody></table></div>
</div><footer><div class="shell">生成于 {generated} · 相关性不等于因果，不构成投资建议</div></footer></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="拉取生猪价格并分析猪周期与牧原股份经营相关性")
    parser.add_argument("--retries", type=int, default=2, help="AkShare 最大尝试次数")
    parser.add_argument("--no-cache", action="store_true", help="联网失败时禁止使用已有缓存")
    args = parser.parse_args()
    if args.retries < 1:
        parser.error("--retries 必须大于 0")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    daily, source, fetch_warning = fetch_price(args.retries, not args.no_cache)
    daily, quarterly = prepare_price_data(daily)
    atomic_csv(daily, DAILY_PATH)
    atomic_csv(quarterly, QUARTERLY_PATH)

    stock_daily, stock_source, stock_fetch_warning, current_stock_price = fetch_stock(
        args.retries, not args.no_cache
    )
    atomic_csv(stock_daily, STOCK_PATH)
    stock_quarterly = prepare_stock_data(stock_daily)

    financial = prepare_financial_data()
    merged = quarterly.merge(financial, on="报告日期", how="inner", validate="one_to_one")
    merged = merged.merge(
        stock_quarterly.drop(columns="季度"), on="报告日期", how="inner", validate="one_to_one"
    )
    merged = merged.sort_values("报告日期").reset_index(drop=True)
    if len(merged) < 12:
        raise SystemExit(f"共同季度只有 {len(merged)} 个，样本不足以进行相关性分析")
    corr = correlations(merged)
    stock_corr = stock_driver_correlations(merged)
    scenarios, model_stats = target_price_scenarios(merged, current_stock_price)
    atomic_csv(merged, MERGED_PATH)
    atomic_csv(corr, CORR_PATH)
    atomic_csv(stock_corr, STOCK_CORR_PATH)
    atomic_csv(scenarios, TARGET_PATH)
    REPORT_PATH.write_text(
        build_report(
            merged, corr, stock_corr, scenarios, model_stats,
            current_stock_price, source, stock_source,
        ),
        encoding="utf-8",
    )

    metadata = {
        "price_measure": "行情宝全国生猪成交均价",
        "unit": "元/公斤",
        "source": source,
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "observation_start": daily["日期"].min().strftime("%Y-%m-%d"),
        "observation_end": daily["日期"].max().strftime("%Y-%m-%d"),
        "observation_frequency": "周度为主",
        "observation_rows": len(daily), "matched_quarters": len(merged),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fetch_warning": fetch_warning,
        "stock_source": stock_source,
        "stock_observation_start": stock_daily["日期"].min().strftime("%Y-%m-%d"),
        "stock_observation_end": stock_daily["日期"].max().strftime("%Y-%m-%d"),
        "current_stock_price": current_stock_price,
        "stock_fetch_warning": stock_fetch_warning,
        "target_price_model": {
            "horizon": "12个月",
            "method": "同期未来猪价涨幅与营收增速解释后复权股价收益的 OLS 情景回归",
            **model_stats,
        },
        "limitations": [
            "行情宝序列始于 2015 年，缺少牧原上市首年 2014 年数据",
            "全国成交均价不等同于牧原自身商品猪结算价或终端猪肉零售价",
            "样本相关性不代表因果关系，滞后期择优存在多重比较偏差",
        ],
    }
    META_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"生猪历史价格: {DAILY_PATH} ({len(daily)} 行)")
    print(f"季度匹配数据: {MERGED_PATH} ({len(merged)} 个季度)")
    print(f"相关性结果: {CORR_PATH}")
    print(f"股价联动结果: {STOCK_CORR_PATH}")
    print(f"情景目标价: {TARGET_PATH}")
    print(f"可视化报告: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
