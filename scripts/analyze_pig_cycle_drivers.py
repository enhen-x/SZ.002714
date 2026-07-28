#!/usr/bin/env python3
"""分析猪周期形成机制、决定因素，并对当前周期顶部作条件预测。"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import subprocess
import urllib.parse
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

RAW_PATH = DATA_DIR / "猪周期驱动因子_原始.json"
PANEL_PATH = DATA_DIR / "猪周期驱动因子_月度.csv"
CAPACITY_PATH = DATA_DIR / "全国生猪产能.csv"
FUTURES_PATH = DATA_DIR / "生猪期货远期曲线.csv"
FACTOR_RESULT_PATH = REPORTS_DIR / "猪周期决定因素定量分析.csv"
CYCLE_PATH = REPORTS_DIR / "猪周期历史拐点.csv"
SIGNAL_PATH = REPORTS_DIR / "猪周期当前信号.csv"
SUPPLY_SCENARIO_PATH = REPORTS_DIR / "顶部价格供给模型情景.csv"
DEPLETION_SENSITIVITY_PATH = REPORTS_DIR / "母猪去化与价格弹性.csv"
FORECAST_PATH = REPORTS_DIR / "本轮猪周期顶部预测.json"
REPORT_PATH = REPORTS_DIR / "猪周期驱动与顶部预测.html"

DRIVER_COLUMNS = [
    "仔猪价格_元每公斤", "二元母猪价格_元每公斤", "猪粮比",
    "育肥猪饲料_元每公斤", "玉米价格_元每吨", "豆粕价格_元每吨",
]

XT_MAP_URL = "https://xt.yangzhu.vip/data/getmapdata"
XT_HITS_URL = "https://xt.yangzhu.vip/data/getzhujiahitsdata"
FUTURES_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQFuturesData?page=1&sort=position&asc=0&node=lh_qh&base=futures"
)

COLORS = {
    "ink": "#202421", "paper": "#f5f3ed", "muted": "#6e726c",
    "green": "#287157", "red": "#b33b32", "amber": "#b27618",
    "blue": "#2d6985", "line": "#d3d5cf", "violet": "#76536d",
}


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    temp.replace(path)


def curl_json(url: str, post: bool = False) -> dict | list:
    executable = shutil.which("curl") or shutil.which("curl.exe")
    if not executable:
        raise RuntimeError("未找到系统 curl")
    command = [
        executable, "-k", "--http1.1", "-L", "--retry", "2", "--retry-all-errors",
        "--fail", "--silent", "--show-error", "--max-time", "60",
    ]
    if post:
        command.extend(["-X", "POST"])
    command.append(url)
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    return json.loads(completed.stdout.decode("utf-8"))


def map_url(ptype: int) -> str:
    return XT_MAP_URL + "?" + urllib.parse.urlencode({"ptype": ptype, "areano": -1})


def hits_url(ptype: int) -> str:
    return XT_HITS_URL + "?" + urllib.parse.urlencode({"ptype": ptype, "areano": -1, "datetype": 0})


def normalize_two_column(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    output = frame.iloc[:, :2].copy()
    output.columns = ["日期", name]
    output["日期"] = pd.to_datetime(output["日期"], errors="coerce")
    output[name] = pd.to_numeric(output[name], errors="coerce")
    return output.dropna(subset=["日期", name]).sort_values("日期").drop_duplicates("日期")


def fetch_simple_series(
    name: str,
    ak_fetch,
    url: str,
    raw_parser,
) -> tuple[pd.DataFrame, str, list | dict]:
    try:
        frame = ak_fetch()
        if frame is None or frame.empty:
            raise RuntimeError("AkShare 返回空数据")
        if "date" in frame.columns and "value" in frame.columns:
            normalized = frame[["date", "value"]].rename(columns={"date": "日期", "value": name})
        elif "date" in frame.columns and "benzhou" in frame.columns:
            normalized = frame[["date", "benzhou"]].rename(columns={"date": "日期", "benzhou": name})
        else:
            raise ValueError(f"未知字段: {list(frame.columns)}")
        normalized["日期"] = pd.to_datetime(normalized["日期"], errors="coerce")
        normalized[name] = pd.to_numeric(normalized[name], errors="coerce")
        normalized = normalized.dropna(subset=["日期", name]).sort_values("日期")
        return normalized, "AkShare / 玄田数据", frame.to_dict("records")
    except Exception:
        payload = curl_json(url, post=True)
        rows = (payload or {}).get("data") or []
        return raw_parser(rows, name), "玄田数据（curl TLS 后备）", rows


def parse_pair_rows(rows: list, name: str) -> pd.DataFrame:
    return normalize_two_column(pd.DataFrame(rows), name)


def parse_hits_rows(rows: list[dict], name: str) -> pd.DataFrame:
    if name == "玉米价格_元每吨":
        frame = pd.DataFrame(rows)[["pricedate", "maizeprice"]]
    else:
        frame = pd.DataFrame(rows)[["pricedate", "bean"]]
    return normalize_two_column(frame, name)


def parse_feed_rows(rows: list[dict], name: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows)[["date", "benzhou"]]
    return normalize_two_column(frame, name)


def parse_capacity_period(value: str) -> pd.Timestamp:
    text = str(value)
    if re.fullmatch(r"20\d{2}", text):
        return pd.Timestamp(f"{text}-12-31")
    year_match = re.search(r"(20\d{2})", text)
    if not year_match:
        return pd.NaT
    year = int(year_match.group(1))
    if "一季度" in text:
        return pd.Timestamp(year=year, month=3, day=31)
    if "二季度" in text:
        return pd.Timestamp(year=year, month=6, day=30)
    if "三季度" in text:
        return pd.Timestamp(year=year, month=9, day=30)
    month_match = re.search(r"(\d{1,2})月", text)
    if month_match:
        return pd.Period(year=year, month=int(month_match.group(1)), freq="M").end_time.normalize()
    return pd.Timestamp(year=year, month=12, day=31)


def fetch_capacity() -> tuple[pd.DataFrame, str, list]:
    try:
        frame = ak.futures_hog_supply(symbol="生猪产能")
        if frame is None or frame.empty:
            raise RuntimeError("AkShare 返回空数据")
        frame = frame.rename(columns={"周期": "期间", "能繁母猪存栏": "能繁母猪_万头", "猪肉产量": "猪肉产量_万吨",
                                      "生猪存栏": "生猪存栏_万头", "生猪出栏": "生猪出栏_万头"})
        raw = frame.to_dict("records")
        source = "AkShare / 玄田数据生猪产能"
    except Exception:
        payload = curl_json(map_url(7), post=True)
        raw = (payload or {}).get("data") or []
        frame = pd.DataFrame(raw, columns=["期间", "能繁母猪_万头", "猪肉产量_万吨", "生猪存栏_万头", "生猪出栏_万头"])
        source = "玄田数据生猪产能（curl TLS 后备）"
    frame["日期"] = frame["期间"].map(parse_capacity_period)
    for column in ["能繁母猪_万头", "猪肉产量_万吨", "生猪存栏_万头", "生猪出栏_万头"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").replace(0, np.nan)
    return frame.dropna(subset=["日期", "能繁母猪_万头"]).sort_values("日期"), source, raw


def fetch_futures_curve() -> tuple[pd.DataFrame, str, list]:
    try:
        frame = ak.futures_zh_realtime(symbol="生猪")
        raw = frame.to_dict("records")
        source = "AkShare / 新浪生猪期货实时行情"
    except Exception:
        raw = curl_json(FUTURES_URL)
        frame = pd.DataFrame(raw)
        source = "新浪生猪期货实时行情（curl TLS 后备）"
    frame = frame[frame["symbol"].astype(str).str.fullmatch(r"LH\d{4}")].copy()
    frame["期货价格_元每公斤"] = pd.to_numeric(frame["trade"], errors="coerce") / 1000
    frame["持仓量"] = pd.to_numeric(frame["position"], errors="coerce")
    frame["交易日期"] = pd.to_datetime(frame["tradedate"], errors="coerce")
    code = frame["symbol"].str.extract(r"LH(\d{2})(\d{2})")
    frame["交割月份"] = pd.to_datetime("20" + code[0] + "-" + code[1] + "-01", errors="coerce")
    return frame[["symbol", "name", "交割月份", "期货价格_元每公斤", "持仓量", "交易日期"]].sort_values("交割月份"), source, raw


def fetch_drivers(allow_cache: bool) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, dict[str, str]]:
    raw_payload: dict[str, object] = {}
    sources: dict[str, str] = {}
    try:
        specifications = [
            ("仔猪价格_元每公斤", lambda: ak.futures_hog_cost(symbol="仔猪价格"), map_url(2), parse_pair_rows),
            ("二元母猪价格_元每公斤", lambda: ak.futures_hog_cost(symbol="二元母猪价格"), map_url(1), parse_pair_rows),
            ("猪粮比", lambda: ak.futures_hog_supply(symbol="猪粮比价"), map_url(11), parse_pair_rows),
            ("育肥猪饲料_元每公斤", lambda: ak.futures_hog_supply(symbol="育肥猪"), map_url(9), parse_feed_rows),
            ("玉米价格_元每吨", lambda: ak.futures_hog_cost(symbol="玉米"), hits_url(4), parse_hits_rows),
            ("豆粕价格_元每吨", lambda: ak.futures_hog_cost(symbol="豆粕"), hits_url(5), parse_hits_rows),
        ]
        series: dict[str, pd.DataFrame] = {}
        for name, fetch, url, parser in specifications:
            print(f"[驱动因子] 拉取 {name}...")
            frame, source, raw = fetch_simple_series(name, fetch, url, parser)
            series[name] = frame
            sources[name] = source
            raw_payload[name] = raw
        capacity, capacity_source, capacity_raw = fetch_capacity()
        futures, futures_source, futures_raw = fetch_futures_curve()
        sources["产能"] = capacity_source
        sources["期货"] = futures_source
        raw_payload["产能"] = capacity_raw
        raw_payload["期货"] = futures_raw
        RAW_PATH.write_text(json.dumps(raw_payload, ensure_ascii=False), encoding="utf-8")
        return series, capacity, futures, sources
    except Exception as exc:
        if not allow_cache or not (PANEL_PATH.exists() and CAPACITY_PATH.exists() and FUTURES_PATH.exists()):
            raise
        print(f"[驱动因子] 联网失败，使用已有缓存: {exc}")
        panel = pd.read_csv(PANEL_PATH)
        panel["月份"] = pd.to_datetime(panel["月份"], errors="coerce")
        series = {
            column: panel[["月份", column]].rename(columns={"月份": "日期"}).dropna()
            for column in DRIVER_COLUMNS if column in panel.columns
        }
        capacity = pd.read_csv(CAPACITY_PATH)
        capacity["日期"] = pd.to_datetime(capacity["日期"], errors="coerce")
        futures = pd.read_csv(FUTURES_PATH)
        for column in ["交割月份", "交易日期"]:
            futures[column] = pd.to_datetime(futures[column], errors="coerce")
        return series, capacity, futures, {"缓存": "本地缓存"}


def build_monthly_panel(series: dict[str, pd.DataFrame]) -> pd.DataFrame:
    hog = pd.read_csv(DATA_DIR / "生猪价格_历史.csv")
    hog["日期"] = pd.to_datetime(hog["日期"], errors="coerce")
    hog["生猪价格_元每公斤"] = pd.to_numeric(hog["价格_元每公斤"], errors="coerce")
    panel = hog.set_index("日期")["生猪价格_元每公斤"].resample("ME").mean().to_frame()
    for name, frame in series.items():
        monthly = frame.set_index("日期")[name].resample("ME").mean()
        panel = panel.join(monthly, how="outer")
    panel = panel.sort_index()
    for column in panel.columns:
        panel[f"{column}_同比_%"] = panel[column].pct_change(12, fill_method=None) * 100
        panel[f"{column}_三月变化_%"] = panel[column].pct_change(3, fill_method=None) * 100
    return panel.reset_index(names="月份")


def best_lead_relation(panel: pd.DataFrame, factor: str, transform: str = "同比") -> dict[str, object]:
    target_column = "生猪价格_元每公斤_同比_%" if transform == "同比" else "生猪价格_元每公斤"
    factor_column = f"{factor}_同比_%" if transform == "同比" else factor
    best: dict[str, object] | None = None
    for lead in range(0, 16):
        pairs = pd.DataFrame({
            "factor": panel[factor_column].shift(lead),
            "target": panel[target_column],
        }).dropna()
        if len(pairs) < 18:
            continue
        coefficient = pairs["factor"].corr(pairs["target"])
        candidate = {"领先月数": lead, "Pearson相关系数": coefficient, "样本数": len(pairs)}
        if best is None or abs(coefficient) > abs(float(best["Pearson相关系数"])):
            best = candidate
    return best or {"领先月数": np.nan, "Pearson相关系数": np.nan, "样本数": 0}


def relation_at_lead(panel: pd.DataFrame, factor: str, transform: str, lead: int) -> tuple[float, int]:
    target_column = "生猪价格_元每公斤_同比_%" if transform == "同比" else "生猪价格_元每公斤"
    factor_column = f"{factor}_同比_%" if transform == "同比" else factor
    pairs = pd.DataFrame({
        "factor": panel[factor_column].shift(lead), "target": panel[target_column],
    }).dropna()
    return (float(pairs["factor"].corr(pairs["target"])), len(pairs)) if len(pairs) >= 18 else (np.nan, len(pairs))


def analyze_factors(panel: pd.DataFrame, capacity: pd.DataFrame) -> pd.DataFrame:
    mechanisms = {
        "仔猪价格_元每公斤": ("同比", 6, "与猪价高度同步；作为补栏价格信号，经育肥后约6个月影响商品猪供给"),
        "二元母猪价格_元每公斤": ("同比", 10, "与猪价同步反映补栏意愿；母猪扩张约10-12个月后影响出栏"),
        "育肥猪饲料_元每公斤": ("同比", 7, "养殖成本；高成本压缩利润并经产能退出滞后影响供给"),
        "猪粮比": ("水平", 0, "养殖利润的同步指标，包含猪价本身，不作为独立预测变量"),
        "玉米价格_元每吨": ("同比", 6, "主要饲料成本，当前历史长度不足以稳定估计"),
        "豆粕价格_元每吨": ("同比", 6, "蛋白饲料成本，当前历史长度不足以稳定估计"),
    }
    rows = []
    for factor, (transform, mechanism_lead, mechanism) in mechanisms.items():
        relation = best_lead_relation(panel, factor, transform)
        mechanism_coefficient, mechanism_n = relation_at_lead(panel, factor, transform, mechanism_lead)
        available = panel.dropna(subset=[factor])
        rows.append({
            "决定因素": factor.replace("_元每公斤", "").replace("_元每吨", ""),
            "量化口径": "同比变化" if transform == "同比" else "价格水平",
            **relation, "机制参考领先月数": mechanism_lead,
            "机制滞后相关系数": mechanism_coefficient, "机制滞后样本数": mechanism_n,
            "数据开始": available["月份"].min(), "数据截至": available["月份"].max(),
            "机制解释": mechanism,
        })

    annual_capacity = capacity[capacity["日期"].dt.month == 12].copy()
    annual_capacity["母猪同比_%"] = annual_capacity["能繁母猪_万头"].pct_change() * 100
    annual_hog = panel.set_index("月份")["生猪价格_元每公斤"].resample("YE").mean().pct_change() * 100
    capacity_pairs = pd.DataFrame({
        "母猪": annual_capacity.set_index("日期")["母猪同比_%"],
        "次年猪价": annual_hog.shift(-1),
    }).dropna()
    rows.append({
        "决定因素": "能繁母猪存栏", "量化口径": "年度同比变化",
        "领先月数": 12, "Pearson相关系数": capacity_pairs["母猪"].corr(capacity_pairs["次年猪价"]),
        "样本数": len(capacity_pairs), "机制参考领先月数": 12,
        "机制滞后相关系数": capacity_pairs["母猪"].corr(capacity_pairs["次年猪价"]),
        "机制滞后样本数": len(capacity_pairs),
        "数据开始": capacity["日期"].min(), "数据截至": capacity["日期"].max(),
        "机制解释": "最核心供给变量；母猪变化经妊娠、育肥后约10-12个月传导到出栏，预期与未来猪价负相关",
    })
    return pd.DataFrame(rows)


def month_difference(later: pd.Timestamp, earlier: pd.Timestamp) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def identify_cycles(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    data = panel.dropna(subset=["生猪价格_元每公斤"])[["月份", "生猪价格_元每公斤"]].copy()
    data["平滑价格"] = data["生猪价格_元每公斤"].rolling(3, center=True, min_periods=1).mean()
    threshold = data["平滑价格"].quantile(0.58)
    candidates = []
    for index in range(len(data)):
        left, right = max(0, index - 5), min(len(data), index + 6)
        if data.iloc[index]["平滑价格"] >= threshold and data.iloc[index]["平滑价格"] >= data.iloc[left:right]["平滑价格"].max():
            candidates.append(index)
    selected: list[int] = []
    for index in candidates:
        if selected and month_difference(data.iloc[index]["月份"], data.iloc[selected[-1]]["月份"]) < 14:
            if data.iloc[index]["平滑价格"] > data.iloc[selected[-1]]["平滑价格"]:
                selected[-1] = index
        else:
            selected.append(index)

    rows = []
    previous_peak_index = 0
    for cycle_number, peak_index in enumerate(selected, 1):
        search_start = previous_peak_index + 2 if cycle_number > 1 else 0
        trough_slice = data.iloc[search_start:peak_index + 1]
        if trough_slice.empty:
            continue
        trough_index = trough_slice["平滑价格"].idxmin()
        peak = data.iloc[peak_index]
        trough = data.loc[trough_index]
        duration = month_difference(peak["月份"], trough["月份"])
        if duration < 3:
            continue
        rows.append({
            "周期": f"周期{len(rows) + 1}", "谷底月份": trough["月份"],
            "谷底价格_元每公斤": trough["生猪价格_元每公斤"],
            "顶部月份": peak["月份"], "顶部价格_元每公斤": peak["生猪价格_元每公斤"],
            "谷底到顶部月数": duration,
            "谷底到顶部涨幅_%": (peak["生猪价格_元每公斤"] / trough["生猪价格_元每公斤"] - 1) * 100,
            "异常冲击": "非洲猪瘟供给冲击" if peak["月份"].year in {2019, 2020} else "常规周期",
        })
        previous_peak_index = peak_index
    cycles = pd.DataFrame(rows)
    last_peak = cycles["顶部月份"].max()
    current_slice = data[data["月份"] > last_peak]
    current_bottom = current_slice.loc[current_slice["平滑价格"].idxmin()]
    return cycles, current_bottom


def add_months(date: pd.Timestamp, months: float) -> pd.Timestamp:
    return (date.to_period("M") + int(round(months))).to_timestamp("M")


def valuation_link(price: float) -> dict[str, float]:
    scenarios = pd.read_csv(REPORTS_DIR / "基本面估值情景.csv")
    assumptions = json.loads((REPORTS_DIR / "基本面估值假设.json").read_text(encoding="utf-8"))
    base = scenarios[scenarios["情景"] == "基准"].iloc[0]
    profit_per_yuan = float(base["年出栏量_万头"] * base["平均重量_公斤每头"] / 1e4)
    net_profit = profit_per_yuan * (price - base["报表隐含成本_元每公斤"]) + base["毛利以下及其他业务_亿元"]
    book_value_per_share = assumptions["parent_equity_亿元"] * 1e8 / assumptions["share_capital"]
    loss_case_pb = float(assumptions["loss_case_pb"])
    pb_reference_price = book_value_per_share * loss_case_pb
    current_pb = assumptions["current_price"] / book_value_per_share
    return {
        "牧原阶段高点经营情景归母净利润_亿元": float(net_profit),
        "当前牧原股价_元": float(assumptions["current_price"]),
        "牧原每股净资产_元": float(book_value_per_share),
        "牧原当前PB_倍": float(current_pb),
        "亏损期PB参考倍数": loss_case_pb,
        "亏损期PB参考价_元": float(pb_reference_price),
        "估值使用成本_元每公斤": float(base["报表隐含成本_元每公斤"]),
        "估值使用出栏量_万头": float(base["年出栏量_万头"]),
    }


def build_forecast(
    panel: pd.DataFrame, capacity: pd.DataFrame, futures: pd.DataFrame,
    cycles: pd.DataFrame, current_bottom: pd.Series,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    regular = cycles[cycles["异常冲击"] == "常规周期"].copy()
    if len(regular) < 2:
        raise ValueError("常规历史周期样本不足")
    duration = regular["谷底到顶部月数"]
    multiplier = 1 + regular["谷底到顶部涨幅_%"] / 100
    bottom_date = pd.Timestamp(current_bottom["月份"])
    bottom_price = float(current_bottom["生猪价格_元每公斤"])

    latest_price = panel.dropna(subset=["生猪价格_元每公斤"]).iloc[-1]
    latest_piglet = panel.dropna(subset=["仔猪价格_元每公斤"]).iloc[-1]
    latest_sow_price = panel.dropna(subset=["二元母猪价格_元每公斤"]).iloc[-1]
    latest_hog_grain = panel.dropna(subset=["猪粮比"]).iloc[-1]
    latest_capacity = capacity.sort_values("日期").iloc[-1]
    base_capacity = capacity[(capacity["日期"].dt.year == 2024) & (capacity["日期"].dt.month == 12)].iloc[-1]

    annual_capacity = capacity[capacity["期间"].astype(str).str.fullmatch(r"20\d{2}")].copy()
    reference_sow = annual_capacity[annual_capacity["期间"].astype(str) == "2023"].iloc[-1]
    reference_output = annual_capacity[annual_capacity["期间"].astype(str) == "2024"].iloc[-1]
    output_per_sow = float(reference_output["生猪出栏_万头"] / reference_sow["能繁母猪_万头"])

    annual_prices = panel.dropna(subset=["生猪价格_元每公斤"])[["月份", "生猪价格_元每公斤"]].copy()
    annual_prices["年份"] = annual_prices["月份"].dt.year
    annual_price_stats = annual_prices[annual_prices["年份"] <= 2024].groupby("年份")["生猪价格_元每公斤"].agg(["mean", "max"])
    regular_price_stats = annual_price_stats[~annual_price_stats.index.isin([2019, 2020, 2021])]
    seasonal_peak_factor = float((regular_price_stats["max"] / regular_price_stats["mean"]).median())

    scenario_specs = [
        ("供给偏宽松", 0.04, -0.90, "效率提升充分抵消母猪去化"),
        ("基准", 0.02, -0.50, "效率延续近年约2%的改善"),
        ("供给偏紧", 0.00, -0.30, "效率不再提升且需求反应较弱"),
    ]
    scenario_rows: list[dict[str, object]] = []
    for name, efficiency_gain, demand_elasticity, meaning in scenario_specs:
        future_output = float(latest_capacity["能繁母猪_万头"] * output_per_sow * (1 + efficiency_gain))
        output_change = future_output / float(reference_output["生猪出栏_万头"]) - 1
        equilibrium_price = float(latest_price["生猪价格_元每公斤"] * (1 + output_change) ** (1 / demand_elasticity))
        stage_top_price = equilibrium_price * seasonal_peak_factor
        scenario_rows.append({
            "情景": name,
            "生产效率提升_%": efficiency_gain * 100,
            "需求价格弹性": demand_elasticity,
            "预测出栏量_万头": future_output,
            "较2024年出栏变化_%": output_change * 100,
            "供需均衡价格_元每公斤": equilibrium_price,
            "阶段高点_元每公斤": stage_top_price,
            "情景含义": meaning,
        })
    scenarios = pd.DataFrame(scenario_rows)
    central_scenario = scenarios[scenarios["情景"] == "基准"].iloc[0]
    central_price = float(central_scenario["阶段高点_元每公斤"])
    low_price = float(scenarios["阶段高点_元每公斤"].min())
    high_price = float(scenarios["阶段高点_元每公斤"].max())

    depletion_rows: list[dict[str, float]] = []
    for sow_capacity in [float(latest_capacity["能繁母猪_万头"]), 3900.0, 3800.0, 3700.0]:
        future_output = sow_capacity * output_per_sow * (1 + float(central_scenario["生产效率提升_%"]) / 100)
        output_change = future_output / float(reference_output["生猪出栏_万头"]) - 1
        equilibrium_price = float(
            latest_price["生猪价格_元每公斤"] * (1 + output_change) ** (1 / float(central_scenario["需求价格弹性"]))
        )
        depletion_rows.append({
            "能繁母猪_万头": sow_capacity,
            "预测出栏量_万头": future_output,
            "较2024年出栏变化_%": output_change * 100,
            "供需均衡价格_元每公斤": equilibrium_price,
            "阶段高点_元每公斤": equilibrium_price * seasonal_peak_factor,
        })
    depletion_sensitivity = pd.DataFrame(depletion_rows)

    futures_horizon = futures.sort_values("交割月份").iloc[-1]
    futures_horizon_date = pd.Timestamp(futures_horizon["交割月份"]).to_period("M").to_timestamp("M")
    futures_horizon_price = float(futures_horizon["期货价格_元每公斤"])
    historical_date = add_months(bottom_date, duration.median())
    central_date = historical_date
    window_start = add_months(bottom_date, duration.quantile(0.25))
    window_end = add_months(bottom_date, duration.quantile(0.75))
    normal_sow_capacity = 3900.0
    sow_change = (latest_capacity["能繁母猪_万头"] / base_capacity["能繁母猪_万头"] - 1) * 100
    sow_change_amount = latest_capacity["能繁母猪_万头"] - base_capacity["能繁母猪_万头"]
    sow_vs_normal = (latest_capacity["能繁母猪_万头"] / normal_sow_capacity - 1) * 100
    capacity_status = "温和去化" if sow_change < 0 and sow_vs_normal > 0 else ("深度去化" if sow_change < 0 else "尚未去化")
    sorted_capacity = capacity.sort_values("日期")
    previous_capacity = sorted_capacity.iloc[-2]
    latest_period_change = (
        latest_capacity["能繁母猪_万头"] / previous_capacity["能繁母猪_万头"] - 1
    ) * 100
    acceleration_status = "去化压力增强，但未确认持续加速"
    valuation = valuation_link(central_price)

    forecast = {
        "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_stage": "底部反弹 / 去产能传导期",
        "current_hog_price_元每公斤": float(latest_price["生猪价格_元每公斤"]),
        "current_price_month": pd.Timestamp(latest_price["月份"]).strftime("%Y-%m"),
        "identified_bottom_month": bottom_date.strftime("%Y-%m"),
        "identified_bottom_price_元每公斤": bottom_price,
        "conditional_top_window_start": window_start.strftime("%Y-%m"),
        "conditional_top_window_end": window_end.strftime("%Y-%m"),
        "central_top_month": central_date.strftime("%Y-%m"),
        "central_top_price_元每公斤": central_price,
        "top_price_low_元每公斤": low_price,
        "top_price_high_元每公斤": high_price,
        "pricing_model": "能繁母猪×次年出栏效率→未来出栏→需求弹性→均衡价格×阶段高点系数",
        "reference_sow_year": 2023,
        "reference_sow_capacity_万头": float(reference_sow["能繁母猪_万头"]),
        "reference_output_year": 2024,
        "reference_output_万头": float(reference_output["生猪出栏_万头"]),
        "output_per_sow_头": output_per_sow,
        "seasonal_peak_factor": seasonal_peak_factor,
        "base_efficiency_gain_%": float(central_scenario["生产效率提升_%"]),
        "base_demand_elasticity": float(central_scenario["需求价格弹性"]),
        "base_future_output_万头": float(central_scenario["预测出栏量_万头"]),
        "base_output_change_vs_2024_%": float(central_scenario["较2024年出栏变化_%"]),
        "base_equilibrium_price_元每公斤": float(central_scenario["供需均衡价格_元每公斤"]),
        "futures_curve_horizon_contract": str(futures_horizon["symbol"]),
        "futures_curve_horizon_month": futures_horizon_date.strftime("%Y-%m"),
        "futures_curve_horizon_price_元每公斤": futures_horizon_price,
        "futures_horizon_right_censored": True,
        "top_timing_basis": "常规周期谷底到顶部时长；期货仅观察至最远合约，不能确认顶部",
        "historical_regular_cycle_median_months": float(duration.median()),
        "historical_regular_cycle_median_multiplier": float(multiplier.median()),
        "latest_sow_capacity_万头": float(latest_capacity["能繁母猪_万头"]),
        "latest_sow_capacity_date": pd.Timestamp(latest_capacity["日期"]).strftime("%Y-%m-%d"),
        "capacity_depletion_status": capacity_status,
        "base_sow_capacity_2024_万头": float(base_capacity["能繁母猪_万头"]),
        "normal_sow_capacity_万头": normal_sow_capacity,
        "sow_change_amount_vs_2024_万头": float(sow_change_amount),
        "sow_change_vs_2024_%": float(sow_change),
        "sow_vs_normal_capacity_%": float(sow_vs_normal),
        "latest_sow_period_change_%": float(latest_period_change),
        "previous_sow_capacity_date": pd.Timestamp(previous_capacity["日期"]).strftime("%Y-%m-%d"),
        "capacity_depletion_acceleration_status": acceleration_status,
        "hog_price_three_month_change_%": float(latest_price["生猪价格_元每公斤_三月变化_%"]),
        "hog_grain_ratio_yoy_%": float(latest_hog_grain["猪粮比_同比_%"]),
        "piglet_price_yoy_%": float(latest_piglet["仔猪价格_元每公斤_同比_%"]),
        "binary_sow_price_yoy_%": float(latest_sow_price["二元母猪价格_元每公斤_同比_%"]),
        "likely_next_sow_range_万头": "3900—3950",
        "central_rebound_vs_current_%": float((central_price / latest_price["生猪价格_元每公斤"] - 1) * 100),
        **valuation,
        "conditions": [
            "2026年能繁母猪和仔猪补栏继续受低利润约束，未在短期内快速扩张",
            "没有发生非洲猪瘟级别的额外供给冲击；若发生，顶部价格可能显著高于区间",
            "基准情景假设每头母猪对应出栏效率提高2%、需求价格弹性为-0.5",
            "需求、冻肉投放、进口、出栏体重和饲料成本没有发生足以改变供需关系的结构突变",
            "期货曲线只覆盖到最远可见合约，末端价格不是顶部确认，且会随新信息快速变化",
        ],
    }
    signals = pd.DataFrame([
        {"信号": "现货价格", "最新值": f"{forecast['current_hog_price_元每公斤']:.2f}元/kg", "日期": forecast["current_price_month"], "含义": "已较识别谷底反弹，但仍低于上一轮顶部"},
        {"信号": "能繁母猪", "最新值": f"{forecast['latest_sow_capacity_万头']:.0f}万头", "日期": forecast["latest_sow_capacity_date"], "含义": f"较2024年末{sow_change:+.1f}%，供给收缩约10-12个月后传导"},
        {"信号": "猪粮比", "最新值": f"{latest_hog_grain['猪粮比']:.2f}", "日期": pd.Timestamp(latest_hog_grain["月份"]).strftime("%Y-%m"), "含义": "低位代表行业亏损和去产能压力，升至高位后才接近盈利顶部"},
        {"信号": "仔猪价格", "最新值": f"{latest_piglet['仔猪价格_元每公斤']:.2f}元/kg", "日期": pd.Timestamp(latest_piglet["月份"]).strftime("%Y-%m"), "含义": "仍处低位，补栏热度尚未形成顶部信号"},
        {"信号": "二元母猪价格", "最新值": f"{latest_sow_price['二元母猪价格_元每公斤']:.2f}元/kg", "日期": pd.Timestamp(latest_sow_price["月份"]).strftime("%Y-%m"), "含义": "母猪补栏价格未显示强扩张"},
        {"信号": "期货期限", "最新值": f"最远{futures_horizon_price:.2f}元/kg", "日期": futures_horizon_date.strftime("%Y-%m"), "含义": "最远合约仍在上行，不代表该月已经见顶"},
        {"信号": "历史节奏", "最新值": f"谷底后{duration.median():.0f}个月", "日期": "常规周期中位数", "含义": "生物学滞后决定顶部更可能落在2027年"},
    ])
    return forecast, signals, scenarios, depletion_sensitivity


def chart_html(fig: go.Figure, first: bool = False) -> str:
    fig.update_layout(
        paper_bgcolor=COLORS["paper"], plot_bgcolor=COLORS["paper"],
        font={"family": "Microsoft YaHei UI, sans-serif", "color": COLORS["ink"]},
        margin={"l": 55, "r": 45, "t": 80, "b": 50}, hovermode="x unified",
        legend={"orientation": "h", "y": 1.04, "x": 1, "xanchor": "right"},
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["line"])
    fig.update_yaxes(gridcolor=COLORS["line"])
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if first else False, config={"displaylogo": False})


def build_report(
    panel: pd.DataFrame, capacity: pd.DataFrame, futures: pd.DataFrame,
    factors: pd.DataFrame, cycles: pd.DataFrame, signals: pd.DataFrame,
    scenarios: pd.DataFrame, depletion_sensitivity: pd.DataFrame,
    forecast: dict[str, object], sources: dict[str, str],
) -> str:
    price = go.Figure()
    price.add_scatter(x=panel["月份"], y=panel["生猪价格_元每公斤"], name="生猪价格", line={"color": COLORS["red"], "width": 3})
    price.add_scatter(x=cycles["顶部月份"], y=cycles["顶部价格_元每公斤"], name="历史顶部", mode="markers", marker={"size": 10, "color": COLORS["ink"], "symbol": "diamond"})
    price.add_vrect(x0=forecast["conditional_top_window_start"] + "-01", x1=forecast["conditional_top_window_end"] + "-28", fillcolor=COLORS["amber"], opacity=0.16, line_width=0)
    price.add_scatter(x=[forecast["central_top_month"] + "-15"], y=[forecast["central_top_price_元每公斤"]], name="供给模型基准", mode="markers", marker={"size": 13, "color": COLORS["amber"], "symbol": "star"})
    price.update_layout(title="历史猪价周期与本轮条件预测", yaxis_title="元/公斤", height=460)

    piglet_series = panel.dropna(subset=["仔猪价格_元每公斤"])
    sow_price_series = panel.dropna(subset=["二元母猪价格_元每公斤"])
    hog_grain_series = panel.dropna(subset=["猪粮比"])
    indicators = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        row_heights=[0.62, 0.38],
        subplot_titles=("繁育价格", "养殖利润信号"),
    )
    indicators.add_scatter(
        x=piglet_series["月份"], y=piglet_series["仔猪价格_元每公斤"],
        name="仔猪价格", line={"color": COLORS["amber"], "width": 2.5}, row=1, col=1,
    )
    indicators.add_scatter(
        x=sow_price_series["月份"], y=sow_price_series["二元母猪价格_元每公斤"],
        name="二元母猪价格", line={"color": COLORS["violet"], "width": 2.5}, row=1, col=1,
    )
    indicators.add_scatter(
        x=hog_grain_series["月份"], y=hog_grain_series["猪粮比"],
        name="猪粮比", line={"color": COLORS["green"], "width": 3}, row=2, col=1,
    )
    indicators.update_yaxes(title_text="元/公斤", tickformat=",.0f", row=1, col=1)
    indicators.update_yaxes(title_text="比值", tickformat=".1f", row=2, col=1)
    indicators.update_layout(title="补栏意愿与养殖利润信号（分面展示）", height=560)

    curve = go.Figure()
    curve.add_scatter(x=futures["交割月份"], y=futures["期货价格_元每公斤"], mode="lines+markers", name="期货价格", line={"color": COLORS["blue"], "width": 3}, marker={"size": 9})
    curve.add_scatter(
        x=[forecast["futures_curve_horizon_month"] + "-01"],
        y=[forecast["futures_curve_horizon_price_元每公斤"]],
        mode="markers", name="最远可见合约（非顶部）",
        marker={"size": 13, "color": COLORS["amber"], "symbol": "diamond-open"},
    )
    curve.add_hline(y=forecast["current_hog_price_元每公斤"], line_dash="dot", line_color=COLORS["muted"], annotation_text="当前现货月均")
    curve.update_layout(title="生猪期货远期曲线（末端合约不等于周期顶部）", yaxis_title="元/公斤", height=400)

    annual_capacity = capacity[capacity["期间"].astype(str).str.fullmatch(r"20\d{2}")].copy()
    recent_capacity = capacity[
        ~capacity.index.isin(annual_capacity.index) & capacity["能繁母猪_万头"].notna()
    ].copy()
    recent_labels = recent_capacity["期间"].astype(str).replace({
        "2025年一季度（末）": "Q1末", "2025年二季度（末）": "Q2末",
        "2025年7月": "7月", "2025年8月": "8月",
        "2025年三季度（末）": "Q3末", "2025年10月": "10月",
    })
    cap = make_subplots(
        rows=3, cols=1, shared_xaxes=False, vertical_spacing=0.12,
        row_heights=[0.38, 0.27, 0.35],
        subplot_titles=("能繁母猪（年度末）", "能繁母猪（2025 月末/季末）", "全国生猪出栏（全年）"),
    )
    cap.add_bar(
        x=annual_capacity["日期"], y=annual_capacity["能繁母猪_万头"],
        name="能繁母猪（年度末）", marker_color=COLORS["green"], row=1, col=1,
    )
    cap.add_scatter(
        x=recent_labels, y=recent_capacity["能繁母猪_万头"],
        name="能繁母猪（2025月/季末）", mode="lines+markers+text",
        line={"color": COLORS["blue"], "width": 2.5}, marker={"size": 8},
        text=recent_capacity["能繁母猪_万头"].map(lambda value: f"{value:,.0f}"),
        textposition="top center",
        customdata=recent_capacity["期间"],
        hovertemplate="%{customdata}<br>%{y:,.0f} 万头<extra></extra>", row=2, col=1,
    )
    cap.add_scatter(
        x=annual_capacity["日期"], y=annual_capacity["生猪出栏_万头"],
        name="全国出栏（全年）", mode="lines+markers",
        line={"color": COLORS["amber"], "width": 2.5}, marker={"size": 6}, row=3, col=1,
    )
    cap.update_yaxes(title_text="万头", tickformat=",.0f", row=1, col=1)
    cap.update_yaxes(
        title_text="万头", tickformat=",.0f",
        range=[recent_capacity["能繁母猪_万头"].min() - 15, recent_capacity["能繁母猪_万头"].max() + 20],
        row=2, col=1,
    )
    cap.update_yaxes(title_text="万头", tickformat=",.0f", row=3, col=1)
    cap.update_xaxes(tickformat="%Y", row=1, col=1)
    cap.update_xaxes(
        type="category", categoryorder="array", categoryarray=recent_labels.tolist(),
        row=2, col=1,
    )
    cap.update_xaxes(tickformat="%Y", row=3, col=1)
    cap.update_layout(title="产能与供给（年度与月度数据分开观察）", height=720)

    factor_rows = "".join(
        f"<tr><td>{html.escape(str(row['决定因素']))}</td><td>{html.escape(str(row['量化口径']))}</td>"
        f"<td>{'—' if pd.isna(row['领先月数']) else int(row['领先月数'])}</td>"
        f"<td>{'—' if pd.isna(row['Pearson相关系数']) else f'{row['Pearson相关系数']:+.3f}'}</td><td>{int(row['样本数'])}</td>"
        f"<td>{int(row['机制参考领先月数'])}</td><td>{'—' if pd.isna(row['机制滞后相关系数']) else f'{row['机制滞后相关系数']:+.3f}'}</td>"
        f"<td>{pd.Timestamp(row['数据开始']):%Y-%m}—{pd.Timestamp(row['数据截至']):%Y-%m}</td><td>{html.escape(str(row['机制解释']))}</td></tr>"
        for _, row in factors.iterrows()
    )
    cycle_rows = "".join(
        f"<tr><td>{row['周期']}</td><td>{row['谷底月份']:%Y-%m}</td><td>{row['谷底价格_元每公斤']:.2f}</td>"
        f"<td>{row['顶部月份']:%Y-%m}</td><td>{row['顶部价格_元每公斤']:.2f}</td><td>{int(row['谷底到顶部月数'])}</td>"
        f"<td>{row['谷底到顶部涨幅_%']:+.1f}%</td><td>{row['异常冲击']}</td></tr>" for _, row in cycles.iterrows()
    )
    signal_rows = "".join(
        f"<tr><td>{row['信号']}</td><td>{row['最新值']}</td><td>{row['日期']}</td><td>{row['含义']}</td></tr>" for _, row in signals.iterrows()
    )
    scenario_rows = "".join(
        f"<tr><td>{row['情景']}</td><td>{row['生产效率提升_%']:.1f}%</td><td>{row['需求价格弹性']:.2f}</td>"
        f"<td>{row['预测出栏量_万头']:,.0f}</td><td>{row['较2024年出栏变化_%']:+.1f}%</td>"
        f"<td>{row['供需均衡价格_元每公斤']:.2f}</td><td>{row['阶段高点_元每公斤']:.2f}</td>"
        f"<td>{html.escape(str(row['情景含义']))}</td></tr>" for _, row in scenarios.iterrows()
    )
    depletion_rows = "".join(
        f"<tr><td>{row['能繁母猪_万头']:,.0f}</td><td>{row['预测出栏量_万头']:,.0f}</td>"
        f"<td>{row['较2024年出栏变化_%']:+.1f}%</td><td>{row['供需均衡价格_元每公斤']:.2f}</td>"
        f"<td>{row['阶段高点_元每公斤']:.2f}</td></tr>" for _, row in depletion_sensitivity.iterrows()
    )
    regular = cycles[cycles["异常冲击"] == "常规周期"]
    strongest = factors.dropna(subset=["Pearson相关系数"]).iloc[factors.dropna(subset=["Pearson相关系数"])["Pearson相关系数"].abs().argmax()]
    source_text = "；".join(sorted(set(sources.values())))
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>猪周期驱动与顶部预测</title>
<style>:root{{--paper:#f5f3ed;--ink:#202421;--muted:#6e726c;--line:#d3d5cf;--red:#b33b32;--green:#287157;--amber:#b27618}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei UI",sans-serif;letter-spacing:0}}.shell{{width:min(1180px,calc(100% - 40px));margin:auto}}header{{padding:42px 0 26px;border-bottom:1px solid var(--ink)}}h1{{font:500 48px/1.12 "STZhongsong","SimSun",serif;margin:14px 0}}.lead,.note{{font-size:12px;line-height:1.85;color:var(--muted)}}.metrics,.verdict{{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--ink)}}.metric,.verdict div{{padding:22px 16px;border-right:1px solid var(--line)}}.metric:last-child,.verdict div:last-child{{border:0}}.metric span,.metric small,.verdict span,.verdict small{{display:block;color:var(--muted);font-size:10px}}.metric strong,.verdict strong{{display:block;margin:8px 0;font:500 22px "STZhongsong","SimSun",serif}}h2{{font:500 29px "STZhongsong","SimSun",serif;margin:52px 0 14px}}.loop{{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid var(--ink);border-bottom:1px solid var(--ink)}}.loop div{{padding:18px 14px;border-right:1px solid var(--line);font-size:12px;line-height:1.65}}.loop div:last-child{{border:0}}.loop b,.loop small{{display:block}}.loop small{{color:var(--muted);margin-top:5px}}.chart{{border-top:1px solid var(--ink);border-bottom:1px solid var(--line)}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{padding:10px 8px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}}th{{font-weight:400;color:var(--muted)}}.scroll{{overflow-x:auto}}.conclusion{{padding:15px 0 19px;border-bottom:1px solid var(--line);font-size:12px;line-height:1.85}}.conclusion strong{{color:var(--red)}}.warning{{margin:24px 0;padding:17px 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);font-size:11px;line-height:1.8;color:var(--muted)}}footer{{margin-top:50px;padding:22px 0;border-top:1px solid var(--ink);font-size:10px;color:var(--muted)}}@media(max-width:760px){{.metrics,.verdict{{grid-template-columns:1fr 1fr}}.metric:nth-child(2),.verdict div:nth-child(2){{border-right:0}}.loop{{grid-template-columns:1fr}}.loop div{{border-right:0;border-bottom:1px solid var(--line)}}h1{{font-size:37px}}}}</style></head>
<body><div class="shell"><header><small>产业周期研究 / 截至 {forecast['as_of'][:10]}</small><h1>猪周期如何形成，以及顶部在哪里</h1><p class="lead">把能繁母猪、生产效率、未来出栏、需求弹性和生物学滞后放进同一供给结构模型。历史周期只用于时间节奏和阶段高点系数，期货曲线只作市场定价对照，不再直接加权生成顶部价格。</p></header>
<section class="metrics"><div class="metric"><span>当前阶段</span><strong>{forecast['current_stage']}</strong><small>现货 {forecast['current_hog_price_元每公斤']:.2f} 元/kg</small></div><div class="metric"><span>历史节奏参考窗口</span><strong>{forecast['conditional_top_window_start']}—{forecast['conditional_top_window_end']}</strong><small>中心 {forecast['central_top_month']}；不排除更晚</small></div><div class="metric"><span>供给模型基准高点</span><strong>{forecast['central_top_price_元每公斤']:.2f}元/kg</strong><small>情景 {forecast['top_price_low_元每公斤']:.2f}—{forecast['top_price_high_元每公斤']:.2f}</small></div><div class="metric"><span>亏损期 PB 参考</span><strong>{forecast['亏损期PB参考价_元']:.2f}元</strong><small>当前 {forecast['牧原当前PB_倍']:.2f} 倍 PB</small></div></section>
<h2>形成机制</h2><div class="loop"><div><b>1. 盈亏信号</b><small>猪价、饲料和猪粮比决定现金利润</small></div><div><b>2. 产能决策</b><small>亏损促淘汰，盈利促母猪和仔猪补栏</small></div><div><b>3. 生物学滞后</b><small>母猪变化约10—12个月后进入商品猪供给</small></div><div><b>4. 出栏供给</b><small>供给收缩推高价格，扩张压低价格</small></div><div><b>5. 反向调节</b><small>高价重新刺激补栏，孕育下一轮下行</small></div></div>
<div class="conclusion"><strong>机制结论：</strong>需求季节性会改变短期波动，饲料和政策会改变振幅，但跨年度猪周期的核心决定因素仍是能繁母猪及生产效率所决定的未来供给。价格对产能的反馈存在生物学延迟，因此行业经常在价格已经上涨时继续去产能，也会在价格已经下跌时继续释放前期扩张的供给。</div>
<h2>当前周期与预测</h2><section class="chart">{chart_html(price, True)}</section><div class="conclusion"><strong>图表结论：</strong>上一轮顶部在 2024 年三季度，随后价格下行至本轮识别谷底 {forecast['identified_bottom_month']} 的 {forecast['identified_bottom_price_元每公斤']:.2f} 元/公斤。按常规周期谷底后约 {forecast['historical_regular_cycle_median_months']:.0f} 个月计算，时间中心落在 {forecast['central_top_month']}；{forecast['conditional_top_window_start']}—{forecast['conditional_top_window_end']} 只是历史节奏参考窗口，不能排除更晚见顶。</div>
<section class="chart">{chart_html(curve)}</section><div class="conclusion"><strong>图表结论：</strong>当前期货数据最远只覆盖 {forecast['futures_curve_horizon_contract']}，交割月为 {forecast['futures_curve_horizon_month']}，价格 {forecast['futures_curve_horizon_price_元每公斤']:.2f} 元/公斤。曲线到样本末端仍在上行，因此这是右截尾观察：它支持“截至 2027 年 5 月仍有修复预期”，但不能证明 5 月就是最高点，也无法排除其后继续上涨。</div>
<h2>决定因素的定量结果</h2><div class="scroll"><table><thead><tr><th>因素</th><th>口径</th><th>统计最强领先</th><th>Pearson</th><th>n</th><th>机制参考领先</th><th>机制滞后相关</th><th>覆盖</th><th>机制</th></tr></thead><tbody>{factor_rows}</tbody></table></div><div class="conclusion"><strong>表格结论：</strong>样本中绝对相关性最高的是“{strongest['决定因素']}”，统计最强关系为领先 {int(strongest['领先月数'])} 个月、Pearson={strongest['Pearson相关系数']:+.3f}。仔猪和母猪价格的最强关系也在同期，说明它们首先是景气温度计；真正决定未来供给的是补栏数量和能繁母猪存栏。能繁母猪同比变化领先下一年猪价的相关系数为 {factors.loc[factors['决定因素']=='能繁母猪存栏','机制滞后相关系数'].iloc[0]:+.3f}，方向符合“产能增加、未来价格承压”，但只有 {int(factors.loc[factors['决定因素']=='能繁母猪存栏','机制滞后样本数'].iloc[0])} 个年度样本。</div>
<section class="chart">{chart_html(indicators)}</section><div class="conclusion"><strong>图表结论：</strong>仔猪和二元母猪价格使用同一单位，可在上图直接比较；猪粮比是无量纲比值，已在下图独立展示。三项指标均从各自首个有效月份开始绘制，不再用空值把横轴人为延伸到 2015 年。繁育价格与猪价往往同期变化，因此更适合作为补栏热度和景气状态指标，不能仅凭曲线同步认定其领先猪价。</div>
<section class="chart">{chart_html(cap)}</section><div class="conclusion"><strong>图表结论：</strong>第一分面展示年度末能繁母猪，第二分面单独放大 2025 年月末或季末观测，第三分面只使用完整年度的全国生猪出栏量。三个分面均以万头计量，但时间频率和坐标范围独立；蓝线只反映 2025 年内从 4,039 万头到 3,990 万头的变化，2025 年季度出栏数据不与全年数据相连，也不参与年度趋势判断。</div>
<h2>直接回答：产能去化与猪价回弹</h2><section class="verdict"><div><span>产能判断</span><strong>{forecast['capacity_depletion_status']}</strong><small>较 2024 年末 {forecast['sow_change_vs_2024_%']:+.1f}%</small></div><div><span>基准未来出栏</span><strong>{forecast['base_future_output_万头']:,.0f}万头</strong><small>较 2024 年 {forecast['base_output_change_vs_2024_%']:+.1f}%</small></div><div><span>基准阶段高点</span><strong>{forecast['central_top_price_元每公斤']:.2f}元/kg</strong><small>较最新价格约 {forecast['central_rebound_vs_current_%']:+.1f}%</small></div><div><span>结构情景范围</span><strong>{forecast['top_price_low_元每公斤']:.2f}—{forecast['top_price_high_元每公斤']:.2f}</strong><small>不是统计置信区间</small></div></section>
<h2>供给结构模型情景</h2><div class="scroll"><table><thead><tr><th>情景</th><th>效率提升</th><th>需求弹性</th><th>未来出栏（万头）</th><th>较2024年</th><th>均衡价</th><th>阶段高点</th><th>含义</th></tr></thead><tbody>{scenario_rows}</tbody></table></div><div class="conclusion"><strong>表格结论：</strong>基准情景假设生产效率提高 {forecast['base_efficiency_gain_%']:.0f}%、需求价格弹性为 {forecast['base_demand_elasticity']:.1f}，由 {forecast['latest_sow_capacity_万头']:.0f} 万头能繁母猪推导未来出栏约 {forecast['base_future_output_万头']:,.0f} 万头，较 2024 年减少 {abs(forecast['base_output_change_vs_2024_%']):.1f}%；供需均衡价约 {forecast['base_equilibrium_price_元每公斤']:.2f} 元/公斤，再乘常规年份阶段高点系数 {forecast['seasonal_peak_factor']:.3f}，得到基准高点 {forecast['central_top_price_元每公斤']:.2f} 元/公斤。{forecast['top_price_high_元每公斤']:.2f} 元/公斤现在属于“效率不再提升且需求较不敏感”的供给偏紧情景，不再是中心预测。</div>
<div class="conclusion"><strong>判断结论：</strong>产能已经去化，但最新能繁母猪仍比 3,900 万头正常保有量高 {forecast['sow_vs_normal_capacity_%']:.1f}%，属于温和去化。现有产能主要约束其后 10—12 个月的供给，不能单独锁定 2027 年顶部；时间仍以历史节奏作为参考，并随 2026 年母猪、仔猪和效率数据滚动更新。价格方面，当前结构模型支持约 {forecast['central_top_price_元每公斤']:.2f} 元/公斤的基准阶段高点，情景范围 {forecast['top_price_low_元每公斤']:.2f}—{forecast['top_price_high_元每公斤']:.2f} 元/公斤，不是统计置信区间。</div>
<h2>去化会不会加速</h2><section class="verdict"><div><span>当前判断</span><strong>{forecast['capacity_depletion_acceleration_status']}</strong><small>单期数据不足以确认趋势</small></div><div><span>最近一期母猪变化</span><strong>{forecast['latest_sow_period_change_%']:+.1f}%</strong><small>{forecast['previous_sow_capacity_date']} 至 {forecast['latest_sow_capacity_date']}</small></div><div><span>补栏领先信号</span><strong>仍然偏弱</strong><small>仔猪同比 {forecast['piglet_price_yoy_%']:+.1f}%</small></div><div><span>基准下一阶段</span><strong>{forecast['likely_next_sow_range_万头']}万头</strong><small>深度去化尚未确认</small></div></section>
<div class="conclusion"><strong>加速判断：</strong>支持继续去化的证据是猪粮比同比 {forecast['hog_grain_ratio_yoy_%']:+.1f}%、仔猪价格同比 {forecast['piglet_price_yoy_%']:+.1f}%、二元母猪价格同比 {forecast['binary_sow_price_yoy_%']:+.1f}%，说明现金利润与补栏意愿仍弱；最近一期母猪下降 {abs(forecast['latest_sow_period_change_%']):.1f}% 也出现加速迹象。反向因素是生猪价格近三个月已经反弹 {forecast['hog_price_three_month_change_%']:+.1f}%，会缓解亏损并延缓淘汰。综合判断更支持继续向 3,900—3,950 万头温和去化，暂不支持直接假设快速降至 3,700—3,800 万头。</div>
<div class="scroll"><table><thead><tr><th>能繁母猪（万头）</th><th>预测出栏（万头）</th><th>较2024年</th><th>均衡价</th><th>阶段高点</th></tr></thead><tbody>{depletion_rows}</tbody></table></div><div class="conclusion"><strong>敏感性表结论：</strong>在生产效率提高 {forecast['base_efficiency_gain_%']:.0f}%、需求价格弹性 {forecast['base_demand_elasticity']:.1f}不变时，母猪降至 3,900 万头对应阶段高点约 {depletion_sensitivity.loc[depletion_sensitivity['能繁母猪_万头']==3900, '阶段高点_元每公斤'].iloc[0]:.2f} 元/公斤；降至 3,800 万头约 {depletion_sensitivity.loc[depletion_sensitivity['能繁母猪_万头']==3800, '阶段高点_元每公斤'].iloc[0]:.2f} 元/公斤；降至 3,700 万头约 {depletion_sensitivity.loc[depletion_sensitivity['能繁母猪_万头']==3700, '阶段高点_元每公斤'].iloc[0]:.2f} 元/公斤。确认持续加速需要看到母猪连续两至三个月下降超过 0.5%、跌破 3,900 万头，猪粮比持续低于 5，同时仔猪、母猪价格和新生仔猪数量继续走弱；否则更深去化只应保留为压力情景。</div>
<h2>历史谷底到顶部</h2><div class="scroll"><table><thead><tr><th>周期</th><th>谷底</th><th>谷底价</th><th>顶部</th><th>顶部价</th><th>月数</th><th>涨幅</th><th>类型</th></tr></thead><tbody>{cycle_rows}</tbody></table></div><div class="conclusion"><strong>表格结论：</strong>剔除非洲猪瘟异常周期后，常规周期从谷底到顶部的中位数为 {regular['谷底到顶部月数'].median():.0f} 个月，中位涨幅为 {regular['谷底到顶部涨幅_%'].median():.1f}%。历史时长用于给出时间参考，月度高点/年均价关系用于阶段高点系数；历史涨幅不再直接加权生成本轮中心价格。</div>
<h2>当前信号</h2><div class="scroll"><table><thead><tr><th>信号</th><th>最新值</th><th>日期</th><th>含义</th></tr></thead><tbody>{signal_rows}</tbody></table></div><div class="conclusion"><strong>表格结论：</strong>最新能繁母猪较 2024 年末变化 {forecast['sow_change_vs_2024_%']:+.1f}%，叠加低猪粮比，支持未来供给收缩；但全国能繁母猪数据只更新到 {forecast['latest_sow_capacity_date']}，2026 年判断还需要仔猪、母猪价格和期货曲线代理。最远期货合约价格为 {forecast['futures_curve_horizon_price_元每公斤']:.2f} 元/公斤，只能作为截至 {forecast['futures_curve_horizon_month']} 的市场锚，不能作为周期顶部上限。</div>
<div class="warning"><strong>估值联动：</strong>当前猪价低于模型成本，牧原处于亏损或低盈利阶段，PE 不作为当前定价工具。以归母净资产 {forecast['牧原每股净资产_元']:.2f} 元/股和亏损期 {forecast['亏损期PB参考倍数']:.2f} 倍 PB 计算，参考价约 {forecast['亏损期PB参考价_元']:.2f} 元；当前股价 {forecast['当前牧原股价_元']:.2f} 元对应 {forecast['牧原当前PB_倍']:.2f} 倍 PB。将猪价基准高点 {forecast['central_top_price_元每公斤']:.2f} 元/公斤代入经营模型得到的 {forecast['牧原阶段高点经营情景归母净利润_亿元']:.1f} 亿元只用于观察盈利恢复弹性，不乘 PE 生成当前目标价；待连续盈利恢复后再启用正常化 PE 交叉验证。<br><strong>条件与限制：</strong>{'；'.join(forecast['conditions'])}。数据源：{html.escape(source_text)}。本结果不是确定性预测，不构成投资建议。</div>
</div><footer><div class="shell">生成于 {generated} · 顶部预测会随母猪、仔猪和期货曲线更新</div></footer></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="猪周期形成机制、决定因素与顶部条件预测")
    parser.add_argument("--no-cache", action="store_true", help="联网失败时禁止使用缓存")
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    series, capacity, futures, sources = fetch_drivers(not args.no_cache)
    panel = build_monthly_panel(series)
    factors = analyze_factors(panel, capacity)
    cycles, current_bottom = identify_cycles(panel)
    forecast, signals, scenarios, depletion_sensitivity = build_forecast(panel, capacity, futures, cycles, current_bottom)

    atomic_csv(panel, PANEL_PATH)
    atomic_csv(capacity, CAPACITY_PATH)
    atomic_csv(futures, FUTURES_PATH)
    atomic_csv(factors, FACTOR_RESULT_PATH)
    atomic_csv(cycles, CYCLE_PATH)
    atomic_csv(signals, SIGNAL_PATH)
    atomic_csv(scenarios, SUPPLY_SCENARIO_PATH)
    atomic_csv(depletion_sensitivity, DEPLETION_SENSITIVITY_PATH)
    FORECAST_PATH.write_text(json.dumps(forecast, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        build_report(panel, capacity, futures, factors, cycles, signals, scenarios, depletion_sensitivity, forecast, sources),
        encoding="utf-8",
    )

    print(f"月度驱动因子: {PANEL_PATH} ({len(panel)}个月)")
    print(f"历史周期: {CYCLE_PATH} ({len(cycles)}轮)")
    print(f"条件顶部: {forecast['conditional_top_window_start']}—{forecast['conditional_top_window_end']}, 中心 {forecast['central_top_price_元每公斤']:.2f}元/kg")
    print(f"可视化报告: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
