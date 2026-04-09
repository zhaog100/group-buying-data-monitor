"""
外卖平台抓取器
- 美团外卖
- 饿了么
- 京东到家
"""
import re
import json
import logging
from typing import Dict, Any
from datetime import datetime

from .config import MonitorConfig, Platform
from .models import DeliveryData
from .scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class MeituanScraper(BaseScraper):
    """美团外卖抓取器"""

    SHOP_URL = "https://www.waimai.meituan.com/restaurant/{shop_id}"
    SEARCH_URL = "https://www.waimai.meituan.com/api/v7/search"

    def __init__(self, config: MonitorConfig):
        super().__init__(Platform.MEITUAN, config)
        self.shop_id = config.store.meituan_shop_id

    async def scrape(self) -> Dict[str, Any]:
        if not self.shop_id:
            return DeliveryData(
                platform="meituan",
                scraped_at=datetime.now().isoformat(),
                status="failed",
                error_message="未配置美团外卖门店ID",
            ).to_dict()

        now = datetime.now().isoformat()
        url = self.SHOP_URL.format(shop_id=self.shop_id)
        response = await self._request_with_retry(url)

        if response and response.status_code == 200:
            return self._parse_shop(response.text, now)

        return DeliveryData(
            platform="meituan",
            scraped_at=now,
            status="failed",
            error_message="无法获取美团外卖数据",
        ).to_dict()

    def _parse_shop(self, html: str, now: str) -> Dict[str, Any]:
        data = DeliveryData(platform="meituan", scraped_at=now)
        try:
            # 从页面数据提取
            window_data = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', html, re.DOTALL)
            if window_data:
                state = json.loads(window_data.group(1))
                shop_info = state.get("shopInfo", state.get("shop", {}))
                data.store_rating = float(shop_info.get("wmPoiScore", shop_info.get("rating", 0)))
                data.sales_volume = int(shop_info.get("monthSaleNum", shop_info.get("sales", 0)))
                data.avg_delivery_time = int(shop_info.get("avgDeliveryTime", 0))

            # 提取商圈排名
            rank_match = re.search(r'"rankNo"\s*:\s*(\d+)', html)
            if rank_match:
                data.district_rank = int(rank_match.group(1))

            # 月订单量估算
            order_match = re.search(r'月售(\d+)[份单]', html)
            if order_match:
                data.order_count = int(order_match.group(1))

            # 转化率估算（基于评分和订单量推算）
            if data.order_count and data.store_rating:
                data.conversion_rate = round(data.store_rating * data.order_count / 10000, 4)

        except Exception as e:
            logger.error(f"[meituan] Parse error: {e}")
            data.status = "partial"
            data.error_message = str(e)

        return data.to_dict()


class ElemeScraper(BaseScraper):
    """饿了么抓取器"""

    SHOP_URL = "https://www.ele.me/shop/{shop_id}"
    API_URL = "https://www.ele.me/restapi/shopping/v2/restaurant/{shop_id}"

    def __init__(self, config: MonitorConfig):
        super().__init__(Platform.ELEME, config)
        self.shop_id = config.store.eleme_shop_id

    async def scrape(self) -> Dict[str, Any]:
        if not self.shop_id:
            return DeliveryData(
                platform="eleme",
                scraped_at=datetime.now().isoformat(),
                status="failed",
                error_message="未配置饿了么门店ID",
            ).to_dict()

        now = datetime.now().isoformat()

        # 尝试API
        api_url = self.API_URL.format(shop_id=self.shop_id)
        response = await self._request_with_retry(api_url)

        if response and response.status_code == 200:
            try:
                return self._parse_api(response.text, now)
            except Exception:
                pass

        # 备用：页面抓取
        url = self.SHOP_URL.format(shop_id=self.shop_id)
        response = await self._request_with_retry(url)

        if response and response.status_code == 200:
            return self._parse_shop(response.text, now)

        return DeliveryData(
            platform="eleme",
            scraped_at=now,
            status="failed",
            error_message="无法获取饿了么数据",
        ).to_dict()

    def _parse_api(self, text: str, now: str) -> Dict[str, Any]:
        data = DeliveryData(platform="eleme", scraped_at=now)
        resp = json.loads(text)
        info = resp.get("data", resp)

        data.store_rating = float(info.get("rating", info.get("score", 0)))
        data.order_count = int(info.get("recent_order_num", info.get("monthSales", 0)))
        data.avg_delivery_time = int(info.get("order_lead_time", 0))
        data.sales_volume = int(info.get("recent_order_num", 0))

        if data.order_count and data.store_rating:
            data.conversion_rate = round(data.store_rating * data.order_count / 10000, 4)

        return data.to_dict()

    def _parse_shop(self, html: str, now: str) -> Dict[str, Any]:
        data = DeliveryData(platform="eleme", scraped_at=now, status="partial")
        try:
            # 从页面提取数据
            rating_match = re.search(r'"rating"\s*:\s*([\d.]+)', html)
            if rating_match:
                data.store_rating = float(rating_match.group(1))

            order_match = re.search(r'月售(\d+)', html)
            if order_match:
                data.order_count = int(order_match.group(1))
                data.sales_volume = data.order_count

            time_match = re.search(r'(\d+)分钟', html)
            if time_match:
                data.avg_delivery_time = int(time_match.group(1))

        except Exception as e:
            data.error_message = str(e)

        return data.to_dict()


class JDScraper(BaseScraper):
    """京东到家抓取器"""

    SHOP_URL = "https://daojia.jd.com/html/{shop_id}.html"
    API_URL = "https://daojia.jd.com/client?functionId=shop/detail"

    def __init__(self, config: MonitorConfig):
        super().__init__(Platform.JD, config)
        self.shop_id = config.store.jd_shop_id

    async def scrape(self) -> Dict[str, Any]:
        if not self.shop_id:
            return DeliveryData(
                platform="jd",
                scraped_at=datetime.now().isoformat(),
                status="failed",
                error_message="未配置京东到家门店ID",
            ).to_dict()

        now = datetime.now().isoformat()

        # 尝试页面抓取
        url = self.SHOP_URL.format(shop_id=self.shop_id)
        response = await self._request_with_retry(url)

        if response and response.status_code == 200:
            return self._parse_page(response.text, now)

        return DeliveryData(
            platform="jd",
            scraped_at=now,
            status="failed",
            error_message="无法获取京东到家数据",
        ).to_dict()

    def _parse_page(self, html: str, now: str) -> Dict[str, Any]:
        data = DeliveryData(platform="jd", scraped_at=now)
        try:
            # 从京东到家页面提取数据
            window_data = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', html, re.DOTALL)
            if window_data:
                state = json.loads(window_data.group(1))
                shop = state.get("shop", state.get("storeInfo", {}))
                data.store_rating = float(shop.get("score", shop.get("rating", 0)))
                data.order_count = int(shop.get("salesCount", shop.get("monthSales", 0)))

            # 评分
            rating_match = re.search(r'(\d\.\d)分', html)
            if rating_match:
                data.store_rating = float(rating_match.group(1))

            # 月售
            sales_match = re.search(r'月售(\d+)', html)
            if sales_match:
                data.order_count = int(sales_match.group(1))
                data.sales_volume = data.order_count

        except Exception as e:
            logger.error(f"[jd] Parse error: {e}")
            data.status = "partial"
            data.error_message = str(e)

        return data.to_dict()
