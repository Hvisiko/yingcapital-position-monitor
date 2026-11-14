from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


BASE_URL = "https://www.binance.com/bapi/futures/v1/friendly/future/copy-trade"


class BinanceError(RuntimeError):
    pass


class PositionDataUnavailable(BinanceError):
    """接口成功，但币安没有公开有效仓位数据。"""


@dataclass(frozen=True)
class BinanceSnapshot:
    detail: dict[str, Any]
    position_rows: list[dict[str, Any]]


class BinanceClient:
    def __init__(
        self,
        portfolio_id: str,
        *,
        timeout: float = 25,
        max_attempts: int = 3,
    ) -> None:
        self.portfolio_id = portfolio_id
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 YingCapitalPositionMonitor/1.0",
            "clienttype": "web",
            "Origin": "https://www.binance.com",
            "Referer": (
                "https://www.binance.com/zh-CN/copy-trading/lead-details/"
                f"{portfolio_id}"
            ),
        }

    def _get(self, path: str) -> Any:
        query = urllib.parse.urlencode({"portfolioId": self.portfolio_id})
        url = f"{BASE_URL}/{path}?{query}"
        request = urllib.request.Request(url=url, headers=self.headers, method="GET")

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if payload.get("success") is not True or payload.get("code") != "000000":
                    raise BinanceError(
                        f"币安接口返回失败：code={payload.get('code')} "
                        f"message={payload.get('message')}"
                    )
                return payload.get("data")
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in {429, 500, 502, 503, 504}:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error

            if attempt < self.max_attempts:
                time.sleep(2 ** (attempt - 1))

        raise BinanceError(f"币安接口请求失败：{last_error}") from last_error

    def fetch_snapshot(self) -> BinanceSnapshot:
        detail = self._get("lead-portfolio/detail")
        if not isinstance(detail, dict):
            raise BinanceError("币安项目详情格式无效")
        if str(detail.get("leadPortfolioId")) != self.portfolio_id:
            raise BinanceError("币安返回了不匹配的项目 ID")

        position_data = self._get("lead-data/positions")
        visibility = detail.get("positionShow")
        if visibility is not True:
            raise PositionDataUnavailable(
                f"当前仓位未公开（positionShow={visibility}）"
            )
        if position_data is None:
            raise PositionDataUnavailable(
                f"当前仓位未公开（positionShow={visibility}，positions data=null）"
            )
        if not isinstance(position_data, list):
            raise PositionDataUnavailable(
                f"当前仓位数据格式无效：{type(position_data).__name__}"
            )
        if not all(isinstance(row, dict) for row in position_data):
            raise PositionDataUnavailable("当前仓位列表包含无效记录")

        return BinanceSnapshot(detail=detail, position_rows=position_data)

