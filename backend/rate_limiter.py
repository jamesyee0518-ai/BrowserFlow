"""Rate limiter — in-memory sliding window rate limiting for API endpoints."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass

from fastapi import HTTPException, Request

logger = logging.getLogger("cloakbrowser.manager.rate_limiter")


@dataclass
class RateLimitConfig:
    requests_per_minute: int = int(os.environ.get("RATE_LIMIT_RPM", "60"))
    burst_size: int = int(os.environ.get("RATE_LIMIT_BURST", "10"))
    cdp_requests_per_minute: int = int(os.environ.get("CDP_RATE_LIMIT_RPM", "30"))


class RateLimiter:
    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or RateLimitConfig()
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._cdp_windows: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown"

    def _cleanup_window(self, entries: list[float], window_seconds: float = 60.0) -> list[float]:
        cutoff = time.monotonic() - window_seconds
        return [t for t in entries if t > cutoff]

    def check_rate_limit(self, request: Request) -> None:
        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        self._windows[client_ip] = self._cleanup_window(self._windows[client_ip])
        self._windows[client_ip].append(now)

        if len(self._windows[client_ip]) > self._config.requests_per_minute:
            logger.warning("Rate limit exceeded for %s: %d requests/min", client_ip, len(self._windows[client_ip]))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please retry later.",
                headers={"Retry-After": "60"},
            )

    def check_cdp_rate_limit(self, request: Request) -> None:
        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        self._cdp_windows[client_ip] = self._cleanup_window(self._cdp_windows[client_ip])
        self._cdp_windows[client_ip].append(now)

        if len(self._cdp_windows[client_ip]) > self._config.cdp_requests_per_minute:
            logger.warning("CDP rate limit exceeded for %s: %d requests/min", client_ip, len(self._cdp_windows[client_ip]))
            raise HTTPException(
                status_code=429,
                detail="CDP rate limit exceeded. Please retry later.",
                headers={"Retry-After": "60"},
            )

    def get_status(self) -> dict:
        return {
            "tracked_ips": len(self._windows),
            "cdp_tracked_ips": len(self._cdp_windows),
            "config": {
                "requests_per_minute": self._config.requests_per_minute,
                "burst_size": self._config.burst_size,
                "cdp_requests_per_minute": self._config.cdp_requests_per_minute,
            },
        }


rate_limiter = RateLimiter()
