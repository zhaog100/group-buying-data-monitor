"""
配置模块 - 团购+外卖实时数据监测系统
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class Platform(Enum):
    DIANPING = "dianping"
    DOUYIN = "douyin"
    GAODE = "gaode"
    MEITUAN = "meituan"
    ELEME = "eleme"
    JD = "jd"


class DataType(Enum):
    REVIEW = "review"      # 评价平台
    DELIVERY = "delivery"   # 外卖平台


@dataclass
class ScrapingTarget:
    """抓取目标配置"""
    platform: Platform
    data_type: DataType
    fields: List[str]
    schedule_cron: str  # cron 表达式
    time_window: Optional[str] = None  # 活跃时间窗口


@dataclass
class FeishuConfig:
    """飞书推送配置"""
    webhook_url: str = os.getenv("FEISHU_WEBHOOK_URL", "")
    app_id: str = os.getenv("FEISHU_APP_ID", "")
    app_secret: str = os.getenv("FEISHU_APP_SECRET", "")


@dataclass
class ProxyConfig:
    """代理配置"""
    enabled: bool = os.getenv("PROXY_ENABLED", "false").lower() == "true"
    http: str = os.getenv("HTTP_PROXY", "")
    https: str = os.getenv("HTTPS_PROXY", "")
    pool_size: int = int(os.getenv("PROXY_POOL_SIZE", "5"))


@dataclass
class StoreConfig:
    """门店配置"""
    store_id: str = os.getenv("STORE_ID", "")
    store_name: str = os.getenv("STORE_NAME", "")
    city: str = os.getenv("STORE_CITY", "")
    district: str = os.getenv("STORE_DISTRICT", "")
    business_district: str = os.getenv("STORE_BUSINESS_DISTRICT", "")
    # 各平台对应ID
    dianping_shop_id: str = os.getenv("DIANPING_SHOP_ID", "")
    douyin_shop_id: str = os.getenv("DOUYIN_SHOP_ID", "")
    gaode_poi_id: str = os.getenv("GAODE_POI_ID", "")
    meituan_shop_id: str = os.getenv("MEITUAN_SHOP_ID", "")
    eleme_shop_id: str = os.getenv("ELEME_SHOP_ID", "")
    jd_shop_id: str = os.getenv("JD_SHOP_ID", "")


@dataclass
class MonitorConfig:
    """监测系统总配置"""
    store: StoreConfig = field(default_factory=StoreConfig)
    feishu: FeishuConfig = field(default_factory=FeishuConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    accuracy_threshold: float = 0.98
    retry_max: int = 3
    retry_delay: float = 5.0
    request_timeout: float = 30.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )


# 评价平台抓取目标配置
REVIEW_PLATFORMS: List[ScrapingTarget] = [
    ScrapingTarget(
        platform=Platform.DIANPING,
        data_type=DataType.REVIEW,
        fields=["comment_count", "rating", "review_content", "store_rank"],
        schedule_cron="0 10,12,14,16,18,20 * * *",
        time_window="10:00-20:00",
    ),
    ScrapingTarget(
        platform=Platform.DOUYIN,
        data_type=DataType.REVIEW,
        fields=["comment_count", "user_level", "rating", "consumer_count"],
        schedule_cron="0 10,12,14,16,18,20 * * *",
        time_window="10:00-20:00",
    ),
    ScrapingTarget(
        platform=Platform.GAODE,
        data_type=DataType.REVIEW,
        fields=["comment_count", "rating", "return_rate", "ranking"],
        schedule_cron="0 10,12,14,16,18,20 * * *",
        time_window="10:00-20:00",
    ),
]

# 外卖平台抓取目标配置
DELIVERY_PLATFORMS: List[ScrapingTarget] = [
    ScrapingTarget(
        platform=Platform.MEITUAN,
        data_type=DataType.DELIVERY,
        fields=["order_count", "conversion_rate", "district_rank", "store_rating"],
        schedule_cron="*/30 10-12,17-19 * * *",
        time_window="10:30-12:30,17:00-19:00",
    ),
    ScrapingTarget(
        platform=Platform.ELEME,
        data_type=DataType.DELIVERY,
        fields=["order_count", "conversion_rate", "district_rank", "store_rating"],
        schedule_cron="*/30 10-12,17-19 * * *",
        time_window="10:30-12:30,17:00-19:00",
    ),
    ScrapingTarget(
        platform=Platform.JD,
        data_type=DataType.DELIVERY,
        fields=["order_count", "conversion_rate", "district_rank", "store_rating"],
        schedule_cron="*/30 10-12,17-19 * * *",
        time_window="10:30-12:30,17:00-19:00",
    ),
]
