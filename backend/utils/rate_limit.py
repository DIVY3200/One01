"""Per-user limit on AI-backed requests, so one account can't drain the Gemini quota.

Sliding one-minute window kept in memory: fine for a single backend process.
With several workers each process counts separately, so the effective limit
is multiplied; move the counters to Redis if you scale out.
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Depends, HTTPException

from db.models import User
from utils.auth import get_current_user
from utils.config import settings

_WINDOW_SECONDS = 60
_hits: Dict[str, Deque[float]] = defaultdict(deque)


async def ai_rate_limit(current_user: User = Depends(get_current_user)) -> None:
    limit = settings.AI_RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return
    now = time.monotonic()
    hits = _hits[str(current_user.id)]
    while hits and now - hits[0] >= _WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= limit:
        retry_after = int(_WINDOW_SECONDS - (now - hits[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many AI requests. Please wait {retry_after}s and try again.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)


def reset() -> None:
    """Clear all counters (used by tests)."""
    _hits.clear()
