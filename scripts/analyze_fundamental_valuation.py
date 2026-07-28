#!/usr/bin/env python3
"""基于出栏量、售价、单位成本和历史周期估值测算牧原股份目标价。"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from pypdf import PdfReader
from plotly.subplots import make_subplots


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
CONFIG_PATH = PROJECT_ROOT / "config" / "fundamental_valuation.json"

NOTICE_RAW_PATH = DATA_DIR / "牧原销售简报_原始.json"
SALES_PATH = DATA_DIR / "牧原月度销售数据.csv"
BUSINESS_PATH = DATA_DIR / "牧原生猪主营构成.csv"
STOCK_RAW_PATH = DATA_DIR / "牧原股份未复权股价_原始.json"
STOCK_PATH = DATA_DIR / "牧原股份股价_未复权.csv"
OPERATING_PATH = REPORTS_DIR / "量价成本历史.csv"
TOP_PATH = REPORTS_DIR / "历史周期顶部估值.csv"
SCENARIO_PATH = REPORTS_DIR / "基本面估值情景.csv"
SENSITIVITY_PATH = REPORTS_DIR / "猪价成本敏感性.csv"
ASSUMPTION_PATH = REPORTS_DIR / "基本面估值假设.json"
REPORT_PATH = REPORTS_DIR / "基本面估值分析.html"

NOTICE_INDEX_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
NOTICE_CONTENT_URL = "https://np-cnotice-stock.eastmoney.com/api/content/ann"
BUSINESS_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax"

COLORS = {
    "ink": "#202421", "paper": "#f5f3ed", "muted": "#6e726c",
    "green": "#287157", "red": "#b33b32", "amber": "#b27618",
    "blue": "#2d6985", "line": "#d3d5cf",
}


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    temp.replace(path)


def curl_json(url: str, timeout: int = 60) -> dict:
    executable = shutil.which("curl") or shutil.which("curl.exe")
    if not executable:
        raise RuntimeError("未找到系统 curl")
    completed = subprocess.run(
        [executable, "-k", "--http1.1", "-L", "--retry", "2", "--retry-all-errors",
         "--fail", "--silent", "--show-error", "--max-time", str(timeout), url],
        capture_output=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    return json.loads(completed.stdout.decode("utf-8"))


def fetch_notice_index() -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        params = {
            "sr": "-1", "page_size": "100", "page_index": page,
            "ann_type": "A", "client_source": "web", "f_node": "0", "s_node": "0",
            "begin_time": "2015-01-01", "end_time": datetime.now().strftime("%Y-%m-%d"),
            "stock_list": "002714",
        }
        payload = curl_json(NOTICE_INDEX_URL + "?" + urllib.parse.urlencode(params))
        data = payload.get("data") or {}
        batch = data.get("list") or []
        rows.extend(batch)
        total_pages = max(1, math.ceil(float(data.get("total_hits") or 0) / 100))
        if page >= total_pages or not batch:
            break
        page += 1
    return [row for row in rows if "销售简报" in str(row.get("title", ""))]


def fetch_notice_content(art_code: str) -> dict:
    params = {"art_code": art_code, "client_source": "web", "page_index": "1"}
    try:
        payload = curl_json(NOTICE_CONTENT_URL + "?" + urllib.parse.urlencode(params))
        data = payload.get("data") or {}
        content = data.get("notice_content") or ""
        if not content:
            raise RuntimeError("公告正文为空")
        return {
            "art_code": art_code, "title": data.get("notice_title"),
            "notice_date": data.get("notice_date"), "content": content,
            "content_source": "东方财富公告正文",
        }
    except Exception:
        executable = shutil.which("curl") or shutil.which("curl.exe")
        if not executable:
            raise
        pdf_path = DATA_DIR / f".{art_code}.pdf.tmp"
        url = f"https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf"
        completed = subprocess.run(
            [executable, "-k", "--http1.1", "-L", "--retry", "2", "--retry-all-errors",
             "--fail", "--silent", "--show-error", "--max-time", "60", url, "-o", str(pdf_path)],
            capture_output=True, check=False,
        )
        if completed.returncode:
            pdf_path.unlink(missing_ok=True)
            raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
        try:
            reader = PdfReader(str(pdf_path))
            content = "\n".join(page.extract_text() or "" for page in reader.pages)
        finally:
            pdf_path.unlink(missing_ok=True)
        if not content:
            raise RuntimeError("PDF未提取出文本")
        return {"art_code": art_code, "content": content, "content_source": "东方财富公告PDF"}


def normalize_notice_text(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    value = value.replace("，", ",").replace("：", ":")
    return re.sub(r"\s+", "", value)


def first_number(text: str, patterns: list[str]) -> float:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(",", ""))
    return float("nan")


def parse_sales_notice(item: dict) -> dict | None:
    title = str(item.get("title") or "")
    title_match = re.search(r"(20\d{2})年(\d{1,2})(?:[-—至](\d{1,2}))?月份(?:生猪)?销售简报", title)
    if not title_match:
        return None
    year = int(title_match.group(1))
    start_month = int(title_match.group(2))
    end_month = int(title_match.group(3) or start_month)
    text = normalize_notice_text(str(item.get("content") or ""))
    volume = first_number(text, [
        r"(?:公司)?(?:共)?销售商品猪([\d,.]+)万头",
        r"(?:公司)?(?:共)?销售生猪([\d,.]+)万头",
    ])
    revenue = first_number(text, [
        r"商品猪销售收入([\d,.]+)亿元", r"生猪销售收入([\d,.]+)亿元",
        r"销售收入([\d,.]+)亿元",
    ])
    price = first_number(text, [
        r"商品猪销售均价([\d,.]+)元/公斤", r"商品猪平均销售价格([\d,.]+)元/公斤",
    ])
    if not np.isfinite(volume):
        return None
    period_end = pd.Period(year=year, month=end_month, freq="M").end_time.normalize()
    weight = revenue * 1e4 / (price * volume) if revenue > 0 and price > 0 else np.nan
    return {
        "期间截止日": period_end, "年份": year, "起始月份": start_month, "截止月份": end_month,
        "覆盖月数": end_month - start_month + 1, "销量_万头": volume,
        "销售收入_亿元": revenue, "商品猪销售均价_元每公斤": price,
        "收入反推平均重量_公斤每头": weight,
        "公告日期": pd.to_datetime(item.get("notice_date"), errors="coerce"),
        "公告标题": title, "公告编码": item.get("art_code"),
    }


def fetch_sales_data(allow_cache: bool) -> tuple[pd.DataFrame, str]:
    try:
        print("[销售简报] 拉取公告目录...")
        notices = fetch_notice_index()
        if not notices:
            raise RuntimeError("公告目录未找到销售简报")
        cached_details = []
        if NOTICE_RAW_PATH.exists():
            cached_details = json.loads(NOTICE_RAW_PATH.read_text(encoding="utf-8"))
        detail_map = {item.get("art_code"): item for item in cached_details if item.get("content")}
        pending = [row for row in notices if row.get("art_code") not in detail_map]
        print(f"[销售简报] 共 {len(notices)} 份，缓存 {len(detail_map)} 份，新增/补取 {len(pending)} 份...")
        with ThreadPoolExecutor(max_workers=8) as executor:
            jobs = {executor.submit(fetch_notice_content, row["art_code"]): row for row in pending}
            for index, future in enumerate(as_completed(jobs), 1):
                try:
                    detail = future.result()
                    detail["title"] = detail.get("title") or jobs[future].get("title")
                    detail["notice_date"] = detail.get("notice_date") or jobs[future].get("notice_date")
                    detail_map[detail["art_code"]] = detail
                except Exception as exc:
                    print(f"  跳过 {jobs[future].get('art_code')}: {exc}")
                if index % 20 == 0:
                    print(f"  已处理 {index}/{len(pending)}")
        details = list(detail_map.values())
        NOTICE_RAW_PATH.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
        source = "东方财富公告接口 / 牧原股份月度销售简报"
    except Exception as exc:
        if not allow_cache or not NOTICE_RAW_PATH.exists():
            raise
        print(f"[销售简报] 联网失败，使用缓存: {exc}")
        details = json.loads(NOTICE_RAW_PATH.read_text(encoding="utf-8"))
        source = "本地销售简报缓存"
    records = [record for item in details if (record := parse_sales_notice(item)) is not None]
    frame = pd.DataFrame(records)
    if frame.empty:
        raise RuntimeError("销售简报未解析出有效数据")
    frame = frame.sort_values(["期间截止日", "公告日期"]).drop_duplicates("期间截止日", keep="last")
    numeric = ["销量_万头", "销售收入_亿元", "商品猪销售均价_元每公斤", "收入反推平均重量_公斤每头"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    return frame.reset_index(drop=True), source


def normalize_business(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["报告日期"] = pd.to_datetime(frame["报告日期"], errors="coerce")
    for column in ["主营收入", "主营成本", "主营利润", "毛利率"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    product = frame[(frame["主营构成"] == "生猪") & (frame["分类类型"] == "按产品分类")].copy()
    if product.empty:
        product = frame[frame["主营构成"].isin(["养殖业务", "养殖行业", "养殖业"])].copy()
    product = product.dropna(subset=["报告日期", "主营收入", "主营成本"])
    return product.sort_values("报告日期").drop_duplicates("报告日期", keep="last")


def fetch_business_data(allow_cache: bool) -> tuple[pd.DataFrame, str]:
    try:
        print("[主营构成] 通过 AkShare 拉取生猪业务收入和成本...")
        frame = ak.stock_zygc_em(symbol="SZ002714")
        if frame.empty:
            raise RuntimeError("AkShare 返回空数据")
        source = "AkShare / 东方财富主营构成"
    except Exception as first_error:
        try:
            payload = curl_json(BUSINESS_URL + "?" + urllib.parse.urlencode({"code": "SZ002714"}))
            raw = pd.DataFrame(payload.get("zygcfx") or [])
            if raw.empty:
                raise RuntimeError("curl 后备接口返回空数据")
            frame = raw.rename(columns={
                "SECURITY_CODE": "股票代码", "REPORT_DATE": "报告日期", "MAINOP_TYPE": "分类类型",
                "ITEM_NAME": "主营构成", "MAIN_BUSINESS_INCOME": "主营收入", "MBI_RATIO": "收入比例",
                "MAIN_BUSINESS_COST": "主营成本", "MBC_RATIO": "成本比例",
                "MAIN_BUSINESS_RPOFIT": "主营利润", "MBR_RATIO": "利润比例", "GROSS_RPOFIT_RATIO": "毛利率",
            })
            frame["分类类型"] = frame["分类类型"].map({"2": "按产品分类", "3": "按地区分类"})
            source = "东方财富主营构成（curl TLS 后备）"
        except Exception:
            if not allow_cache or not BUSINESS_PATH.exists():
                raise RuntimeError(f"主营构成拉取失败: {first_error}") from first_error
            cached = pd.read_csv(BUSINESS_PATH)
            cached["报告日期"] = pd.to_datetime(cached["报告日期"], errors="coerce")
            return cached, "本地主营构成缓存"
    return normalize_business(frame), source


def fetch_unadjusted_stock(allow_cache: bool) -> tuple[pd.DataFrame, str]:
    rows: list[list[str]] = []
    try:
        current_year = datetime.now().year
        for start_year in range(2014, current_year + 1, 2):
            end_year = min(start_year + 1, current_year)
            end_date = f"{end_year}-12-31" if end_year < current_year else datetime.now().strftime("%Y-%m-%d")
            params = f"sz002714,day,{start_year}-01-01,{end_date},640"
            url = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline?" + urllib.parse.urlencode({"param": params})
            payload = curl_json(url)
            batch = (payload.get("data") or {}).get("sz002714", {}).get("day") or []
            if not batch:
                raise RuntimeError(f"{start_year}-{end_year} 未返回K线")
            rows.extend(batch)
        STOCK_RAW_PATH.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        source = "腾讯证券未复权日线（AkShare行情TLS后备）"
    except Exception as exc:
        if not allow_cache or not STOCK_RAW_PATH.exists():
            raise
        print(f"[股价] 联网失败，使用缓存: {exc}")
        rows = json.loads(STOCK_RAW_PATH.read_text(encoding="utf-8"))
        source = "本地未复权股价缓存"
    frame = pd.DataFrame([row[:6] for row in rows], columns=["日期", "开盘", "收盘", "最高", "最低", "成交量"])
    frame["日期"] = pd.to_datetime(frame["日期"], errors="coerce")
    for column in ["开盘", "收盘", "最高", "最低", "成交量"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["日期", "收盘"]).sort_values("日期").drop_duplicates("日期"), source


def read_financial(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"缺少 {path}，请先运行 fetch_financial_reports.py")
    frame = pd.read_csv(path)
    frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"], errors="coerce")
    return frame.dropna(subset=["REPORT_DATE"]).sort_values("REPORT_DATE")


def sales_overlap_adjusted(sales: pd.DataFrame) -> pd.DataFrame:
    """组合月份公告按覆盖月数保留；避免把1-2月合并公告当成单月。"""
    return sales.copy().sort_values("期间截止日")


def aggregate_sales_to_report(sales: pd.DataFrame, report_date: pd.Timestamp) -> dict[str, float]:
    selected = sales[(sales["年份"] == report_date.year) & (sales["截止月份"] <= report_date.month)].copy()
    if selected.empty:
        return {"公告销量_万头": np.nan, "公告销售收入_亿元": np.nan, "公告加权售价_元每公斤": np.nan,
                "反推平均重量_公斤每头": np.nan}
    volume = selected["销量_万头"].sum(min_count=1)
    revenue = selected["销售收入_亿元"].sum(min_count=1)
    valid = selected.dropna(subset=["销售收入_亿元", "商品猪销售均价_元每公斤"])
    implied_kg = (valid["销售收入_亿元"] * 1e8 / valid["商品猪销售均价_元每公斤"]).sum()
    price = revenue * 1e8 / implied_kg if revenue > 0 and implied_kg > 0 else np.nan
    weight = implied_kg / (volume * 1e4) if volume > 0 and implied_kg > 0 else np.nan
    return {"公告销量_万头": volume, "公告销售收入_亿元": revenue,
            "公告加权售价_元每公斤": price, "反推平均重量_公斤每头": weight}


def build_operating_history(sales: pd.DataFrame, business: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, item in business.iterrows():
        report_date = pd.Timestamp(item["报告日期"])
        sale = aggregate_sales_to_report(sales, report_date)
        cost_ratio = item["主营成本"] / item["主营收入"] if item["主营收入"] else np.nan
        implied_cost = sale["公告加权售价_元每公斤"] * cost_ratio
        rows.append({
            "报告日期": report_date, **sale,
            "生猪主营收入_亿元": item["主营收入"] / 1e8,
            "生猪主营成本_亿元": item["主营成本"] / 1e8,
            "生猪主营毛利率_%": (1 - cost_ratio) * 100,
            "报表隐含单位成本_元每公斤": implied_cost,
        })
    return pd.DataFrame(rows).sort_values("报告日期")


def annual_sales(sales: pd.DataFrame) -> pd.DataFrame:
    return sales.groupby("年份", as_index=False).agg(
        年销量_万头=("销量_万头", "sum"), 年销售收入_亿元=("销售收入_亿元", "sum"),
    )


def quarterly_financials() -> pd.DataFrame:
    single = read_financial("主要财务指标_按单季度.csv")
    result = single[["REPORT_DATE", "PARENTNETPROFIT"]].copy()
    result["PARENTNETPROFIT"] = pd.to_numeric(result["PARENTNETPROFIT"], errors="coerce") / 1e8
    result["季度"] = result["REPORT_DATE"].dt.to_period("Q")
    return result.sort_values("REPORT_DATE")


def find_cycle_peaks(price: pd.DataFrame) -> pd.DataFrame:
    data = price.copy().sort_values("报告日期").reset_index(drop=True)
    threshold = data["季度均价_元每公斤"].quantile(0.65)
    candidates = []
    for index, row in data.iterrows():
        left, right = max(0, index - 3), min(len(data), index + 4)
        if row["季度均价_元每公斤"] >= threshold and row["季度均价_元每公斤"] >= data.iloc[left:right]["季度均价_元每公斤"].max():
            candidates.append(index)
    selected: list[int] = []
    for index in candidates:
        if selected and index - selected[-1] < 6:
            if data.loc[index, "季度均价_元每公斤"] > data.loc[selected[-1], "季度均价_元每公斤"]:
                selected[-1] = index
        else:
            selected.append(index)
    return data.loc[selected, ["报告日期", "季度", "季度均价_元每公斤"]].reset_index(drop=True)


def latest_before(frame: pd.DataFrame, date: pd.Timestamp, date_column: str = "REPORT_DATE") -> pd.Series | None:
    eligible = frame[frame[date_column] <= date]
    return None if eligible.empty else eligible.iloc[-1]


def build_top_valuations(stock: pd.DataFrame, price: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    balance = read_financial("资产负债表_按报告期.csv")
    for column in ["SHARE_CAPITAL", "TOTAL_PARENT_EQUITY"]:
        balance[column] = pd.to_numeric(balance[column], errors="coerce")
    qprofit = quarterly_financials()
    annual = annual_sales(sales).set_index("年份")
    rows = []
    for _, peak in find_cycle_peaks(price).iterrows():
        pig_peak = pd.Timestamp(peak["报告日期"])
        window = stock[(stock["日期"] >= pig_peak - pd.DateOffset(months=12)) & (stock["日期"] <= pig_peak + pd.DateOffset(months=3))]
        if window.empty:
            continue
        stock_peak = window.loc[window["收盘"].idxmax()]
        date, close = pd.Timestamp(stock_peak["日期"]), float(stock_peak["收盘"])
        bal = latest_before(balance, date)
        if bal is None or not bal["SHARE_CAPITAL"]:
            continue
        market_cap = close * bal["SHARE_CAPITAL"] / 1e8
        quarter = date.to_period("Q")
        forward_profit = qprofit[(qprofit["季度"] > quarter) & (qprofit["季度"] <= quarter + 4)]["PARENTNETPROFIT"].sum(min_count=4)
        volume_year = date.year if date.month >= 7 else date.year - 1
        volume = annual.loc[volume_year, "年销量_万头"] if volume_year in annual.index else np.nan
        rows.append({
            "猪周期顶部季度": peak["季度"], "顶部季度猪价_元每公斤": peak["季度均价_元每公斤"],
            "观察窗口股价高点日": date, "未复权股价高点_元": close, "总市值_亿元": market_cap,
            "未来四季归母净利润_亿元": forward_profit,
            "前瞻PE_倍": market_cap / forward_profit if forward_profit > 0 else np.nan,
            "PB_倍": market_cap * 1e8 / bal["TOTAL_PARENT_EQUITY"] if bal["TOTAL_PARENT_EQUITY"] > 0 else np.nan,
            "参考年销量_万头": volume,
            "市值每万头_亿元": market_cap / volume if volume > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def quantile(values: pd.Series, q: float, fallback: float) -> float:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    clean = clean[clean > 0]
    return float(clean.quantile(q)) if not clean.empty else fallback


def build_model(
    sales: pd.DataFrame, operating: pd.DataFrame, tops: pd.DataFrame,
    current_price: float, config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    balance = read_financial("资产负债表_按报告期.csv")
    income = read_financial("利润表_按报告期.csv")
    latest_balance = balance.iloc[-1]
    shares = float(pd.to_numeric(latest_balance["SHARE_CAPITAL"], errors="coerce"))
    equity = float(pd.to_numeric(latest_balance["TOTAL_PARENT_EQUITY"], errors="coerce")) / 1e8

    latest_year = int(sales["年份"].max())
    latest_year_sales = sales[sales["年份"] == latest_year]
    covered_months = int(latest_year_sales["覆盖月数"].sum())
    volume_ytd = float(latest_year_sales["销量_万头"].sum())
    annualized_volume = volume_ytd * 12 / max(covered_months, 1)
    valid_weight = sales.loc[sales["收入反推平均重量_公斤每头"].between(80, 150), "收入反推平均重量_公斤每头"]
    observed_weight = quantile(valid_weight.tail(24), 0.5, 115.0)
    model_weight = float(config["average_weight_kg"])
    latest_cost = float(operating["报表隐含单位成本_元每公斤"].dropna().iloc[-1])

    latest_annual_income = income[income["REPORT_DATE"].dt.month == 12].iloc[-1]
    latest_profit = float(pd.to_numeric(latest_annual_income["PARENT_NETPROFIT"], errors="coerce")) / 1e8
    latest_operating = operating[operating["报告日期"].dt.month == 12].iloc[-1]
    latest_pig_gross = latest_operating["生猪主营收入_亿元"] - latest_operating["生猪主营成本_亿元"]
    below_gross = latest_profit - latest_pig_gross

    calibration_start = pd.Timestamp(config["valuation_calibration_start"])
    calibration_tops = tops[pd.to_datetime(tops["观察窗口股价高点日"]) >= calibration_start]
    if len(calibration_tops) < 2:
        raise ValueError("成熟规模阶段的历史周期顶部样本不足")
    rows = []
    for scenario in config["scenarios"]:
        name = scenario["name"]
        pig_price = float(scenario["pig_price_yuan_per_kg"])
        unit_cost = float(scenario["unit_cost_yuan_per_kg"])
        volume = float(scenario["annual_volume_10k_heads"])
        valuation_q = float(scenario["valuation_quantile"])
        revenue = volume * 1e4 * model_weight * pig_price / 1e8
        pig_gross = volume * 1e4 * model_weight * (pig_price - unit_cost) / 1e8
        net_profit = pig_gross + below_gross
        pe = quantile(calibration_tops.get("前瞻PE_倍", pd.Series(dtype=float)), valuation_q, 10.0)
        pb = quantile(calibration_tops.get("PB_倍", pd.Series(dtype=float)), valuation_q, 3.0)
        cap_per_volume = quantile(calibration_tops.get("市值每万头_亿元", pd.Series(dtype=float)), valuation_q, 0.5)
        pe_cap = net_profit * pe if net_profit > 0 else np.nan
        forecast_equity = equity + max(net_profit, 0) * (1 - float(config["dividend_payout_ratio"]))
        pb_cap = forecast_equity * pb
        volume_cap = volume * cap_per_volume
        if np.isfinite(pe_cap):
            target_cap = float(pe_cap)
            target_method = "前瞻PE法"
        else:
            target_cap = float(equity * float(config["loss_case_pb"]))
            target_method = f"亏损期PB法({float(config['loss_case_pb']):.2f}倍)"
        caps = pd.Series([target_cap, pb_cap, volume_cap], dtype=float).dropna()
        target_price = target_cap * 1e8 / shares
        rows.append({
            "情景": name, "商品猪售价_元每公斤": pig_price, "报表隐含成本_元每公斤": unit_cost,
            "年出栏量_万头": volume, "平均重量_公斤每头": model_weight,
            "预测生猪收入_亿元": revenue, "预测生猪毛利_亿元": pig_gross,
            "毛利以下及其他业务_亿元": below_gross, "预测归母净利润_亿元": net_profit,
            "历史顶部前瞻PE_倍": pe, "历史顶部PB_倍": pb,
            "历史顶部市值每万头_亿元": cap_per_volume,
            "PE法市值_亿元": pe_cap, "PB法市值_亿元": pb_cap, "出栏量法市值_亿元": volume_cap,
            "主估值方法": target_method, "核心目标市值_亿元": target_cap,
            "交叉验证市值下沿_亿元": float(caps.min()), "交叉验证市值上沿_亿元": float(caps.max()),
            "目标价_元": target_price,
            "相对当前价空间_%": (target_price / current_price - 1) * 100,
        })
    scenarios = pd.DataFrame(rows)

    base = scenarios[scenarios["情景"] == "基准"].iloc[0]
    price_grid = np.arange(max(8.0, math.floor(base["商品猪售价_元每公斤"] - 4)), math.ceil(base["商品猪售价_元每公斤"] + 4.1), 1.0)
    cost_grid = np.arange(max(8.0, math.floor(base["报表隐含成本_元每公斤"] - 2)), math.ceil(base["报表隐含成本_元每公斤"] + 2.1), 0.5)
    sensitivity_rows = []
    for pig_price in price_grid:
        for unit_cost in cost_grid:
            gross = base["年出栏量_万头"] * 1e4 * base["平均重量_公斤每头"] * (pig_price - unit_cost) / 1e8
            profit = gross + base["毛利以下及其他业务_亿元"]
            target = profit * base["历史顶部前瞻PE_倍"] * 1e8 / shares if profit > 0 else np.nan
            sensitivity_rows.append({
                "猪价_元每公斤": pig_price, "单位成本_元每公斤": unit_cost,
                "预测归母净利润_亿元": profit, "PE法目标价_元": target,
            })
    assumptions = {
        "model": "出栏量×平均重量×(商品猪售价-报表隐含单位成本)+毛利以下及其他业务",
        "current_price": current_price, "share_capital": shares, "parent_equity_亿元": equity,
        "sales_latest_year": latest_year, "sales_covered_months": covered_months,
        "annualized_volume_万头": annualized_volume,
        "observed_weight_median_公斤每头": observed_weight,
        "model_weight_公斤每头": model_weight,
        "latest_implicit_cost_元每公斤": latest_cost, "below_gross_and_other_亿元": below_gross,
        "valuation_calibration_start": config["valuation_calibration_start"],
        "loss_case_pb": float(config["loss_case_pb"]),
        "valuation": "历史猪价顶部前12个月至后3个月内的股价高点；使用事后未来四季利润计算前瞻PE，并同时参考PB和市值/出栏量；估值分位数仅使用成熟规模阶段样本",
        "important_limit": "单位成本由生猪主营成本率×公司销售简报加权售价反推，不等于管理层披露的即时完全成本",
    }
    return scenarios, pd.DataFrame(sensitivity_rows), assumptions


def fig_html(fig: go.Figure, first: bool = False) -> str:
    fig.update_layout(
        paper_bgcolor=COLORS["paper"], plot_bgcolor=COLORS["paper"],
        font={"family": "Microsoft YaHei UI, sans-serif", "color": COLORS["ink"]},
        margin={"l": 55, "r": 35, "t": 75, "b": 50}, hovermode="x unified",
        legend={"orientation": "h", "y": 1.04, "x": 1, "xanchor": "right"},
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["line"])
    fig.update_yaxes(gridcolor=COLORS["line"])
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if first else False, config={"displaylogo": False})


def build_report(
    sales: pd.DataFrame, operating: pd.DataFrame, tops: pd.DataFrame,
    scenarios: pd.DataFrame, sensitivity: pd.DataFrame, assumptions: dict,
    sources: dict[str, str],
) -> str:
    yearly = annual_sales(sales)
    volume = go.Figure()
    volume.add_bar(x=yearly["年份"], y=yearly["年销量_万头"], name="销量", marker_color=COLORS["green"])
    volume.update_layout(title="出栏规模与销售收入", height=420)
    volume.add_scatter(x=yearly["年份"], y=yearly["年销售收入_亿元"], name="销售收入", yaxis="y2", line={"color": COLORS["amber"], "width": 3})
    volume.update_layout(yaxis={"title": "销量（万头）"}, yaxis2={"title": "收入（亿元）", "overlaying": "y", "side": "right"})

    cost = go.Figure()
    cost.add_scatter(x=operating["报告日期"], y=operating["公告加权售价_元每公斤"], name="公司销售均价", line={"color": COLORS["red"], "width": 3})
    cost.add_scatter(x=operating["报告日期"], y=operating["报表隐含单位成本_元每公斤"], name="报表隐含单位成本", line={"color": COLORS["blue"], "width": 3})
    cost.update_layout(title="猪价与报表隐含单位成本", yaxis_title="元/公斤", height=420)

    target = go.Figure()
    for method, color in [("PE法市值_亿元", COLORS["red"]), ("PB法市值_亿元", COLORS["blue"]), ("出栏量法市值_亿元", COLORS["amber"])]:
        target.add_bar(x=scenarios["情景"], y=scenarios[method], name=method.replace("市值_亿元", ""), marker_color=color)
    target.add_scatter(x=scenarios["情景"], y=scenarios["核心目标市值_亿元"], name="核心估值", mode="lines+markers", line={"color": COLORS["ink"], "width": 3})
    target.update_layout(title="三种估值方法交叉验证", yaxis_title="目标市值（亿元）", barmode="group", height=430)

    base = scenarios[scenarios["情景"] == "基准"].iloc[0]
    profit_per_spread_yuan = base["年出栏量_万头"] * base["平均重量_公斤每头"] / 1e4
    mature_tops = tops[pd.to_datetime(tops["观察窗口股价高点日"]) >= pd.Timestamp(assumptions["valuation_calibration_start"])]
    mature_pe = pd.to_numeric(mature_tops["前瞻PE_倍"], errors="coerce").dropna()
    mature_pb = pd.to_numeric(mature_tops["PB_倍"], errors="coerce").dropna()
    highest_pe = mature_tops.loc[pd.to_numeric(mature_tops["前瞻PE_倍"], errors="coerce").idxmax()]
    matrix = sensitivity.pivot(index="单位成本_元每公斤", columns="猪价_元每公斤", values="PE法目标价_元")
    heat_text = [["" if pd.isna(value) else f"{value:.1f}" for value in row] for row in matrix.to_numpy()]
    heat = go.Figure(go.Heatmap(
        x=matrix.columns, y=matrix.index, z=matrix.values, colorscale="RdYlGn",
        text=heat_text, texttemplate="%{text}", colorbar={"title": "元"},
    ))
    heat.update_layout(title="猪价 × 单位成本：PE法目标价敏感性", xaxis_title="猪价（元/公斤）", yaxis_title="单位成本（元/公斤）", height=520)

    scenario_rows = "".join(
        f"<tr><td>{row['情景']}</td><td>{row['商品猪售价_元每公斤']:.2f}</td><td>{row['报表隐含成本_元每公斤']:.2f}</td>"
        f"<td>{row['年出栏量_万头']:.0f}</td><td>{row['预测归母净利润_亿元']:.1f}</td><td>{row['历史顶部前瞻PE_倍']:.1f}</td>"
        f"<td>{row['主估值方法']}</td><td>{row['核心目标市值_亿元']:.0f}</td><td><strong>{row['目标价_元']:.2f}</strong></td><td>{row['相对当前价空间_%']:+.1f}%</td></tr>"
        for _, row in scenarios.iterrows()
    )
    top_rows = "".join(
        f"<tr><td>{row['猪周期顶部季度']}</td><td>{row['顶部季度猪价_元每公斤']:.2f}</td><td>{row['观察窗口股价高点日']:%Y-%m-%d}</td>"
        f"<td>{row['未复权股价高点_元']:.2f}</td><td>{row['前瞻PE_倍']:.1f}</td><td>{row['PB_倍']:.2f}</td><td>{row['市值每万头_亿元']:.3f}</td></tr>"
        for _, row in tops.iterrows()
    )
    charts = "".join([
        fig_html(volume, True), fig_html(cost), fig_html(target), fig_html(heat),
    ])
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>牧原股份基本面估值</title><style>
:root{{--paper:#f5f3ed;--ink:#202421;--muted:#6e726c;--line:#d3d5cf;--red:#b33b32}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei UI",sans-serif;letter-spacing:0}}.shell{{width:min(1160px,calc(100% - 40px));margin:auto}}
header{{padding:42px 0 26px;border-bottom:1px solid var(--ink)}}h1{{font:500 48px/1.15 "STZhongsong","SimSun",serif;margin:14px 0}}.lead,.note{{color:var(--muted);font-size:12px;line-height:1.8;max-width:880px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--ink)}}.card{{padding:22px 16px;border-right:1px solid var(--line)}}.card:last-child{{border:0}}.card span,.card small{{display:block;color:var(--muted);font-size:10px}}.card strong{{display:block;font:500 23px "STZhongsong","SimSun",serif;margin:8px 0}}
h2{{font:500 28px "STZhongsong","SimSun",serif;margin:52px 0 14px}}.chart{{border-top:1px solid var(--ink);border-bottom:1px solid var(--line)}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{padding:11px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}th{{color:var(--muted);font-weight:400}}.scroll{{overflow-x:auto}}.warning{{margin:24px 0;padding:18px 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);color:var(--muted);font-size:11px;line-height:1.8}}footer{{margin-top:46px;padding:22px 0;border-top:1px solid var(--ink);color:var(--muted);font-size:10px}}
.conclusion{{margin:14px 0 24px;padding:14px 0;color:var(--ink);font-size:12px;line-height:1.85;border-bottom:1px solid var(--line)}}.conclusion strong{{color:var(--red)}}
@media(max-width:760px){{.cards{{grid-template-columns:1fr 1fr}}.card:nth-child(2){{border-right:0}}h1{{font-size:36px}}}}
</style></head><body><div class="shell"><header><small>基本面估值 / SZ.002714</small><h1>量、价、成本与周期顶部估值</h1><p class="lead">目标价由经营假设逐项计算，不使用股价相关性回归。核心公式为：出栏量 × 平均重量 ×（商品猪售价 − 单位成本）+ 毛利以下及其他业务，再以历史周期顶部的前瞻 PE、PB 和市值/出栏量交叉估值。</p></header>
<section class="cards"><div class="card"><span>当前股价</span><strong>{assumptions['current_price']:.2f}元</strong><small>未复权最新收盘</small></div><div class="card"><span>基准目标价</span><strong>{base['目标价_元']:.2f}元</strong><small>{base['主估值方法']}</small></div><div class="card"><span>基准预测净利润</span><strong>{base['预测归母净利润_亿元']:.1f}亿</strong><small>公式推导</small></div><div class="card"><span>基准量价成本</span><strong>{base['年出栏量_万头']:.0f}万头</strong><small>售价 {base['商品猪售价_元每公斤']:.2f} / 成本 {base['报表隐含成本_元每公斤']:.2f}</small></div></section>
<h2>基本面情景</h2><div class="scroll"><table><thead><tr><th>情景</th><th>猪价</th><th>成本</th><th>出栏量(万头)</th><th>归母净利(亿)</th><th>前瞻PE</th><th>主估值方法</th><th>目标市值(亿)</th><th>目标价</th><th>空间</th></tr></thead><tbody>{scenario_rows}</tbody></table></div>
<div class="conclusion"><strong>表格结论：</strong>基准情景在售价 {base['商品猪售价_元每公斤']:.2f} 元/公斤、成本 {base['报表隐含成本_元每公斤']:.2f} 元/公斤和出栏 {base['年出栏量_万头']:.0f} 万头的假设下，预测归母净利润约 {base['预测归母净利润_亿元']:.1f} 亿元，前瞻 PE 法目标价约 {base['目标价_元']:.2f} 元。按当前基准出栏量和体重，售价与单位成本的价差每扩大或收窄 1 元/公斤，预测利润约同向变化 {profit_per_spread_yuan:.1f} 亿元，因此成本判断与猪价判断同等重要。压力情景出现亏损时，PE 失效，模型自动切换到低位 PB。</div>
<div class="warning"><strong>成本口径：</strong>{html.escape(str(assumptions['important_limit']))}。收入反推重量还会受到仔猪、种猪产品结构影响，因此模型所有假设均保留在 CSV/JSON 中供复核，不应把单一目标价理解为确定性预测。未来猪价路径及当前周期位置请结合<a href="猪周期驱动与顶部预测.html">猪周期驱动与顶部预测</a>报告更新。</div>
<section class="chart">{charts}</section>
<div class="conclusion"><strong>敏感性矩阵结论：</strong>横轴是商品猪售价，纵轴是单位成本，每个格子是在出栏量 {base['年出栏量_万头']:.0f} 万头、平均重量 {base['平均重量_公斤每头']:.0f} 公斤/头、毛利以下及其他业务影响 {base['毛利以下及其他业务_亿元']:.1f} 亿元和前瞻 PE {base['历史顶部前瞻PE_倍']:.2f} 倍保持不变时的目标价。越靠右下方，售价与成本的价差越大，目标价越高；空白格表示预测利润小于等于零，PE 不适用，应改看 PB。该矩阵用于检查假设敏感度，不表示猪价和成本一定会落在某个格子。</div>
<h2>历史周期顶部估值样本</h2><div class="scroll"><table><thead><tr><th>猪价顶部</th><th>顶部猪价</th><th>窗口股价高点</th><th>股价</th><th>事后前瞻PE</th><th>PB</th><th>市值/万头</th></tr></thead><tbody>{top_rows}</tbody></table></div>
<div class="conclusion"><strong>表格结论：</strong>2020 年以来成熟规模阶段共有 {len(mature_tops)} 个顶部样本，事后前瞻 PE 中位数为 {mature_pe.median():.2f} 倍，PB 中位数为 {mature_pb.median():.2f} 倍。最高前瞻 PE 出现在 {highest_pe['猪周期顶部季度']}，达到 {highest_pe['前瞻PE_倍']:.2f} 倍，主要因为随后四季利润偏低，不能直接套用于高利润景气情景。模型因此以 PE 为核心、PB 和市值/出栏量为交叉检查，并且景气情景不再同时上调估值倍数。</div>
<div class="warning"><strong>前瞻 PE 定义：</strong>历史股价高点当日总市值 ÷ 该高点之后四个季度实际归母净利润。它与使用过去利润的 TTM PE 不同，并带有事后视角，只用于观察市场曾经为未来一年利润支付多少倍估值，不表示当时投资者能够准确预知利润。<br><strong>顶部识别：</strong>{html.escape(str(assumptions['valuation']))}。<br><strong>数据源：</strong>销售：{html.escape(sources['sales'])}；主营构成：{html.escape(sources['business'])}；股价：{html.escape(sources['stock'])}。</div>
</div><footer><div class="shell">生成于 {generated} · 情景估值不构成投资建议</div></footer></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="牧原股份量价成本与历史周期顶部估值")
    parser.add_argument("--no-cache", action="store_true", help="联网失败时禁止使用缓存")
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"缺少估值配置: {CONFIG_PATH}")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    sales, sales_source = fetch_sales_data(not args.no_cache)
    business, business_source = fetch_business_data(not args.no_cache)
    stock, stock_source = fetch_unadjusted_stock(not args.no_cache)
    operating = build_operating_history(sales_overlap_adjusted(sales), business)
    price = pd.read_csv(DATA_DIR / "生猪价格_季度.csv")
    price["报告日期"] = pd.to_datetime(price["报告日期"], errors="coerce")
    tops = build_top_valuations(stock, price, sales)
    if len(tops) < 2:
        raise RuntimeError(f"历史周期顶部有效样本不足: {len(tops)}")
    scenarios, sensitivity, assumptions = build_model(
        sales, operating, tops, float(stock.iloc[-1]["收盘"]), config
    )

    atomic_csv(sales, SALES_PATH)
    atomic_csv(business, BUSINESS_PATH)
    atomic_csv(stock, STOCK_PATH)
    atomic_csv(operating, OPERATING_PATH)
    atomic_csv(tops, TOP_PATH)
    atomic_csv(scenarios, SCENARIO_PATH)
    atomic_csv(sensitivity, SENSITIVITY_PATH)
    ASSUMPTION_PATH.write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(
        sales, operating, tops, scenarios, sensitivity, assumptions,
        {"sales": sales_source, "business": business_source, "stock": stock_source},
    ), encoding="utf-8")

    base = scenarios[scenarios["情景"] == "基准"].iloc[0]
    print(f"月度销售数据: {SALES_PATH} ({len(sales)} 条)")
    print(f"历史顶部样本: {TOP_PATH} ({len(tops)} 个周期)")
    print(f"基本面估值情景: {SCENARIO_PATH}")
    print(f"基准目标价: {base['目标价_元']:.2f} 元；当前价: {assumptions['current_price']:.2f} 元")
    print(f"可视化报告: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
