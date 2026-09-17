"""Provider-neutral signal observations.

This module intentionally performs deterministic normalization only. Model
interpretation, sentiment, ranking, or recommendations happen downstream and
must preserve the observation provenance carried here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Iterable, Optional, Tuple

_TOKEN_RE = re.compile(r"(?u)(?:[$#@]?[A-Za-z0-9][A-Za-z0-9._-]{1,63})")
_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
        "for", "from", "had", "has", "have", "he", "her", "here", "him",
        "his", "i", "if", "in", "into", "is", "it", "its", "me", "my",
        "not", "of", "on", "or", "our", "she", "so", "that", "the",
        "their", "them", "there", "they", "this", "to", "up", "us", "we",
        "were", "what", "when", "where", "which", "who", "with", "you",
        "your",
    }
)
_ALLOWED_MODALITIES = frozenset({"text", "audio_transcript", "video_transcript"})
_ALLOWED_VERIFICATION = frozenset({"unverified", "corroborated", "verified", "disputed"})


def _canonicalize_token(token: str) -> str:
    value = token.strip().casefold()
    if value[:1] in {"$", "#", "@"}:
        value = value[1:]
    return value.strip("._-")


def extract_keywords(text: str, *, max_keywords: int = 24) -> Tuple[str, ...]:
    """Extract stable keyword candidates without model inference.

    Order follows first appearance. Duplicates, common stop words, and tokens
    shorter than two characters are removed. Hashtag/cashtag/mention prefixes
    are normalized so that ``#Bitcoin`` and ``bitcoin`` share one Word HQ.
    """
    if max_keywords < 1:
        return ()

    seen = set()
    result = []
    for match in _TOKEN_RE.finditer(text or ""):
        token = _canonicalize_token(match.group(0))
        if len(token) < 2 or token in _STOP_WORDS or token in seen:
            continue
        seen.add(token)
        result.append(token)
        if len(result) >= max_keywords:
            break
    return tuple(result)


def _observation_id(
    source: str,
    source_reference: str,
    captured_at: str,
    speaker_id: Optional[str],
    text: str,
) -> str:
    payload = "\x1f".join(
        [source, source_reference, captured_at, speaker_id or "", text]
    ).encode("utf-8")
    return "sig_" + sha256(payload).hexdigest()[:32]


@dataclass(frozen=True)
class SignalObservation:
    """One attributable unit of observed social/audio evidence."""

    observation_id: str
    source: str
    source_reference: str
    captured_at: str
    text: str
    modality: str = "text"
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = None
    language: Optional[str] = None
    confidence: Optional[float] = None
    verification_state: str = "unverified"
    keywords: Tuple[str, ...] = ()

    @classmethod
    def from_text(
        cls,
        *,
        source: str,
        source_reference: str,
        captured_at: str,
        text: str,
        modality: str = "text",
        speaker_id: Optional[str] = None,
        speaker_name: Optional[str] = None,
        language: Optional[str] = None,
        confidence: Optional[float] = None,
        verification_state: str = "unverified",
        keywords: Optional[Iterable[str]] = None,
    ) -> "SignalObservation":
        if not source or not source_reference or not captured_at:
            raise ValueError("source, source_reference, and captured_at are required")
        if not text or not text.strip():
            raise ValueError("text is required")
        if modality not in _ALLOWED_MODALITIES:
            raise ValueError("unsupported modality: %s" % modality)
        if verification_state not in _ALLOWED_VERIFICATION:
            raise ValueError("unsupported verification_state: %s" % verification_state)
        if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        if keywords is None:
            normalized_keywords = extract_keywords(text)
        else:
            normalized_keywords = tuple(
                dict.fromkeys(
                    token
                    for token in (_canonicalize_token(item) for item in keywords)
                    if len(token) >= 2
                )
            )

        return cls(
            observation_id=_observation_id(
                source, source_reference, captured_at, speaker_id, text.strip()
            ),
            source=source,
            source_reference=source_reference,
            captured_at=captured_at,
            text=text.strip(),
            modality=modality,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            language=language,
            confidence=float(confidence) if confidence is not None else None,
            verification_state=verification_state,
            keywords=normalized_keywords,
        )

    @classmethod
    def from_social_event(cls, event: dict) -> "SignalObservation":
        """Normalize an already-governed Social Event into signal evidence."""
        provenance = event.get("provenance") or {}
        author = event.get("author") or {}
        content = event.get("content") or {}
        source_reference = provenance.get("source_reference") or event.get("event_id")
        captured_at = (
            event.get("source_timestamp")
            or provenance.get("retrieved_at")
            or event.get("received_at")
        )
        return cls.from_text(
            source=str(event.get("platform") or "unknown"),
            source_reference=str(source_reference or ""),
            captured_at=str(captured_at or ""),
            text=str(content.get("text") or ""),
            modality="text",
            speaker_id=str(author.get("id")) if author.get("id") is not None else None,
            speaker_name=author.get("display_name"),
            language=content.get("raw_language"),
            verification_state="unverified",
        )

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["keywords"] = list(self.keywords)
        return payload
