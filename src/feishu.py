"""
飞书推送模块 - 团购+外卖实时数据监测系统
支持 Webhook 和 App 两种模式
"""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import httpx

from .config import FeishuConfig
from .models import MonitorReport

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书消息推送"""

    def __init__(self, config: FeishuConfig):
        self.config = config
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_webhook(self, report: MonitorReport) -> bool:
        """通过 Webhook 发送消息卡片"""
        if not self.config.webhook_url:
            logger.error("[feishu] Webhook URL 未配置")
            return False

        card = self._build_card(report)

        try:
            response = await self._client.post(
                self.config.webhook_url,
                json={"msg_type": "interactive", "card": card},
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info("[feishu] 消息发送成功")
                    return True
                else:
                    logger.error(f"[feishu] 发送失败: {result}")
            else:
                logger.error(f"[feishu] HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"[feishu] 发送异常: {e}")

        return False

    async def send_to_chat(self, report: MonitorReport, chat_id: str) -> bool:
        """通过 App 模式发送到群聊"""
        if not self.config.app_id or not self.config.app_secret:
            logger.error("[feishu] App ID/Secret 未配置")
            return False

        token = await self._get_tenant_token()
        if not token:
            return False

        card = self._build_card(report)

        try:
            response = await self._client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={"receive_id_type": "chat_id"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "interactive",
                    "content": json.dumps({"config": {"wide_mode": True}, **card}),
                },
            )
            result = response.json()
            return result.get("code") == 0
        except Exception as e:
            logger.error(f"[feishu] App发送异常: {e}")
            return False

    async def _get_tenant_token(self) -> Optional[str]:
        """获取 tenant_access_token"""
        try:
            response = await self._client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.config.app_id,
                    "app_secret": self.config.app_secret,
                },
            )
            result = response.json()
            return result.get("tenant_access_token")
        except Exception as e:
            logger.error(f"[feishu] 获取token失败: {e}")
            return None

    def _build_card(self, report: MonitorReport) -> Dict[str, Any]:
        """构建飞书消息卡片"""
        summary = report.generate_summary()
        elements = []

        # 头部
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📊 {report.store_name} - 数据监测报告**\n"
                           f"⏰ {report.generated_at} | "
                           f"成功率: {summary.get('accuracy_rate', 0):.0%}",
            },
        })
        elements.append({"tag": "hr"})

        # 评价平台数据
        if report.review_data:
            review_md = "**🔍 评价平台数据**\n"
            for item in report.review_data:
                platform = item.get("platform", "?")
                status = item.get("status", "?")
                icon = "✅" if status == "success" else "⚠️" if status == "partial" else "❌"

                line = f"{icon} **{platform.upper()}** "
                if item.get("rating"):
                    line += f"| 评分: {item['rating']} "
                if item.get("comment_count"):
                    line += f"| 评论: {item['comment_count']} "
                if item.get("store_rank"):
                    line += f"| 排名: #{item['store_rank']} "
                if item.get("consumer_count"):
                    line += f"| 消费人数: {item['consumer_count']} "
                if item.get("return_rate"):
                    line += f"| 回头率: {item['return_rate']}% "
                review_md += line + "\n"

            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": review_md},
            })

        # 外卖平台数据
        if report.delivery_data:
            delivery_md = "**🛵 外卖平台数据**\n"
            for item in report.delivery_data:
                platform = item.get("platform", "?")
                status = item.get("status", "?")
                icon = "✅" if status == "success" else "⚠️" if status == "partial" else "❌"

                line = f"{icon} **{platform.upper()}** "
                if item.get("store_rating"):
                    line += f"| 评分: {item['store_rating']} "
                if item.get("order_count"):
                    line += f"| 月售: {item['order_count']} "
                if item.get("district_rank"):
                    line += f"| 商圈排名: #{item['district_rank']} "
                if item.get("conversion_rate"):
                    line += f"| 转化率: {item['conversion_rate']}% "
                if item.get("avg_delivery_time"):
                    line += f"| 配送: {item['avg_delivery_time']}min "
                delivery_md += line + "\n"

            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": delivery_md},
            })

        # 告警
        if report.alerts:
            alert_md = "**🚨 告警信息**\n"
            for alert in report.alerts:
                alert_md += f"⚠️ {alert.get('level', 'WARN')}: {alert.get('message', '')}\n"
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": alert_md},
            })

        # 摘要
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"报告ID: {report.report_id} | 平台数: {summary.get('total_platforms', 0)} | 成功: {summary.get('success_count', 0)} | 失败: {summary.get('fail_count', 0)}",
                }
            ],
        })

        return {
            "header": {
                "title": {"tag": "plain_text", "content": "📊 团购+外卖数据监测"},
                "template": "blue",
            },
            "elements": elements,
        }

    async def close(self):
        await self._client.aclose()
