"""Resource manager — concurrency control, memory guard, and limits."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("cloakbrowser.manager.resource_manager")


@dataclass
class ConcurrencyConfig:
    max_concurrent_workflows: int = int(os.environ.get("MAX_CONCURRENT_WORKFLOWS", "10"))
    max_concurrent_browsers_per_profile: int = int(os.environ.get("MAX_BROWSERS_PER_PROFILE", "3"))
    max_total_browser_instances: int = int(os.environ.get("MAX_TOTAL_BROWSERS", "20"))
    max_memory_per_browser_mb: int = int(os.environ.get("MAX_MEMORY_PER_BROWSER_MB", "2048"))
    browser_idle_timeout_seconds: int = int(os.environ.get("BROWSER_IDLE_TIMEOUT", "300"))
    workflow_queue_max_size: int = int(os.environ.get("WORKFLOW_QUEUE_MAX_SIZE", "100"))
    max_llm_tokens_per_task: int = int(os.environ.get("MAX_LLM_TOKENS_PER_TASK", "200000"))
    max_llm_budget_usd: float = float(os.environ.get("MAX_LLM_BUDGET_USD", "50.0"))


class ResourceManager:
    def __init__(self, config: ConcurrencyConfig | None = None) -> None:
        self._config = config or ConcurrencyConfig()
        self._workflow_semaphore = asyncio.Semaphore(self._config.max_concurrent_workflows)
        self._browser_semaphore = asyncio.Semaphore(self._config.max_total_browser_instances)
        self._profile_semaphores: dict[str, asyncio.Semaphore] = {}
        self._active_workflows: set[str] = set()
        self._llm_tokens_used: int = 0
        self._llm_cost_usd: float = 0.0

    @property
    def config(self) -> ConcurrencyConfig:
        return self._config

    @property
    def active_workflow_count(self) -> int:
        return len(self._active_workflows)

    @property
    def llm_tokens_used(self) -> int:
        return self._llm_tokens_used

    @property
    def llm_cost_usd(self) -> float:
        return self._llm_cost_usd

    async def acquire_workflow_slot(self, workflow_run_id: str) -> None:
        if self._workflow_semaphore.locked() and len(self._active_workflows) >= self._config.max_concurrent_workflows:
            raise WorkflowQueueFullError(
                f"Max concurrent workflows ({self._config.max_concurrent_workflows}) reached. "
                f"Please retry later."
            )
        await self._workflow_semaphore.acquire()
        self._active_workflows.add(workflow_run_id)
        logger.info(
            "Workflow slot acquired",
            extra={"workflow_run_id": workflow_run_id, "active_count": len(self._active_workflows)},
        )

    def release_workflow_slot(self, workflow_run_id: str) -> None:
        self._active_workflows.discard(workflow_run_id)
        self._workflow_semaphore.release()
        logger.info(
            "Workflow slot released",
            extra={"workflow_run_id": workflow_run_id, "active_count": len(self._active_workflows)},
        )

    async def acquire_browser_slot(self, profile_id: str) -> None:
        if profile_id not in self._profile_semaphores:
            self._profile_semaphores[profile_id] = asyncio.Semaphore(
                self._config.max_concurrent_browsers_per_profile
            )
        await self._browser_semaphore.acquire()
        await self._profile_semaphores[profile_id].acquire()
        logger.info(
            "Browser slot acquired",
            extra={"profile_id": profile_id},
        )

    def release_browser_slot(self, profile_id: str) -> None:
        self._browser_semaphore.release()
        if profile_id in self._profile_semaphores:
            self._profile_semaphores[profile_id].release()
        logger.info(
            "Browser slot released",
            extra={"profile_id": profile_id},
        )

    def check_llm_budget(self, tokens_to_add: int = 0) -> bool:
        if self._llm_tokens_used + tokens_to_add > self._config.max_llm_tokens_per_task:
            return False
        if self._llm_cost_usd >= self._config.max_llm_budget_usd:
            return False
        return True

    def record_llm_usage(self, tokens: int, cost_usd: float = 0.0) -> None:
        self._llm_tokens_used += tokens
        self._llm_cost_usd += cost_usd

    def get_status(self) -> dict:
        return {
            "active_workflows": len(self._active_workflows),
            "max_concurrent_workflows": self._config.max_concurrent_workflows,
            "max_total_browsers": self._config.max_total_browser_instances,
            "max_memory_per_browser_mb": self._config.max_memory_per_browser_mb,
            "llm_tokens_used": self._llm_tokens_used,
            "llm_cost_usd": round(self._llm_cost_usd, 4),
            "llm_budget_remaining_usd": round(self._config.max_llm_budget_usd - self._llm_cost_usd, 4),
        }


class WorkflowQueueFullError(Exception):
    pass
