"""
评价平台抓取器
- 大众点评 (无API，需反爬)
- 抖音来客
- 高德地图
"""
import re
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .config import MonitorConfig, Platform
from .models import ReviewData
from .scraper_base import BaseScraper

logger = logging.getLogger(__name__)


class DianpingScraper(BaseScraper):
    """大众点评抓取器 - 无公开API，使用页面抓取+数据提取"""

    SEARCH_URL = "https://www.dianping.com/search/keyword/{city}/{district}_{keyword}"
    SHOP_URL = "https://www.dianping.com/shop/{shop_id}"

    def __init__(self, config: MonitorConfig):
        super().__init__(Platform.DIANPING, config)
        self.shop_id = config.store.dianping_shop_id

    async def scrape(self) -> Dict[str, Any]:
        if not self.shop_id:
            return ReviewData(
                platform="dianping",
                scraped_at=datetime.now().isoformat(),
                status="failed",
                error_message="未配置大众点评门店ID",
            ).to_dict()

        now = datetime.now().isoformat()

        # 方法1: 直接抓取门店页面
        response = await self._request_with_retry(
            self.SHOP_URL.format(shop_id=self.shop_id)
        )

        if response and response.status_code == 200:
            return self._parse_shop_page(response.text, now)

        # 方法2: 搜索页面获取排名
        search_url = self.SEARCH_URL.format(
            city=self.config.store.city or "2",  # 默认北京
            district=self.config.store.district or "r0",
            keyword=self.config.store.store_name or "",
        )
        response = await self._request_with_retry(search_url)
        if response and response.status_code == 200:
            return self._parse_search_page(response.text, now)

        return ReviewData(
            platform="dianping",
            scraped_at=now,
            status="failed",
            error_message="无法获取大众点评数据，可能被反爬拦截",
        ).to_dict()

    def _parse_shop_page(self, html: str, now: str) -> Dict[str, Any]:
        """解析门店页面"""
        data = ReviewData(platform="dianping", scraped_at=now)

        try:
            # 提取评分
            rating_match = re.search(r'"avgScore"\s*:\s*"?([\d.]+)"?', html)
            if rating_match:
                data.rating = float(rating_match.group(1))

            # 提取评论数
            comment_match = re.search(r'"reviewCount"\s*:\s*(\d+)', html)
            if comment_match:
                data.comment_count = int(comment_match.group(1))

            # 提取评论内容
            reviews = []
            review_blocks = re.findall(
                r'"reviewBody"\s*:\s*"([^"]+)"', html
            )
            for body in review_blocks[:10]:
                reviews.append({"content": body[:200]})
            data.review_content = reviews if reviews else None

            # 尝试从 JSON-LD 提取
            jsonld_match = re.search(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
            )
            if jsonld_match:
                try:
                    ld = json.loads(jsonld_match.group(1))
                    if "aggregateRating" in ld:
                        ar = ld["aggregateRating"]
                        data.rating = data.rating or float(ar.get("ratingValue", 0))
                        data.comment_count = data.comment_count or int(
                            ar.get("reviewCount", 0)
                        )
                except (json.JSONDecodeError, ValueError):
                    pass

        except Exception as e:
            logger.error(f"[dianping] Parse error: {e}")
            data.status = "partial"
            data.error_message = str(e)

        return data.to_dict()

    def _parse_search_page(self, html: str, now: str) -> Dict[str, Any]:
        """解析搜索结果获取排名"""
        data = ReviewData(platform="dianping", scraped_at=now, status="partial")

        try:
            # 查找门店在搜索结果中的排名
            shop_pattern = re.compile(
                re.escape(self.shop_id) + r'.*?data-rank="(\d+)"',
                re.DOTALL,
            )
            rank_match = shop_pattern.search(html)
            if rank_match:
                data.store_rank = int(rank_match.group(1))
            else:
                # 计算在列表中的位置
                all_shops = re.findall(r'shop-\d+', html)
                for i, shop_id in enumerate(all_shops):
                    if self.shop_id in shop_id:
                        data.store_rank = i + 1
                        break
        except Exception as e:
            data.error_message = str(e)

        return data.to_dict()


