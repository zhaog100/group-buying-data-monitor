"""
基础抓取器 - 团购+外卖实时数据监测系统
提供反爬策略、代理池、重试机制等通用能力
"""
import asyncio
import random
import time
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx

from .config import MonitorConfig, Platform

logger = logging.getLogger(__name__)


class AntiDetect:
    """反检测工具集"""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]

    @classmethod
    def random_ua(cls) -> str:
        return random.choice(cls.USER_AGENTS)

    @classmethod
    def random_delay(cls, min_s: float = 1.0, max_s: float = 3.0) -> float:
        return random.uniform(min_s, max_s)

    @classmethod
    def fingerprint_headers(cls) -> Dict[str, str]:
        """生成浏览器指纹 headers"""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }


class BaseScraper(ABC):
    """抓取器基类"""

    def __init__(self, platform: Platform, config: MonitorConfig):
        self.platform = platform
        self.config = config
        self.anti_detect = AntiDetect()
        self._client: Optional[httpx.AsyncClient] = None
        self.session_id = hashlib.md5(
            f"{platform.value}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            proxy = None
            if self.config.proxy.enabled and self.config.proxy.https:
                proxy = self.config.proxy.https
            elif self.config.proxy.enabled and self.config.proxy.http:
                proxy = self.config.proxy.http

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.request_timeout),
                proxy=proxy,
                headers=self._build_headers(),
                follow_redirects=True,
                verify=False,
            )
        return self._client

    def _build_headers(self) -> Dict[str, str]:
        headers = self.anti_detect.fingerprint_headers()
        headers["User-Agent"] = self.anti_detect.random_ua()
        return headers

    async def _request_with_retry(
        self,
        url: str,
        method: str = "GET",
        **kwargs,
    ) -> Optional[httpx.Response]:
        """带重试的请求"""
        client = await self._get_client()
        last_error = None

        for attempt in range(self.config.retry_max):
            try:
                delay = self.anti_detect.random_delay()
                await asyncio.sleep(delay)

                # 旋转 UA
                client.headers["User-Agent"] = self.anti_detect.random_ua()

                response = await getattr(client, method.lower())(url, **kwargs)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "30"))
                    logger.warning(f"[{self.platform.value}] Rate limited, retry after {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif response.status_code == 403:
                    logger.warning(f"[{self.platform.value}] Blocked (403), rotating session")
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    logger.warning(f"[{self.platform.value}] HTTP {response.status_code}")

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(f"[{self.platform.value}] Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        logger.error(f"[{self.platform.value}] All retries exhausted: {last_error}")
        return None

    @abstractmethod
    async def scrape(self) -> Dict[str, Any]:
        """子类实现具体抓取逻辑"""
        ...

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
