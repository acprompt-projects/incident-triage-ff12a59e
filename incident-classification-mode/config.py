from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class SeverityRule:
    """A single rule mapping signal thresholds to a severity level."""
    severity: str
    keywords: List[str] = field(default_factory=list)
    min_score: float = 0.0
    affected_ratio_min: float = 0.0
    priority: int = 0  # lower = evaluated first

@dataclass
class CategoryRule:
    """Rule mapping keywords/prefixes to an incident category."""
    category: str
    keywords: List[str] = field(default_factory=list)
    key_prefixes: List[str] = field(default_factory=list)

@dataclass
class ClassificationConfig:
    severity_rules: List[SeverityRule]
    category_rules: List[CategoryRule]
    default_severity: str = "P4"
    default_category: str = "app"

DEFAULT_CONFIG = ClassificationConfig(
    severity_rules=[
        SeverityRule(severity="P1", priority=0,
                     keywords=["outage", "down", "data_loss", "breach", "compromised"],
                     min_score=90, affected_ratio_min=0.5),
        SeverityRule(severity="P2", priority=1,
                     keywords=["degraded", "timeout", "error_rate_high", "unauthorized"],
                     min_score=70, affected_ratio_min=0.25),
        SeverityRule(severity="P3", priority=2,
                     keywords=["warning", "slow", "retry", "flapping"],
                     min_score=40, affected_ratio_min=0.05),
        SeverityRule(severity="P4", priority=3,
                     keywords=["info", "notice", "heartbeat"],
                     min_score=0, affected_ratio_min=0.0),
    ],
    category_rules=[
        CategoryRule(category="security",
                     keywords=["breach", "compromised", "unauthorized", "auth_fail",
                               "malware", "intrusion", "cve", "vulnerability"],
                     key_prefixes=["sec_", "auth_", "vuln_"]),
        CategoryRule(category="infra",
                     keywords=["cpu", "memory", "disk", "host_down", "vm",
                               "container", "pod", "node", "provisioner"],
                     key_prefixes=["infra_", "host_", "node_"]),
        CategoryRule(category="network",
                     keywords=["latency", "packet_loss", "dns", "connection_refused",
                               "timeout", "link_down", "bandwidth"],
                     key_prefixes=["net_", "dns_", "link_"]),
        CategoryRule(category="app",
                     keywords=["error", "exception", "crash", "deploy", "rollback",
                               "5xx", "4xx", "queue_backlog"],
                     key_prefixes=["app_", "svc_", "job_"]),
    ],
)