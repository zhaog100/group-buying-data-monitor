"""
调度器 - 团购+外卖实时数据监测系统
管理抓取任务的定时执行
"""
import asyncio
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional

from .config import MonitorConfig, REVIEW_PLATFORMS, DELIVERY_PLATFORMS
from .models import MonitorReport
from .scraper_review import DianpingScraper, DouyinScraper, GaodeScraper
from .scraper_delivery import MeituanScraper, ElemeScraper, JDScraper
from .feishu import FeishuNotifier

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """监测调度器"""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self.notifier = FeishuNotifier(config.feishu)
        self._running = False
        self._last_report: Optional[MonitorReport] = None

        # 初始化抓取器
        self.review_scrapers = {
            "dianping": DianpingScraper(config),
            "douyin": DouyinScraper(config),
            "gaode": GaodeScraper(config),
        }
        self.delivery_scrapers = {
            "meituan": MeituanScraper(config),
            "eleme": ElemeScraper(config),
            "jd": JDScraper(config),
        }

    async def run_once(self, include_review: bool = True, include_delivery: bool = True) -> MonitorReport:
        """执行一次完整监测"""
        report_id = hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:8]
        report = MonitorReport(
            report_id=report_id,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            store_name=self.config.store.store_name,
        )

        # 抓取评价平台
        if include_review:
            tasks = []
            for name, scraper in self.review_scrapers.items():
                tasks.append(self._safe_scrape(name, scraper))
            results = await asyncio.gather(*tasks)
            for result in results:
                report.add_review(result)

        # 抓取外卖平台
        if include_delivery:
            tasks = []
            for name, scraper in self.delivery_scrapers.items():
                tasks.append(self._safe_scrape(name, scraper))
            results = await asyncio.gather(*tasks)
            for result in results:
                report.add_delivery(result)

        # 生成告警
        report.alerts = self._check_alerts(report)

        self._last_report = report
        return report

    async def _safe_scrape(self, name: str, scraper) -> Dict[str, Any]:
        """安全执行抓取，捕获异常"""
        try:
            logger.info(f"[scheduler] Scraping {name}...")
            result = await scraper.scrape()
            logger.info(f"[scheduler] {name} done: {result.get('status', '?')}")
            return result
        except Exception as e:
            logger.error(f"[scheduler] {name} failed: {e}")
            return {
                "platform": name,
                "scraped_at": datetime.now().isoformat(),
                "status": "failed",
                "error_message": str(e),
            }

    def _check_alerts(self, report: MonitorReport) -> List[Dict[str, str]]:
        """检查告警条件"""
        alerts = []

        for data in report.review_data + report.delivery_data:
            if data.get("status") == "failed":
                alerts.append({
                    "level": "ERROR",
                    "message": f"{data.get('platform', '?')} 数据抓取失败: {data.get('error_message', '未知错误')}",
                })

            # 评分下降告警
            rating = data.get("rating") or data.get("store_rating")
            if rating and rating < 4.0:
                alerts.append({
                    "level": "WARN",
                    "message": f"{data.get('platform', '?')} 评分低于4.0: {rating}",
                })

            # 排名下降
            rank = data.get("store_rank") or data.get("district_rank")
            if rank and rank > 20:
                alerts.append({
                    "level": "INFO",
                    "message": f"{data.get('platform', '?')} 排名较低: #{rank}",
                })

        return alerts

    async def run_and_notify(self, include_review: bool = True, include_delivery: bool = True) -> MonitorReport:
        """执行监测并推送飞书"""
        report = await self.run_once(include_review, include_delivery)

        # 推送飞书
        sent = await self.notifier.send_webhook(report)
        if not sent:
            logger.warning("[scheduler] 飞书推送失败，报告仅本地保存")

        # 保存报告
        self._save_report(report)

        return report

    def _save_report(self, report: MonitorReport):
        """保存报告到文件"""
        import os
        report_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
        os.makedirs(report_dir, exist_ok=True)

        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(report_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report.to_json())

        logger.info(f"[scheduler] Report saved: {filepath}")

    async def run_scheduled(self):
        """按调度规则持续运行"""
        self._running = True
        logger.info("[scheduler] Started scheduled monitoring")

        while self._running:
            now = datetime.now()
            hour = now.hour
            minute = now.minute

            # 评价平台：10:00-20:00 每2小时
            include_review = False
            if 10 <= hour <= 20 and minute < 5 and hour % 2 == 0:
                include_review = True

            # 外卖平台：午餐 10:30-12:30 / 晚餐 17:00-19:00 每30分钟
            include_delivery = False
            if (10 <= hour <= 12 and minute < 5) or (17 <= hour <= 19 and minute < 5):
                include_delivery = True

            if include_review or include_delivery:
                try:
                    await self.run_and_notify(include_review, include_delivery)
                except Exception as e:
                    logger.error(f"[scheduler] Run failed: {e}")

            # 每5分钟检查一次
            await asyncio.sleep(300)

    def stop(self):
        self._running = False

    async def close(self):
        """关闭所有资源"""
        self.stop()
        for scraper in list(self.review_scrapers.values()) + list(self.delivery_scrapers.values()):
            await scraper.close()
        await self.notifier.close()
