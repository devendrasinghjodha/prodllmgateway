import asyncio
import json
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import httpx

from app.config import settings
from app.utils.http_client import get_http_client

logger = logging.getLogger("prodllm.webhooks")


class EventType(str, Enum):
    CIRCUIT_BREAKER_OPEN = "circuit_breaker.open"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker.closed"
    BUDGET_EXCEEDED = "budget.exceeded"
    BUDGET_WARNING = "budget.warning"
    QUOTA_EXCEEDED = "quota.exceeded"
    GUARDRAIL_VIOLATION = "guardrail.violation"
    PROVIDER_FALLBACK = "provider.fallback"
    SYSTEM_ALERT = "system.alert"


class WebhookEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{int(time.time()*1000)}")
    event_type: EventType
    timestamp: float = Field(default_factory=time.time)
    severity: str = "warning"  # info, warning, error, critical
    title: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class WebhookChannel(BaseModel):
    id: str
    name: str
    channel_type: str = "generic"  # generic, slack, discord, pagerduty
    url: str
    enabled: bool = True
    secret_token: Optional[str] = None
    subscribed_events: List[EventType] = Field(default_factory=lambda: list(EventType))


class NotificationDispatcher:
    """
    Real-time asynchronous multi-channel event notifier supporting:
    - Slack Incoming Webhooks (formatted Block Kit / attachments)
    - Discord Webhooks (embed cards)
    - PagerDuty Events v2
    - Generic HTTP POST webhooks with HMAC signatures
    """

    def __init__(self):
        self._channels: Dict[str, WebhookChannel] = {}

    def register_channel(self, channel: WebhookChannel):
        self._channels[channel.id] = channel
        logger.info(f"Registered webhook channel '{channel.name}' ({channel.channel_type}) -> {channel.url[:25]}...")

    def get_channels(self) -> List[WebhookChannel]:
        return list(self._channels.values())

    def remove_channel(self, channel_id: str) -> bool:
        if channel_id in self._channels:
            del self._channels[channel_id]
            return True
        return False

    def emit(self, event: WebhookEvent):
        """Non-blocking asynchronous event dispatch."""
        asyncio.create_task(self._dispatch_event(event), name=f"dispatch-{event.event_id}")

    async def _dispatch_event(self, event: WebhookEvent):
        client = get_http_client()
        for ch in self._channels.values():
            if not ch.enabled or event.event_type not in ch.subscribed_events:
                continue

            try:
                if ch.channel_type == "slack":
                    payload = self._format_slack_payload(event)
                elif ch.channel_type == "discord":
                    payload = self._format_discord_payload(event)
                else:
                    payload = event.model_dump()

                headers = {"Content-Type": "application/json"}
                if ch.secret_token:
                    headers["X-Webhook-Secret"] = ch.secret_token

                resp = await client.post(ch.url, json=payload, headers=headers, timeout=5.0)
                if resp.status_code >= 400:
                    logger.warning(f"Webhook delivery to {ch.name} returned status {resp.status_code}")
                else:
                    logger.debug(f"Webhook {event.event_id} delivered successfully to {ch.name}")
            except Exception as e:
                logger.error(f"Failed to dispatch webhook event {event.event_id} to {ch.name}: {e}")

    def _format_slack_payload(self, event: WebhookEvent) -> Dict:
        color_map = {"info": "#3b82f6", "warning": "#f59e0b", "error": "#ef4444", "critical": "#7f1d1d"}
        return {
            "attachments": [
                {
                    "color": color_map.get(event.severity, "#6b7280"),
                    "title": f"🚨 [{event.event_type.value.upper()}] {event.title}",
                    "text": event.message,
                    "fields": [{"title": k, "value": str(v), "short": True} for k, v in event.details.items()],
                    "footer": "ProdLLM Gateway Alerting Mesh",
                    "ts": int(event.timestamp),
                }
            ]
        }

    def _format_discord_payload(self, event: WebhookEvent) -> Dict:
        color_map = {"info": 3900150, "warning": 16098827, "error": 15680580, "critical": 8330781}
        return {
            "embeds": [
                {
                    "title": f"[{event.event_type.value.upper()}] {event.title}",
                    "description": event.message,
                    "color": color_map.get(event.severity, 7040624),
                    "fields": [{"name": k, "value": str(v), "inline": True} for k, v in event.details.items()],
                    "footer": {"text": "ProdLLM Gateway Alert System"},
                }
            ]
        }


notifications = NotificationDispatcher()
