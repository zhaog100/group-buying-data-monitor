#!/usr/bin/env python3
"""
团购+外卖实时数据监测系统 - 主入口

用法:
  python main.py                    # 运行一次完整监测
  python main.py --scheduled        # 按调度规则持续运行
  python main.py --review-only      # 只抓取评价平台
  python main.py --delivery-only    # 只抓取外卖平台
  python main.py --no-notify        # 不推送飞书
"""
import asyncio
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.config import MonitorConfig
from src.scheduler import MonitorScheduler
from src.models import MonitorReport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "monitor.log")),
    ],
)

logger = logging.getLogger("main")


async def main():
    parser = argparse.ArgumentParser(description="团购+外卖实时数据监测系统")
    parser.add_argument("--scheduled", action="store_true", help="按调度规则持续运行")
    parser.add_argument("--review-only", action="store_true", help="只抓取评价平台")
    parser.add_argument("--delivery-only", action="store_true", help="只抓取外卖平台")
    parser.add_argument("--no-notify", action="store_true", help="不推送飞书")
    parser.add_argument("--config", type=str, default=".env", help="配置文件路径")
    args = parser.parse_args()

    # 加载环境变量
    if os.path.exists(args.config):
        from dotenv import load_dotenv
        load_dotenv(args.config)
        logger.info(f"Loaded config from {args.config}")

    config = MonitorConfig()

    # 验证配置
    if not config.store.store_name:
        logger.warning("STORE_NAME 未配置，使用默认值")
        config.store.store_name = "默认门店"

    include_review = not args.delivery_only
    include_delivery = not args.review_only

    scheduler = MonitorScheduler(config)

    try:
        if args.scheduled:
            logger.info("🚀 启动定时监测模式...")
            await scheduler.run_scheduled()
        else:
            logger.info("📊 执行单次监测...")
            if args.no_notify:
                report = await scheduler.run_once(include_review, include_delivery)
            else:
                report = await scheduler.run_and_notify(include_review, include_delivery)

            # 输出报告
            print("\n" + "=" * 60)
            print(f"📊 监测报告 - {report.generated_at}")
            print(f"门店: {report.store_name}")
            print("=" * 60)

            if report.review_data:
                print("\n🔍 评价平台数据:")
                for d in report.review_data:
                    status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(
                        d.get("status", "?"), "?"
                    )
                    print(f"  {status_icon} {d.get('platform', '?').upper()}")
                    for k, v in d.items():
                        if k not in ("platform", "status", "scraped_at", "raw_data", "error_message") and v:
                            print(f"     {k}: {v}")
                    if d.get("error_message"):
                        print(f"     ⚠️ {d['error_message']}")

            if report.delivery_data:
                print("\n🛵 外卖平台数据:")
                for d in report.delivery_data:
                    status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(
                        d.get("status", "?"), "?"
                    )
                    print(f"  {status_icon} {d.get('platform', '?').upper()}")
                    for k, v in d.items():
                        if k not in ("platform", "status", "scraped_at", "raw_data", "error_message") and v:
                            print(f"     {k}: {v}")
                    if d.get("error_message"):
                        print(f"     ⚠️ {d['error_message']}")

            if report.alerts:
                print("\n🚨 告警:")
                for alert in report.alerts:
                    print(f"  {alert.get('level', '?')}: {alert.get('message', '')}")

            summary = report.generate_summary()
            print(f"\n📈 汇总: 成功 {summary['success_count']}/{summary['total_platforms']} "
                  f"准确率 {summary['accuracy_rate']:.0%}")

    except KeyboardInterrupt:
        logger.info("🛑 用户中断")
    finally:
        await scheduler.close()


if __name__ == "__main__":
    asyncio.run(main())
