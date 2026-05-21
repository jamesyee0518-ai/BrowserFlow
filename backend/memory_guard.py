"""Memory guard — monitor browser process memory and restart on limit breach."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("cloakbrowser.manager.memory_guard")


@dataclass
class MemoryGuardConfig:
    check_interval_seconds: int = int(os.environ.get("MEMORY_CHECK_INTERVAL", "30"))
    max_memory_mb: int = int(os.environ.get("MAX_MEMORY_PER_BROWSER_MB", "2048"))
    restart_cooldown_seconds: int = int(os.environ.get("MEMORY_RESTART_COOLDOWN", "120"))
    max_restart_attempts: int = int(os.environ.get("MEMORY_MAX_RESTART_ATTEMPTS", "3"))


class MemoryGuard:
    def __init__(
        self,
        config: MemoryGuardConfig | None = None,
        browser_manager: Any = None,
    ) -> None:
        self._config = config or MemoryGuardConfig()
        self._browser_manager = browser_manager
        self._task: asyncio.Task | None = None
        self._restart_timestamps: dict[str, list[float]] = {}
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(), name="memory_guard")
        logger.info(
            "MemoryGuard started (interval=%ds, limit=%dMB)",
            self._config.check_interval_seconds,
            self._config.max_memory_mb,
        )

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.info("MemoryGuard stopped")

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self._check_all_browsers()
            except Exception as e:
                logger.error("MemoryGuard check error: %s", e)
            await asyncio.sleep(self._config.check_interval_seconds)

    async def _check_all_browsers(self) -> None:
        if not self._browser_manager:
            return

        from .metrics import MetricsCollector
        metrics = MetricsCollector.get()

        for profile_id, running in list(self._browser_manager.running.items()):
            mem_mb = self._get_process_memory_mb(running)
            if mem_mb is not None:
                metrics.set_gauge(
                    "cloakbrowser_browser_memory_mb",
                    float(mem_mb),
                    {"profile_id": profile_id},
                )
                if mem_mb > self._config.max_memory_mb:
                    logger.warning(
                        "Profile %s memory %.0fMB exceeds limit %dMB",
                        profile_id, mem_mb, self._config.max_memory_mb,
                    )
                    await self._handle_memory_exceeded(profile_id, mem_mb)

    def _get_process_memory_mb(self, running: Any) -> float | None:
        try:
            return self._get_process_memory_from_os(running)
        except Exception as e:
            logger.debug("Failed to get memory for profile: %s", e)
            return None

    def _get_process_memory_from_os(self, running: Any) -> float | None:
        try:
            import psutil
        except ImportError:
            return self._get_process_memory_from_proc(running)

        try:
            cdp_port = running.cdp_port
            for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
                try:
                    cmdline = proc.info.get("cmdline") or []
                    cmdline_str = " ".join(cmdline)
                    if f"--remote-debugging-port={cdp_port}" in cmdline_str:
                        mem_info = proc.info.get("memory_info")
                        if mem_info:
                            return mem_info.rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug("psutil scan failed: %s", e)

        return self._get_process_memory_from_proc(running)

    def _get_process_memory_from_proc(self, running: Any) -> float | None:
        try:
            import subprocess
            result = subprocess.run(
                ["ps", "-o", "rss=", "-o", "pid="],
                capture_output=True, text=True, timeout=5,
            )
            cdp_port = running.cdp_port
            pgrep = subprocess.run(
                ["pgrep", "-f", f"--remote-debugging-port={cdp_port}"],
                capture_output=True, text=True, timeout=5,
            )
            pids = pgrep.stdout.strip().split("\n")
            if not pids or pids == [""]:
                return None

            total_rss_kb = 0
            for line in result.stdout.strip().split("\n"):
                parts = line.strip().split()
                if len(parts) >= 2:
                    rss_kb = int(parts[0])
                    pid = parts[1]
                    if pid in pids:
                        total_rss_kb += rss_kb

            return total_rss_kb / 1024 if total_rss_kb > 0 else None
        except Exception as e:
            logger.debug("proc scan failed: %s", e)
            return None

    async def _handle_memory_exceeded(self, profile_id: str, mem_mb: float) -> None:
        import time

        now = time.monotonic()
        timestamps = self._restart_timestamps.get(profile_id, [])
        timestamps = [t for t in timestamps if now - t < self._config.restart_cooldown_seconds]
        self._restart_timestamps[profile_id] = timestamps

        if len(timestamps) >= self._config.max_restart_attempts:
            logger.warning(
                "Profile %s exceeded max restart attempts (%d) within cooldown (%ds), skipping restart",
                profile_id,
                self._config.max_restart_attempts,
                self._config.restart_cooldown_seconds,
            )
            return

        if timestamps and now - timestamps[-1] < self._config.restart_cooldown_seconds / self._config.max_restart_attempts:
            logger.info("Profile %s restart on cooldown, skipping", profile_id)
            return

        logger.info(
            "Restarting profile %s due to memory limit (%.0fMB > %dMB)",
            profile_id, mem_mb, self._config.max_memory_mb,
        )

        from .metrics import MetricsCollector
        MetricsCollector.get().inc_counter(
            "cloakbrowser_browser_memory_restarts_total",
            labels={"profile_id": profile_id},
        )

        try:
            profile_data = None
            try:
                from . import database as db
                profile_data = db.get_profile(profile_id)
            except Exception:
                pass

            await self._browser_manager.stop(profile_id)
            logger.info("Profile %s stopped for memory restart", profile_id)

            if profile_data:
                await asyncio.sleep(2)
                await self._browser_manager.launch(profile_data)
                logger.info("Profile %s relaunched after memory restart", profile_id)

            timestamps.append(now)
            self._restart_timestamps[profile_id] = timestamps

        except Exception as e:
            logger.error("Failed to restart profile %s: %s", profile_id, e)

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "check_interval_seconds": self._config.check_interval_seconds,
            "max_memory_mb": self._config.max_memory_mb,
            "restart_cooldown_seconds": self._config.restart_cooldown_seconds,
            "max_restart_attempts": self._config.max_restart_attempts,
            "profiles_restarted": {
                pid: len(ts) for pid, ts in self._restart_timestamps.items() if ts
            },
        }
