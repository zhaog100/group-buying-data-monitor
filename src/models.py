"""
数据模型 - 团购+外卖实时数据监测系统
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class PlatformStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"


@dataclass
class ReviewData:
    """评价平台数据"""
    platform: str
    scraped_at: str
    comment_count: Optional[int] = None
    rating: Optional[float] = None
    review_content: Optional[List[Dict[str, Any]]] = None
    store_rank: Optional[int] = None
    user_level: Optional[str] = None
    consumer_count: Optional[int] = None
    return_rate: Optional[float] = None
    ranking: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None
    status: str = PlatformStatus.SUCCESS.value
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class DeliveryData:
    """外卖平台数据"""
    platform: str
    scraped_at: str
    order_count: Optional[int] = None
    conversion_rate: Optional[float] = None
    district_rank: Optional[int] = None
    store_rating: Optional[float] = None
    sales_volume: Optional[int] = None
    avg_delivery_time: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None
    status: str = PlatformStatus.SUCCESS.value
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class MonitorReport:
    """监测报告"""
    report_id: str
    generated_at: str
    store_name: str
    review_data: List[Dict[str, Any]] = field(default_factory=list)
    delivery_data: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, str]] = field(default_factory=list)

    def add_review(self, data: ReviewData):
        self.review_data.append(data.to_dict())

    def add_delivery(self, data: DeliveryData):
        self.delivery_data.append(data.to_dict())

    def generate_summary(self) -> Dict[str, Any]:
        """生成数据摘要"""
        success_review = sum(1 for d in self.review_data if d.get("status") == "success")
        success_delivery = sum(1 for d in self.delivery_data if d.get("status") == "success")

        self.summary = {
            "total_platforms": len(self.review_data) + len(self.delivery_data),
            "success_count": success_review + success_delivery,
            "fail_count": (len(self.review_data) - success_review) + (len(self.delivery_data) - success_delivery),
            "accuracy_rate": (success_review + success_delivery) / max(len(self.review_data) + len(self.delivery_data), 1),
            "review_platforms": len(self.review_data),
            "delivery_platforms": len(self.delivery_data),
        }
        return self.summary

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
