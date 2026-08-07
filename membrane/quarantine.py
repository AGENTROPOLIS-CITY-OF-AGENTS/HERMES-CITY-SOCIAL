"""Quarantine entry checks: size, type, and static validation (B3)."""

MAX_PAYLOAD_BYTES = 1_000_000
MAX_TEXT_CHARS = 2000
ALLOWED_MEDIA_TYPES = {
    "image/png", "image/jpeg", "image/webp", "image/gif",
    "video/mp4", "audio/mpeg", "text/plain", "application/json",
}


class QuarantineError(ValueError):
    pass


def check_size(payload_bytes):
    """Payload must be under MAX_PAYLOAD_BYTES.

    Accepts either the raw payload (bytes/str) or a precomputed byte length
    (int). The membrane passes the raw provider payload bytes; the quarantine
    gate compares its length.
    """
    if payload_bytes is None:
        return None
    if isinstance(payload_bytes, (bytes, bytearray)):
        size = len(payload_bytes)
    elif isinstance(payload_bytes, str):
        size = len(payload_bytes.encode("utf-8"))
    else:
        size = int(payload_bytes)
    if size > MAX_PAYLOAD_BYTES:
        raise QuarantineError("payload exceeds %d bytes" % MAX_PAYLOAD_BYTES)
    return None


def check_media_types(media_items):
    """Reject unsupported media types."""
    invalid = []
    for item in media_items or []:
        mtype = (item or {}).get("type")
        if mtype and mtype not in ALLOWED_MEDIA_TYPES:
            invalid.append(mtype)
    if invalid:
        raise QuarantineError("unsupported media type(s): %s" % ", ".join(invalid))
    return None


def check_static(payload_bytes_or_text):
    """Static validation: parse JSON if bytes/str are supplied."""
    if payload_bytes_or_text is None:
        return None
    if isinstance(payload_bytes_or_text, (bytes, bytearray)):
        data = payload_bytes_or_text.decode("utf-8", errors="replace")
    elif isinstance(payload_bytes_or_text, str):
        data = payload_bytes_or_text
    else:
        return None
    import json

    try:
        json.loads(data)
    except (ValueError, TypeError) as exc:
        raise QuarantineError("malformed JSON payload: %s" % exc) from exc
    return None
