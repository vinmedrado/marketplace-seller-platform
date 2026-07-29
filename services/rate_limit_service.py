"""Rate limiter leve para endpoints sensíveis.

É uma proteção de processo único. Em uma implantação com múltiplas réplicas,
substitua por um backend distribuído no gateway ou Redis.
"""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self.limit:
                return False
            attempts.append(now)
            return True


login_limiter = SlidingWindowRateLimiter(limit=20, window_seconds=300)
public_utility_limiter = SlidingWindowRateLimiter(limit=60, window_seconds=60)
