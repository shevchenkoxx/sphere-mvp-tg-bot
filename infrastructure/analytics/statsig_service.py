"""Statsig server-side event logging via HTTP API."""

import hashlib
import logging
import time

import aiohttp

from config.settings import settings

logger = logging.getLogger(__name__)

_STATSIG_LOG_URL = "https://events.statsigapi.net/v1/rgstr"

# src_code prefix -> cluster mapping (mirrors site-side getCluster())
_CLUSTER_PREFIXES = {
    "homepage": "homepage",
    "home": "homepage",
    "alt": "alternatives",
    "vs": "vs",
    "blog": "blog",
    "connect": "connect",
    "match": "match",
    "for": "for",
    "compare": "compare",
    "press": "press",
    "why": "why-sphere",
    "venues": "venues",
    "geo": "geo",
    "in": "geo",
    "ai": "programmatic",
    "find": "programmatic",
}


def _hash_user_id(telegram_user_id: str) -> str:
    return hashlib.sha256(f"tg:{telegram_user_id}".encode()).hexdigest()[:16]


def _infer_cluster(src_code: str) -> str:
    lower = src_code.lower()
    if lower in _CLUSTER_PREFIXES:
        return _CLUSTER_PREFIXES[lower]
    first_segment = lower.split("_")[0] if "_" in lower else lower
    return _CLUSTER_PREFIXES.get(first_segment, "other")


def _infer_page_url(src_code: str, cluster: str) -> str:
    if cluster == "homepage":
        return "/"
    parts = src_code.split("_")
    if len(parts) > 1:
        slug = "/".join(parts[1:])
        if cluster in ("alternatives", "vs", "connect", "match", "for", "blog", "geo"):
            return f"/{cluster}/{slug}"
    return f"/{cluster}"


async def log_waitlist_signup_completed(
    telegram_user_id: str,
    src_code: str,
) -> None:
    if not settings.statsig_server_secret:
        logger.debug("STATSIG_SERVER_SECRET not set, skipping event")
        return

    cluster = _infer_cluster(src_code)
    page_url = _infer_page_url(src_code, cluster)
    hashed_uid = _hash_user_id(telegram_user_id)

    event = {
        "eventName": "waitlist_signup_completed",
        "user": {"userID": hashed_uid},
        "value": src_code,
        "metadata": {
            "src_code": src_code,
            "page_url": page_url,
            "cluster": cluster,
            "target_url": f"https://t.me/Spheresocial_bot?start=src_{src_code}",
        },
        "time": int(time.time() * 1000),
    }

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                _STATSIG_LOG_URL,
                headers={
                    "Content-Type": "application/json",
                    "statsig-api-key": settings.statsig_server_secret,
                },
                json={"events": [event]},
                timeout=aiohttp.ClientTimeout(total=10),
            )
            if resp.status >= 400:
                body = await resp.text()
                logger.warning("Statsig event failed (%d): %s", resp.status, body[:200])
            else:
                logger.info("waitlist_signup_completed fired for src_%s", src_code)
    except Exception:
        logger.warning("Statsig event send failed", exc_info=True)
