# -*- coding: utf-8 -*-
"""
钉钉 Webhook 发送提醒服务

通过自定义机器人 Webhook 发送钉钉群消息
文档: https://open.dingtalk.com/document/orgapp/custom-robots-send-group-messages
"""
import hashlib
import hmac
import base64
import logging
import time
import urllib.parse
from typing import Optional

import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes, format_dingtalk_markdown

logger = logging.getLogger(__name__)


class DingtalkSender:

    def __init__(self, config: Config):
        self._dingtalk_webhook_url: Optional[str] = getattr(config, 'dingtalk_webhook_url', None)
        self._dingtalk_webhook_secret: Optional[str] = getattr(config, 'dingtalk_webhook_secret', None)
        self._dingtalk_max_bytes: int = getattr(config, 'dingtalk_max_bytes', 20000)
        self._webhook_verify_ssl: bool = getattr(config, 'webhook_verify_ssl', True)

    def _sign_url(self, url: str) -> str:
        """加签：如果配置了 secret，在 URL 上追加 timestamp + sign"""
        if not self._dingtalk_webhook_secret:
            return url
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._dingtalk_webhook_secret}"
        hmac_code = hmac.new(
            self._dingtalk_webhook_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{url}&timestamp={timestamp}&sign={sign}"

    def send_to_dingtalk(self, content: str) -> bool:
        """
        推送 Markdown 消息到钉钉群机器人

        钉钉单条消息限制约 20KB，超长自动分批发送

        Args:
            content: Markdown 格式消息内容

        Returns:
            是否发送成功
        """
        if not self._dingtalk_webhook_url:
            logger.warning("钉钉 Webhook 未配置，跳过推送")
            return False

        content = format_dingtalk_markdown(content)
        chunks = chunk_content_by_max_bytes(content, self._dingtalk_max_bytes)
        total = len(chunks)
        success = True

        for i, chunk in enumerate(chunks):
            url = self._sign_url(self._dingtalk_webhook_url)
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "saima股票分析日报",
                    "text": chunk,
                },
            }
            try:
                resp = requests.post(url, json=payload, timeout=15, verify=self._webhook_verify_ssl)
                data = resp.json()
                if data.get("errcode") == 0:
                    logger.info(f"钉钉推送成功 ({i+1}/{total})")
                else:
                    logger.error(f"钉钉推送失败: {data}")
                    success = False
            except Exception as e:
                logger.error(f"钉钉推送异常: {e}")
                success = False

            if i < total - 1:
                time.sleep(1)

        return success
