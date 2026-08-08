"""Content sanitization for model-facing representations (B3).

Raw provider payloads never enter model prompts. sanitize_content returns a
sanitized representation plus warnings, links, and untrusted markers. Content
is ALWAYS marked untrusted; nothing from content can become a policy field.
"""
import re

from .quarantine import MAX_TEXT_CHARS
from .risk import CREDENTIAL_KEYS, INSTRUCTION_SIGNALS

HTML_TAG_RE = re.compile(r"<[^>]*>")
URL_RE = re.compile(r"https?://[^\s]+")
JAVASCRIPT_URL_RE = re.compile(r"^\s*javascript:", re.IGNORECASE)


def sanitize_text(text):
    if not isinstance(text, str):
        text = str(text)
    text = HTML_TAG_RE.sub("", text)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + " [truncated]"
    return text


def sanitize_content(content):
    """Return (sanitized_content, warnings, links, credential_hits)."""
    warnings = []
    links = []
    credential_hits = []
    if not isinstance(content, dict):
        return {"text": sanitize_text(content), "untrusted": True}, ["non-object content"], [], []

    sanitized = {}
    for key, value in content.items():
        if key.lower() in CREDENTIAL_KEYS:
            credential_hits.append(key)
            continue
        if isinstance(value, str):
            if key.lower() in ("url", "link"):
                links.append(value)
                if JAVASCRIPT_URL_RE.match(value):
                    warnings.append("javascript: URL in field %s" % key)
            else:
                for match in URL_RE.findall(value):
                    links.append(match)
                if JAVASCRIPT_URL_RE.match(value):
                    warnings.append("javascript: URL in field %s" % key)
            sanitized[key] = sanitize_text(value)
        elif isinstance(value, (dict, list)):
            sanitized[key] = value
        else:
            sanitized[key] = value
    sanitized["untrusted"] = True
    return sanitized, warnings, links, credential_hits


def flag_instruction_signals(text):
    lowered = (text or "").lower()
    return [s for s in INSTRUCTION_SIGNALS if s in lowered]
