import time
import logging
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from functools import lru_cache

import httpx

logger = logging.getLogger("notification-dispatcher")


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Channel(Enum):
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"


SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


@dataclass
class RoutingRule:
    min_severity: Severity
    categories: list[str] = field(default_factory=lambda: ["*"])
    channels: list[Channel] = field(default_factory=list)


@dataclass
class RateLimitState:
    max_per_window: int
    window_seconds: float
    timestamps: list[float] = field(default_factory=list)

    def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        if len(self.timestamps) >= self.max_per_window:
            return False
        self.timestamps.append(now)
        return True


@dataclass
class Incident:
    id: str
    title: str
    severity: Severity
    category: str
    description: str = ""
    metadata: dict = field(default_factory=dict)


class NotificationDispatcher:
    def __init__(self, config: dict):
        self.config = config
        self.client = httpx.Client(timeout=10.0)
        self.routing_rules = self._parse_routing_rules(config.get("routing_rules", []))
        self.rate_limits: dict[str, RateLimitState] = {}
        for chan, rl in config.get("rate_limits", {}).items():
            self.rate_limits[chan] = RateLimitState(
                max_per_window=rl["max_per_window"],
                window_seconds=rl["window_seconds"],
            )

    def _parse_routing_rules(self, rules: list[dict]) -> list[RoutingRule]:
        parsed = []
        for r in rules:
            parsed.append(RoutingRule(
                min_severity=Severity(r["min_severity"]),
                categories=r.get("categories", ["*"]),
                channels=[Channel(c) for c in r["channels"]],
            ))
        return parsed

    def _resolve_channels(self, incident: Incident) -> list[Channel]:
        channels: set[Channel] = set()
        sev_rank = SEVERITY_ORDER[incident.severity]
        for rule in self.routing_rules:
            rule_rank = SEVERITY_ORDER[rule.min_severity]
            if sev_rank > rule_rank:
                continue
            if "*" not in rule.categories and incident.category not in rule.categories:
                continue
            channels.update(rule.channels)
        return sorted(channels, key=lambda c: c.value)

    def _check_rate_limit(self, channel: Channel) -> bool:
        rl = self.rate_limits.get(channel.value)
        if rl is None:
            return True
        allowed = rl.allow()
        if not allowed:
            logger.warning("Rate limited on channel %s", channel.value)
        return allowed

    def dispatch(self, incident: Incident) -> dict[str, bool]:
        channels = self._resolve_channels(incident)
        results: dict[str, bool] = {}
        for channel in channels:
            if not self._check_rate_limit(channel):
                results[channel.value] = False
                continue
            try:
                if channel == Channel.SLACK:
                    ok = self._send_slack(incident)
                elif channel == Channel.PAGERDUTY:
                    ok = self._send_pagerduty(incident)
                elif channel == Channel.EMAIL:
                    ok = self._send_email(incident)
                else:
                    ok = False
                results[channel.value] = ok
            except Exception as exc:
                logger.exception("Failed to dispatch %s: %s", channel.value, exc)
                results[channel.value] = False
        return results

    def _send_slack(self, incident: Incident) -> bool:
        webhook_url = self.config["channels"]["slack"]["webhook_url"]
        sev_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}
        emoji = sev_emoji.get(incident.severity.value, "⚪")
        payload = {
            "text": f"{emoji} [{incident.severity.value.upper()}] {incident.title}",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn",
                 "text": f"*{emoji} Incident {incident.id}*\n*Severity:* {incident.severity.value}\n*Category:* {incident.category}\n*Description:* {incident.description}"}},
            ],
        }
        resp = self.client.post(webhook_url, json=payload)
        resp.raise_for_status()
        logger.info("Slack notification sent for incident %s", incident.id)
        return True

    def _send_pagerduty(self, incident: Incident) -> bool:
        cfg = self.config["channels"]["pagerduty"]
        routing_key = cfg["routing_key"]
        pd_severity_map = {"critical": "critical", "high": "high", "medium": "warning", "low": "info", "info": "info"}
        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": incident.title,
                "severity": pd_severity_map.get(incident.severity.value, "info"),
                "source": incident.metadata.get("source", "incident-triage"),
                "component": incident.category,
                "custom_details": {"incident_id": incident.id, "description": incident.description},
            },
        }
        resp = self.client.post("https://events.pagerduty.com/v2/enqueue", json=payload)
        resp.raise_for_status()
        logger.info("PagerDuty alert sent for incident %s", incident.id)
        return True

    def _send_email(self, incident: Incident) -> bool:
        cfg = self.config["channels"]["email"]
        api_url = cfg["api_url"]
        recipients = cfg.get("recipients", [])
        payload = {
            "to": recipients,
            "subject": f"[{incident.severity.value.upper()}] {incident.title}",
            "body": f"Incident ID: {incident.id}\nSeverity: {incident.severity.value}\nCategory: {incident.category}\n\n{incident.description}",
        }
        resp = self.client.post(api_url, json=payload, headers=cfg.get("headers", {}))
        resp.raise_for_status()
        logger.info("Email notification sent for incident %s", incident.id)
        return True

    def close(self):
        self.client.close()