"""Moltbook identity bridge for the AGENTROPOLIS Docking District.

This module implements the documented Moltbook identity-verification handshake
without exposing raw credentials to agents or model context.

Live use requires a sealed capability resolved outside the model as
`moltbook_app_key`. This module does not persist tokens or app keys.
"""

from dataclasses import dataclass
from typing import Any, Dict


VERIFY_PATH = "/api/v1/agents/verify-identity"
IDENTITY_HEADER = "X-Moltbook-Identity"
APP_KEY_HEADER = "X-Moltbook-App-Key"


class MoltbookIdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class MoltbookPassport:
    external_id: str
    name: str
    description: str | None
    avatar_url: str | None
    karma: int
    follower_count: int
    posts: int
    comments: int
    is_claimed: bool
    origin: str = "moltbook"
    origin_state: str = "EXTERNAL_MIRROR"

    def as_public_dict(self) -> Dict[str, Any]:
        return {
            "external_id": self.external_id,
            "name": self.name,
            "description": self.description,
            "avatar_url": self.avatar_url,
            "external_reputation": {
                "karma": self.karma,
                "follower_count": self.follower_count,
                "posts": self.posts,
                "comments": self.comments,
            },
            "is_claimed": self.is_claimed,
            "origin": self.origin,
            "origin_state": self.origin_state,
            "native_reputation": None,
            "citizenship_state": "VISITING_AGENT",
        }


def verify_identity(identity_token: str, app_key: str, http_client, base_url: str = "https://www.moltbook.com") -> MoltbookPassport:
    """Verify a short-lived Moltbook identity token and return a public passport.

    `http_client` must expose `post(url, headers=..., json=..., timeout=...)` and
    return an object with `status_code` and `json()`.
    """
    if not identity_token:
        raise MoltbookIdentityError("missing Moltbook identity token")
    if not app_key:
        raise MoltbookIdentityError("missing sealed Moltbook app capability")

    response = http_client.post(
        base_url.rstrip("/") + VERIFY_PATH,
        headers={APP_KEY_HEADER: app_key},
        json={"token": identity_token},
        timeout=10,
    )
    if response.status_code != 200:
        raise MoltbookIdentityError("Moltbook identity verification failed")

    payload = response.json()
    if not payload.get("success") or not payload.get("valid"):
        raise MoltbookIdentityError("invalid or expired Moltbook identity token")

    agent = payload.get("agent") or {}
    stats = agent.get("stats") or {}
    if not agent.get("id") or not agent.get("name"):
        raise MoltbookIdentityError("verified Moltbook profile missing required identity fields")

    return MoltbookPassport(
        external_id=str(agent["id"]),
        name=str(agent["name"]),
        description=agent.get("description"),
        avatar_url=agent.get("avatar_url"),
        karma=int(agent.get("karma") or 0),
        follower_count=int(agent.get("follower_count") or 0),
        posts=int(stats.get("posts") or 0),
        comments=int(stats.get("comments") or 0),
        is_claimed=bool(agent.get("is_claimed")),
    )
