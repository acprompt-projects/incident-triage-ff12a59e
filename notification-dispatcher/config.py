from dispatcher import NotificationDispatcher, Severity, Incident

DEFAULT_CONFIG = {
    "channels": {
        "slack": {
            "webhook_url": "https://hooks.slack.com/services/T00/B00/xxx",
        },
        "pagerduty": {
            "routing_key": "pd-routing-key-placeholder",
        },
        "email": {
            "api_url": "https://api.example.com/v1/email",
            "recipients": ["oncall@example.com"],
            "headers": {"Authorization": "Bearer token-placeholder"},
        },
    },
    "routing_rules": [
        {"min_severity": "critical", "categories": ["*"], "channels": ["slack", "pagerduty", "email"]},
        {"min_severity": "high", "categories": ["infrastructure", "security"], "channels": ["slack", "pagerduty"]},
        {"min_severity": "high", "categories": ["*"], "channels": ["slack", "email"]},
        {"min_severity": "medium", "categories": ["*"], "channels": ["slack"]},
        {"min_severity": "low", "categories": ["security"], "channels": ["slack"]},
    ],
    "rate_limits": {
        "slack": {"max_per_window": 20, "window_seconds": 60},
        "pagerduty": {"max_per_window": 10, "window_seconds": 60},
        "email": {"max_per_window": 30, "window_seconds": 60},
    },
}


def create_dispatcher(config: dict | None = None) -> NotificationDispatcher:
    return NotificationDispatcher(config or DEFAULT_CONFIG)


__all__ = ["DEFAULT_CONFIG", "create_dispatcher", "NotificationDispatcher", "Severity", "Incident"]