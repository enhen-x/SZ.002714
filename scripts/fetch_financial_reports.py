#!/usr/bin/env python3
"""使用 AkShare 下载牧原股份的完整历史财务报表及主要财务指标。"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

try:
    import akshare as ak
    import pandas as pd
except ImportError as exc:
    raise SystemExit(
        "缺少依赖，请先执行: python -m pip install -U akshare pandas"
    ) from exc


STOCK_CODE = "002714"
DISPLAY_SYMBOL = "SZ.002714"
STOCK_NAME = "牧原股份"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data"


def fetch_with_retry(
    name: str,
    fetcher: Callable[[], pd.DataFrame],
    retries: int,
    retry_delay: float,
) -> pd.DataFrame:
    """调用接口并在临时网络错误时重试。"""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[{name}] 正在拉取（第 {attempt}/{retries} 次）...")
            frame = fetcher()
            if frame is None or frame.empty:
                raise RuntimeError("接口返回空数据")
            return frame
        except Exception as exc:  # AkShare 的底层请求异常类型并不统一
            last_error = exc
            if attempt < retries:
                print(f"[{name}] 拉取失败: {exc}; {retry_delay:g} 秒后重试")
                time.sleep(retry_delay)
    raise RuntimeError(f"连续 {retries} 次拉取失败: {last_error}") from last_error


def save_csv(frame: pd.DataFrame, path: Path) -> None:
    """先写临时文件，再替换正式文件，避免中断时留下半个 CSV。"""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp_path, index=False, encoding="utf-8-sig")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="下载牧原股份（SZ.002714）的全部历史财报数据"
    )
    parser.add_argument("--retries", type=int, default=3, help="每个接口的最大尝试次数")
    parser.add_argument(
        "--retry-delay", type=float, default=3.0, help="失败后的重试间隔（秒）"
    )
    args = parser.parse_args()
    if args.retries < 1 or args.retry_delay < 0:
        parser.error("--retries 必须大于 0，--retry-delay 不能小于 0")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 不同 AkShare 数据源使用不同的市场代码格式。
    eastmoney_statement_symbol = f"SZ{STOCK_CODE}"
    eastmoney_indicator_symbol = f"{STOCK_CODE}.SZ"

    datasets: list[tuple[str, str, Callable[[], pd.DataFrame]]] = [
        (
            "资产负债表",
            "资产负债表_按报告期.csv",
            lambda: ak.stock_balance_sheet_by_report_em(
                symbol=eastmoney_statement_symbol
            ),
        ),
        (
            "利润表",
            "利润表_按报告期.csv",
            lambda: ak.stock_profit_sheet_by_report_em(
                symbol=eastmoney_statement_symbol
            ),
        ),
        (
            "现金流量表",
            "现金流量表_按报告期.csv",
            lambda: ak.stock_cash_flow_sheet_by_report_em(
                symbol=eastmoney_statement_symbol
            ),
        ),
        (
            "主要财务指标（按报告期）",
            "主要财务指标_按报告期.csv",
            lambda: ak.stock_financial_analysis_indicator_em(
                symbol=eastmoney_indicator_symbol, indicator="按报告期"
            ),
        ),
        (
            "主要财务指标（按单季度）",
            "主要财务指标_按单季度.csv",
            lambda: ak.stock_financial_analysis_indicator_em(
                symbol=eastmoney_indicator_symbol, indicator="按单季度"
            ),
        ),
    ]

    started_at = datetime.now().astimezone()
    results: list[dict[str, object]] = []
    failures = 0

    for name, filename, fetcher in datasets:
        output_path = OUTPUT_DIR / filename
        try:
            frame = fetch_with_retry(name, fetcher, args.retries, args.retry_delay)
            save_csv(frame, output_path)
            results.append(
                {
                    "name": name,
                    "file": filename,
                    "status": "success",
                    "rows": len(frame),
                    "columns": len(frame.columns),
                }
            )
            print(f"[{name}] 已保存 {len(frame)} 行 -> {output_path}")
        except Exception as exc:
            failures += 1
            results.append(
                {
                    "name": name,
                    "file": filename,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"[{name}] 最终失败: {exc}")

    manifest = {
        "stock": {"symbol": DISPLAY_SYMBOL, "code": STOCK_CODE, "name": STOCK_NAME},
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "output_directory": str(OUTPUT_DIR),
        "datasets": results,
    }
    manifest_path = OUTPUT_DIR / "拉取清单.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    succeeded = len(datasets) - failures
    print(f"\n完成：成功 {succeeded} 项，失败 {failures} 项。清单：{manifest_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