class DouyinScraper(BaseScraper):
    """抖音来客抓取器"""

    API_BASE = "https://www.douyin.com/aweme/v1/web"

    def __init__(self, config: MonitorConfig):
        super().__init__(Platform.DOUYIN, config)
        self.shop_id = config.store.douyin_shop_id

    async def scrape(self) -> Dict[str, Any]:
        if not self.shop_id:
            return ReviewData(
                platform="douyin",
                scraped_at=datetime.now().isoformat(),
                status="failed",
                error_message="未配置抖音来客门店ID",
            ).to_dict()

        now = datetime.now().isoformat()

        # 抖音来客主要通过商家后台API获取数据
        # 公开页面数据有限，尝试抓取门店公开信息
        url = f"https://www.douyin.com/discover?modal_id={self.shop_id}"
        response = await self._request_with_retry(url)

        if response and response.status_code == 200:
            return self._parse_page(response.text, now)

        # 备用：通过搜索接口
        search_url = f"{self.API_BASE}/search/item/"
        response = await self._request_with_retry(
            search_url,
            params={"keyword": self.config.store.store_name, "count": "10"},
        )

        if response and response.status_code == 200:
            return self._parse_api(response.text, now)

        return ReviewData(
            platform="douyin",
            scraped_at=now,
            status="failed",
            error_message="无法获取抖音来客数据",
        ).to_dict()

    def _parse_page(self, html: str, now: str) -> Dict[str, Any]:
        data = ReviewData(platform="douyin", scraped_at=now)
        try:
            # 从页面 SSR 数据提取
            render_data = re.search(r'renderData["\s]*[:=]\s*({.+?})\s*[;<]', html, re.DOTALL)
            if render_data:
                rd = json.loads(render_data.group(1))
                shop_data = rd.get("poiInfo", rd.get("shopInfo", {}))
                data.rating = float(shop_data.get("score", 0))
                data.comment_count = int(shop_data.get("commentCount", 0))
                data.consumer_count = int(shop_data.get("consumeNum", 0))

            # 提取用户级别分布
            level_pattern = re.findall(r'"userLevel"\s*:\s*"(\w+)"', html)
            if level_pattern:
                data.user_level = ",".join(set(level_pattern[:5]))

        except Exception as e:
            logger.error(f"[douyin] Parse error: {e}")
            data.status = "partial"
            data.error_message = str(e)

        return data.to_dict()

    def _parse_api(self, text: str, now: str) -> Dict[str, Any]:
        data = ReviewData(platform="douyin", scraped_at=now, status="partial")
        try:
            resp = json.loads(text)
            items = resp.get("data", [])
            for item in items[:10]:
                if self.shop_id in str(item):
                    data.rating = float(item.get("score", 0))
                    data.comment_count = int(item.get("comment_count", 0))
                    break
        except (json.JSONDecodeError, Exception) as e:
            data.error_message = str(e)
        return data.to_dict()


class GaodeScraper(BaseScraper):
    """高德地图抓取器 - 有公开POI API"""

    DETAIL_API = "https://www.amap.com/detail/get/detail"
    SEARCH_API = "https://www.amap.com/service/poiInfo/search"

    def __init__(self, config: MonitorConfig):
        super().__init__(Platform.GAODE, config)
        self.poi_id = config.store.gaode_poi_id

    async def scrape(self) -> Dict[str, Any]:
        now = datetime.now().isoformat()

        if self.poi_id:
            # 通过POI ID获取详情
            response = await self._request_with_retry(
                self.DETAIL_API,
                params={"id": self.poi_id},
            )
            if response and response.status_code == 200:
                return self._parse_detail(response.text, now)

        # 搜索获取
        response = await self._request_with_retry(
            self.SEARCH_API,
            params={
                "keywords": self.config.store.store_name,
                "city": self.config.store.city,
                "pagesize": "10",
            },
        )

        if response and response.status_code == 200:
            return self._parse_search(response.text, now)

        return ReviewData(
            platform="gaode",
            scraped_at=now,
            status="failed",
            error_message="无法获取高德地图数据",
        ).to_dict()

    def _parse_detail(self, text: str, now: str) -> Dict[str, Any]:
        data = ReviewData(platform="gaode", scraped_at=now)
        try:
            resp = json.loads(text)
            detail = resp.get("data", resp)

            data.rating = float(detail.get("rating", detail.get("score", 0)))
            data.comment_count = int(detail.get("comment_num", detail.get("commentCount", 0)))
            data.return_rate = float(detail.get("return_rate", detail.get("returnRate", 0)))

            # 榜单排名
            ranking_list = detail.get("ranking", detail.get("rankList", []))
            if ranking_list:
                data.ranking = ranking_list[0].get("rank") if isinstance(ranking_list, list) else None

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[gaode] Parse error: {e}")
            data.status = "partial"
            data.error_message = str(e)

        return data.to_dict()

    def _parse_search(self, text: str, now: str) -> Dict[str, Any]:
        data = ReviewData(platform="gaode", scraped_at=now, status="partial")
        try:
            resp = json.loads(text)
            pois = resp.get("data", {}).get("poi_list", resp.get("pois", []))

            for i, poi in enumerate(pois):
                if self.poi_id and poi.get("id") == self.poi_id:
                    data.rating = float(poi.get("rating", 0))
                    data.comment_count = int(poi.get("comment_num", 0))
                    data.store_rank = i + 1
                    break
                elif self.config.store.store_name in poi.get("name", ""):
                    data.rating = float(poi.get("rating", 0))
                    data.comment_count = int(poi.get("comment_num", 0))
                    data.store_rank = i + 1
                    break

        except (json.JSONDecodeError, Exception) as e:
            data.error_message = str(e)

        return data.to_dict()
