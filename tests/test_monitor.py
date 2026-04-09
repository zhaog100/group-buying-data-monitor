"""
单元测试 - 团购+外卖实时数据监测系统
"""
import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# 添加 src 到路径
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import MonitorConfig, Platform, StoreConfig, FeishuConfig
from src.models import ReviewData, DeliveryData, MonitorReport
from src.feishu import FeishuNotifier
from src.scheduler import MonitorScheduler


class TestModels:
    """数据模型测试"""

    def test_review_data_creation(self):
        data = ReviewData(
            platform="dianping",
            scraped_at="2026-04-10T10:00:00",
            comment_count=100,
            rating=4.5,
            store_rank=3,
        )
        assert data.platform == "dianping"
        assert data.comment_count == 100
        assert data.rating == 4.5
        assert data.store_rank == 3
        assert data.status == "success"

    def test_review_data_to_dict(self):
        data = ReviewData(platform="gaode", scraped_at="2026-04-10T10:00:00", rating=4.8)
        d = data.to_dict()
        assert d["platform"] == "gaode"
        assert d["rating"] == 4.8

    def test_review_data_to_json(self):
        data = ReviewData(platform="douyin", scraped_at="2026-04-10T10:00:00")
        j = data.to_json()
        parsed = json.loads(j)
        assert parsed["platform"] == "douyin"

    def test_delivery_data_creation(self):
        data = DeliveryData(
            platform="meituan",
            scraped_at="2026-04-10T10:30:00",
            order_count=500,
            store_rating=4.7,
            district_rank=5,
        )
        assert data.platform == "meituan"
        assert data.order_count == 500
        assert data.district_rank == 5

    def test_monitor_report(self):
        report = MonitorReport(
            report_id="test001",
            generated_at="2026-04-10 10:00:00",
            store_name="测试门店",
        )
        report.add_review(ReviewData(platform="dianping", scraped_at="2026-04-10T10:00:00", rating=4.5))
        report.add_delivery(DeliveryData(platform="meituan", scraped_at="2026-04-10T10:00:00", order_count=100))

        summary = report.generate_summary()
        assert summary["total_platforms"] == 2
        assert summary["success_count"] == 2
        assert summary["accuracy_rate"] == 1.0

    def test_monitor_report_with_failures(self):
        report = MonitorReport(
            report_id="test002",
            generated_at="2026-04-10 10:00:00",
            store_name="测试门店",
        )
        report.add_review(ReviewData(platform="dianping", scraped_at="2026-04-10T10:00:00", rating=4.5))
        report.add_review(ReviewData(platform="gaode", scraped_at="2026-04-10T10:00:00", status="failed", error_message="超时"))
        report.add_delivery(DeliveryData(platform="meituan", scraped_at="2026-04-10T10:00:00", order_count=100))

        summary = report.generate_summary()
        assert summary["total_platforms"] == 3
        assert summary["success_count"] == 2
        assert summary["fail_count"] == 1
        assert abs(summary["accuracy_rate"] - 0.667) < 0.01


class TestConfig:
    """配置测试"""

    def test_default_config(self):
        config = MonitorConfig()
        assert config.retry_max == 3
        assert config.accuracy_threshold == 0.98
        assert config.request_timeout == 30.0

    def test_store_config(self):
        config = StoreConfig(store_name="测试门店", city="北京")
        assert config.store_name == "测试门店"
        assert config.city == "北京"


class TestFeishuNotifier:
    """飞书通知测试"""

    def test_build_card(self):
        config = FeishuConfig(webhook_url="https://test.webhook.url")
        notifier = FeishuNotifier(config)

        report = MonitorReport(
            report_id="card001",
            generated_at="2026-04-10 10:00:00",
            store_name="测试门店",
        )
        report.add_review(ReviewData(platform="dianping", scraped_at="2026-04-10T10:00:00", rating=4.5, comment_count=100))
        report.add_delivery(DeliveryData(platform="meituan", scraped_at="2026-04-10T10:00:00", order_count=200, store_rating=4.7))

        card = notifier._build_card(report)
        assert "header" in card
        assert "elements" in card
        assert len(card["elements"]) >= 3  # header + data + footer

    @pytest.mark.asyncio
    async def test_send_webhook_no_url(self):
        config = FeishuConfig(webhook_url="")
        notifier = FeishuNotifier(config)
        report = MonitorReport(
            report_id="test",
            generated_at="2026-04-10 10:00:00",
            store_name="测试",
        )
        result = await notifier.send_webhook(report)
        assert result is False
        await notifier.close()


class TestScheduler:
    """调度器测试"""

    def test_check_alerts_rating(self):
        config = MonitorConfig()
        scheduler = MonitorScheduler(config)

        report = MonitorReport(
            report_id="alert001",
            generated_at="2026-04-10 10:00:00",
            store_name="测试",
        )
        report.add_review(ReviewData(platform="dianping", scraped_at="2026-04-10T10:00:00", rating=3.5))

        alerts = scheduler._check_alerts(report)
        assert any("评分低于4.0" in a["message"] for a in alerts)

    def test_check_alerts_failure(self):
        config = MonitorConfig()
        scheduler = MonitorScheduler(config)

        report = MonitorReport(
            report_id="alert002",
            generated_at="2026-04-10 10:00:00",
            store_name="测试",
        )
        report.add_review(ReviewData(platform="gaode", scraped_at="2026-04-10T10:00:00", status="failed", error_message="超时"))

        alerts = scheduler._check_alerts(report)
        assert any("数据抓取失败" in a["message"] for a in alerts)

    def test_check_alerts_high_rank(self):
        config = MonitorConfig()
        scheduler = MonitorScheduler(config)

        report = MonitorReport(
            report_id="alert003",
            generated_at="2026-04-10 10:00:00",
            store_name="测试",
        )
        report.add_delivery(DeliveryData(platform="meituan", scraped_at="2026-04-10T10:00:00", district_rank=25))

        alerts = scheduler._check_alerts(report)
        assert any("排名较低" in a["message"] for a in alerts)


class TestScrapers:
    """抓取器基础测试"""

    def test_dianping_missing_id(self):
        """测试未配置门店ID时的处理"""
        config = MonitorConfig()
        from src.scraper_review import DianpingScraper
        scraper = DianpingScraper(config)
        assert scraper.shop_id == ""

    def test_meituan_missing_id(self):
        config = MonitorConfig()
        from src.scraper_delivery import MeituanScraper
        scraper = MeituanScraper(config)
        assert scraper.shop_id == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
