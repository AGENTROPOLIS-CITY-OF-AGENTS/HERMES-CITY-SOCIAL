"""Deterministic risk classification (B3).

Mirrors policies/risk-levels.yaml bands and signals. The policy test suite
asserts these defaults match the YAML (single source of truth).
"""

BANDS = {
    "low": (0, 24),
    "moderate": (25, 49),
    "high": (50, 74),
    "critical": (75, 100),
}

CREDENTIAL_KEYS = {
    "token", "secret", "password", "authorization", "cookie",
    "api_key", "apikey", "bearer", "client_secret",
}
INSTRUCTION_SIGNALS = (
    "ignore previous", "ignore all previous", "system prompt",
    "you are now", "developer instruction", "disregard",
)


def level_for_score(score):
    for level, (lo, hi) in BANDS.items():
        if lo <= score <= hi:
            return level
    return "critical"


def score_content(content, invalid_media=False, oversized=False):
    """Deterministic risk score (0-100) from content signals."""
    text = ""
    if isinstance(content, dict):
        for value in content.values():
            if isinstance(value, str):
                text += value + " "
    elif isinstance(content, str):
        text = content

    score = 0
    lowered = text.lower()
    if "http://" in lowered or "https://" in lowered:
        score += 20
    if "javascript:" in lowered:
        score += 35
    for signal in INSTRUCTION_SIGNALS:
        if signal in lowered:
            score += 25
            break
    for key in CREDENTIAL_KEYS:
        if isinstance(content, dict) and key in content:
            score += 30
            break
    if invalid_media:
        score += 15
    if oversized:
        score += 10
    return min(100, score)
