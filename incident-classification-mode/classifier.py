from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import ClassificationConfig, DEFAULT_CONFIG


@dataclass
class Incident:
    """Raw incident coming from the rules engine / deduplicator."""
    id: str
    title: str
    key: str                          # dedup/correlation key (e.g. "host_cpu_high")
    score: float = 0.0                # 0-100 composite urgency score
    affected_ratio: float = 0.0       # fraction of fleet/tenants impacted
    tags: Dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass
class TriageLabels:
    """Structured output of the classifier."""
    incident_id: str
    severity: str        # P1 | P2 | P3 | P4
    category: str        # infra | app | security | network
    confidence: float    # 0.0-1.0 how certain the classification is
    matched_rules: List[str] = field(default_factory=list)
    original_score: float = 0.0
    original_ratio: float = 0.0


class IncidentClassifier:
    """Rule-based classifier that assigns severity and category to incidents."""

    def __init__(self, config: Optional[ClassificationConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._severity_rules = sorted(
            self.config.severity_rules, key=lambda r: r.priority
        )

    # ── public API ────────────────────────────────────────────────────

    def classify(self, incident: Incident) -> TriageLabels:
        severity, sev_conf, sev_rule = self._classify_severity(incident)
        category, cat_conf, cat_rule = self._classify_category(incident)
        confidence = round((sev_conf + cat_conf) / 2, 3)

        matched = []
        if sev_rule:
            matched.append(f"severity:{sev_rule}")
        if cat_rule:
            matched.append(f"category:{cat_rule}")

        return TriageLabels(
            incident_id=incident.id,
            severity=severity,
            category=category,
            confidence=confidence,
            matched_rules=matched,
            original_score=incident.score,
            original_ratio=incident.affected_ratio,
        )

    def classify_batch(self, incidents: List[Incident]) -> List[TriageLabels]:
        return [self.classify(inc) for inc in incidents]

    # ── severity logic ────────────────────────────────────────────────

    def _classify_severity(self, inc: Incident):
        text = f"{inc.title} {inc.description}".lower()
        best_sev = self.config.default_severity
        best_conf = 0.0
        best_rule = ""

        for rule in self._severity_rules:
            score_match = inc.score >= rule.min_score
            ratio_match = inc.affected_ratio >= rule.affected_ratio_min
            kw_match = any(kw in text for kw in rule.keywords)
            tag_match = any(
                v.lower() in text for v in inc.tags.values()
            )

            if score_match and ratio_match:
                conf = self._severity_confidence(inc, rule, kw_match or tag_match)
                if conf > best_conf:
                    best_sev = rule.severity
                    best_conf = conf
                    best_rule = rule.severity
            elif kw_match or tag_match:
                conf = 0.55  # keyword-only is moderate confidence
                if conf > best_conf:
                    best_sev = rule.severity
                    best_conf = conf
                    best_rule = rule.severity

        return best_sev, best_conf, best_rule

    @staticmethod
    def _severity_confidence(inc: Incident, rule, reinforced: bool) -> float:
        base = 0.65
        if inc.score >= rule.min_score + 20:
            base += 0.15
        if inc.affected_ratio >= rule.affected_ratio_min + 0.1:
            base += 0.1
        if reinforced:
            base += 0.1
        return min(round(base, 3), 1.0)

    # ── category logic ────────────────────────────────────────────────

    def _classify_category(self, inc: Incident):
        text = f"{inc.title} {inc.description} {inc.key}".lower()
        best_cat = self.config.default_category
        best_conf = 0.0
        best_rule = ""

        for rule in self.config.category_rules:
            kw_hits = sum(1 for kw in rule.keywords if kw in text)
            prefix_hits = sum(
                1 for p in rule.key_prefixes if inc.key.lower().startswith(p)
            )
            tag_hits = sum(
                1 for v in inc.tags.values() if v.lower() in rule.keywords
            )
            total = kw_hits + prefix_hits + tag_hits
            if total > 0:
                conf = min(0.5 + 0.2 * total, 1.0)
                if conf > best_conf:
                    best_cat = rule.category
                    best_conf = round(conf, 3)
                    best_rule = rule.category

        return best_cat, best_conf, best_rule


# ── convenience ────────────────────────────────────────────────────────

def classify_incident(incident: Incident,
                      config: Optional[ClassificationConfig] = None) -> TriageLabels:
    """One-shot helper for callers that don't want to manage a classifier instance."""
    return IncidentClassifier(config).classify(incident)