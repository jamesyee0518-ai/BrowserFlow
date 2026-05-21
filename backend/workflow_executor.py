"""Dual-path workflow executor — Agent (LLM) and Script (deterministic) execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Literal

from .browser_manager import BrowserManager
from .llm_config import LLMConfig
from .resource_manager import ResourceManager, WorkflowQueueFullError
from .metrics import MetricsCollector

logger = logging.getLogger("cloakbrowser.manager.workflow_executor")


@dataclass
class BlockResult:
    block_label: str
    status: Literal["completed", "failed", "terminated"]
    execution_path: Literal["agent", "script", "agent_fallback"]
    output: dict[str, Any] | None = None
    error: str | None = None
    llm_tokens_used: int = 0
    duration_seconds: float = 0.0
    actions_executed: int = 0
    screenshots_taken: int = 0


@dataclass
class WorkflowRunResult:
    workflow_run_id: str
    workflow_id: str
    profile_id: str
    status: Literal["completed", "failed", "terminated"]
    execution_path: Literal["agent", "script", "agent_fallback"] = "agent"
    blocks_completed: int = 0
    blocks_total: int = 0
    llm_tokens_used: int = 0
    duration_seconds: float = 0.0
    output: dict[str, Any] | None = None
    error: str | None = None


class RetryConfig:
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor


@dataclass
class AgentStep:
    action_type: str
    action_params: dict[str, Any] = field(default_factory=dict)
    element_id: str | None = None
    reasoning: str = ""


@dataclass
class AgentStepResult:
    success: bool
    action: AgentStep | None = None
    extracted_data: dict[str, Any] | None = None
    is_complete: bool = False
    error: str | None = None


class LLMCaller:
    """Unified LLM caller supporting OpenAI, Anthropic, and DeepSeek."""

    def __init__(self, llm_config: LLMConfig) -> None:
        self._config = llm_config
        self._openai_client = None
        self._anthropic_client = None

    def _get_openai_client(self):
        if self._openai_client is None:
            try:
                from openai import AsyncOpenAI

                cfg = self._config.primary
                self._openai_client = AsyncOpenAI(
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                )
            except ImportError:
                raise RuntimeError("openai package not installed. Run: pip install openai")
        return self._openai_client

    def _get_anthropic_client(self):
        if self._anthropic_client is None:
            try:
                from anthropic import AsyncAnthropic

                cfg = self._config.primary
                self._anthropic_client = AsyncAnthropic(api_key=cfg.api_key)
            except ImportError:
                raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        return self._anthropic_client

    async def call(
        self,
        prompt: str,
        screenshots: list[bytes] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        cfg = self._config.primary
        providers_to_try = [cfg.provider]

        fallback_map = {
            "openai": ["anthropic", "deepseek"],
            "anthropic": ["openai", "deepseek"],
            "deepseek": ["openai", "anthropic"],
            "azure": ["openai", "anthropic"],
        }
        for fb in fallback_map.get(cfg.provider, ["openai"]):
            if fb != cfg.provider and fb not in providers_to_try:
                providers_to_try.append(fb)

        last_error: Exception | None = None
        for provider in providers_to_try:
            try:
                if provider in ("openai", "deepseek"):
                    return await self._call_openai(
                        prompt=prompt,
                        screenshots=screenshots,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens or cfg.max_tokens,
                        temperature=temperature if temperature is not None else cfg.temperature,
                    )
                elif provider == "anthropic":
                    return await self._call_anthropic(
                        prompt=prompt,
                        screenshots=screenshots,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens or cfg.max_tokens,
                        temperature=temperature if temperature is not None else cfg.temperature,
                    )
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM provider %s failed, trying fallback: %s",
                    provider, str(e),
                )
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def _call_openai(
        self,
        prompt: str,
        screenshots: list[bytes] | None,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        import base64

        client = self._get_openai_client()
        cfg = self._config.primary

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if screenshots:
            for screenshot in screenshots:
                b64 = base64.b64encode(screenshot).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

        response = await client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        text = response.choices[0].message.content or ""
        tokens_used = 0
        if response.usage:
            tokens_used = response.usage.total_tokens

        return {"text": text, "tokens_used": tokens_used, "model": cfg.model}

    async def _call_anthropic(
        self,
        prompt: str,
        screenshots: list[bytes] | None,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        import base64

        client = self._get_anthropic_client()
        cfg = self._config.primary

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if screenshots:
            for screenshot in screenshots:
                b64 = base64.b64encode(screenshot).decode("utf-8")
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                })

        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        tokens_used = 0
        if response.usage:
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

        return {"text": text, "tokens_used": tokens_used, "model": cfg.model}


class ScriptExecutor:
    """Execute cached deterministic scripts in a sandboxed environment."""

    ALLOWED_BUILTINS = {
        "int": int, "float": float, "str": str, "bool": bool,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "len": len, "range": range, "enumerate": enumerate,
        "zip": zip, "sorted": sorted, "min": min, "max": max,
        "abs": abs, "round": round, "isinstance": isinstance,
        "True": True, "False": False, "None": None,
    }

    async def execute(
        self,
        script_code: str,
        page: Any,
        context_values: dict[str, Any],
    ) -> dict[str, Any]:
        local_vars: dict[str, Any] = {
            "__builtins__": self.ALLOWED_BUILTINS,
            "page": page,
            "context": context_values,
        }

        exec(script_code, local_vars)

        result = local_vars.get("result")
        if result is None:
            run_func = local_vars.get("run")
            if run_func and callable(run_func):
                result = run_func(page, context_values)

        if isinstance(result, dict):
            return result
        return {"value": result}


class ScriptGenerator:
    """Generate deterministic scripts from successful Agent executions."""

    async def generate_from_actions(
        self,
        url: str,
        actions: list[AgentStep],
        extraction_result: dict[str, Any] | None = None,
    ) -> str:
        lines = [
            "async def run(page, context):",
            f"    await page.goto({url!r}, wait_until='domcontentloaded', timeout=30000)",
        ]

        for action in actions:
            if action.action_type == "click":
                if action.element_id:
                    lines.append(
                        f"    await page.click({action.element_id!r}, timeout=10000)"
                    )
                elif action.action_params.get("selector"):
                    sel = action.action_params["selector"]
                    lines.append(f"    await page.click({sel!r}, timeout=10000)")
            elif action.action_type == "fill" or action.action_type == "input":
                if action.action_params.get("selector") and action.action_params.get("value"):
                    sel = action.action_params["selector"]
                    val = action.action_params["value"]
                    lines.append(f"    await page.fill({sel!r}, {val!r})")
            elif action.action_type == "select_option":
                if action.action_params.get("selector") and action.action_params.get("value"):
                    sel = action.action_params["selector"]
                    val = action.action_params["value"]
                    lines.append(f"    await page.select_option({sel!r}, {val!r})")
            elif action.action_type == "wait":
                timeout = action.action_params.get("timeout", 3000)
                lines.append(f"    await page.wait_for_timeout({timeout})")
            elif action.action_type == "goto":
                target_url = action.action_params.get("url", "")
                if target_url:
                    lines.append(
                        f"    await page.goto({target_url!r}, wait_until='domcontentloaded', timeout=30000)"
                    )

        if extraction_result:
            lines.append("    result = {}")
            for key, value in extraction_result.items():
                lines.append(f"    result[{key!r}] = {value!r}")
            lines.append("    return result")
        else:
            lines.append("    return {'status': 'completed'}")

        return "\n".join(lines)


class WorkflowExecutor:
    def __init__(self, browser_manager: BrowserManager) -> None:
        self.browser_manager = browser_manager
        self._llm_config = LLMConfig.get()
        self._llm_caller: LLMCaller | None = None
        self._script_executor = ScriptExecutor()
        self._script_generator = ScriptGenerator()
        self._running_workflows: dict[str, asyncio.Task] = {}
        self._resource_manager = ResourceManager()
        self._metrics = MetricsCollector.get()

    def _get_llm_caller(self) -> LLMCaller:
        if self._llm_caller is None:
            self._llm_caller = LLMCaller(self._llm_config)
        return self._llm_caller

    async def execute_workflow(
        self,
        workflow: dict[str, Any],
        workflow_run_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        start_time = time.monotonic()
        profile_id = workflow["profile_id"]
        definition = workflow.get("definition", {})
        blocks = definition.get("blocks", [])
        run_with = workflow.get("run_with", "agent")
        ai_fallback = workflow.get("ai_fallback", True)
        adaptive_caching = workflow.get("adaptive_caching", True)

        results: list[BlockResult] = []
        context_values: dict[str, Any] = dict(parameters or {})

        try:
            await self._resource_manager.acquire_workflow_slot(workflow_run_id)
        except WorkflowQueueFullError as e:
            return WorkflowRunResult(
                workflow_run_id=workflow_run_id,
                workflow_id=workflow["id"],
                profile_id=profile_id,
                status="failed",
                error=str(e),
                duration_seconds=time.monotonic() - start_time,
            )

        try:
            running = await self.browser_manager.allocate_for_workflow(
                profile_id=profile_id,
                workflow_run_id=workflow_run_id,
            )
        except Exception as e:
            logger.error("Failed to allocate browser for workflow %s: %s", workflow_run_id, e)
            return WorkflowRunResult(
                workflow_run_id=workflow_run_id,
                workflow_id=workflow["id"],
                profile_id=profile_id,
                status="failed",
                error=f"Browser allocation failed: {e}",
                duration_seconds=time.monotonic() - start_time,
            )

        try:
            for block_idx, block in enumerate(blocks):
                block_result = await self._execute_block_with_retry(
                    block=block,
                    block_idx=block_idx,
                    run_with=run_with,
                    ai_fallback=ai_fallback,
                    adaptive_caching=adaptive_caching,
                    context_values=context_values,
                    running_profile=running,
                )
                results.append(block_result)
                context_values[block.get("label", f"block_{block_idx}")] = block_result.output

                if block_result.status == "failed":
                    break

            all_completed = all(r.status == "completed" for r in results)
            primary_path = "agent"
            if results:
                first_path = results[0].execution_path
                if all(r.execution_path == first_path for r in results):
                    primary_path = first_path
                elif any(r.execution_path == "agent_fallback" for r in results):
                    primary_path = "agent_fallback"
                elif any(r.execution_path == "script" for r in results):
                    primary_path = "script"

            return WorkflowRunResult(
                workflow_run_id=workflow_run_id,
                workflow_id=workflow["id"],
                profile_id=profile_id,
                status="completed" if all_completed else "failed",
                execution_path=primary_path,
                blocks_completed=sum(1 for r in results if r.status == "completed"),
                blocks_total=len(blocks),
                llm_tokens_used=sum(r.llm_tokens_used for r in results),
                duration_seconds=time.monotonic() - start_time,
                output=context_values,
                error=results[-1].error if results and results[-1].status == "failed" else None,
            )

        finally:
            keep_alive = workflow.get("keep_browser_alive", False)
            await self.browser_manager.release_from_workflow(
                profile_id=profile_id,
                workflow_run_id=workflow_run_id,
                keep_alive=keep_alive,
            )
            self._resource_manager.release_workflow_slot(workflow_run_id)
            self._metrics.record_workflow_duration(
                time.monotonic() - start_time, primary_path, workflow["id"],
            )
            self._metrics.set_browser_pool_active(len(self.browser_manager.running))
            self._metrics.record_llm_tokens(
                sum(r.llm_tokens_used for r in results), self._llm_config.primary.model, primary_path,
            )

    async def _execute_block_with_retry(
        self,
        block: dict[str, Any],
        block_idx: int,
        run_with: str,
        ai_fallback: bool,
        adaptive_caching: bool,
        context_values: dict[str, Any],
        running_profile: Any,
        retry_config: RetryConfig | None = None,
    ) -> BlockResult:
        config = retry_config or RetryConfig(max_retries=3, backoff_factor=1.0)
        last_result: BlockResult | None = None

        for attempt in range(config.max_retries):
            result = await self._execute_block(
                block=block,
                block_idx=block_idx,
                run_with=run_with,
                ai_fallback=ai_fallback,
                adaptive_caching=adaptive_caching,
                context_values=context_values,
                running_profile=running_profile,
            )

            if result.status == "completed":
                return result

            last_result = result

            is_retryable = result.error and any(
                kw in result.error.lower()
                for kw in ["timeout", "connection", "crashed", "navigation"]
            )
            if not is_retryable or attempt == config.max_retries - 1:
                break

            backoff = config.backoff_factor * (2 ** attempt)
            logger.warning(
                "Block %s failed (attempt %d/%d), retrying in %.1fs: %s",
                block.get("label", f"block_{block_idx}"),
                attempt + 1, config.max_retries, backoff, result.error,
            )
            await asyncio.sleep(backoff)

        if last_result and last_result.status == "failed" and ai_fallback:
            if last_result.execution_path == "script":
                logger.warning(
                    "Script path failed for block %s after retries, falling back to agent",
                    block.get("label", f"block_{block_idx}"),
                )
                agent_result = await self._execute_agent_path(
                    block, running_profile, context_values,
                )
                agent_result.execution_path = "agent_fallback"
                return agent_result

        return last_result or BlockResult(
            block_label=block.get("label", f"block_{block_idx}"),
            status="failed",
            execution_path="agent",
            error="All retries exhausted",
        )

    async def _execute_block(
        self,
        block: dict[str, Any],
        block_idx: int,
        run_with: str,
        ai_fallback: bool,
        adaptive_caching: bool,
        context_values: dict[str, Any],
        running_profile: Any,
    ) -> BlockResult:
        block_label = block.get("label", f"block_{block_idx}")
        block_type = block.get("block_type", "task")
        start_time = time.monotonic()

        if block_type == "code":
            return await self._execute_code_block(block, context_values, start_time)

        if block_type == "for_loop":
            return await self._execute_for_loop_block(
                block, run_with, ai_fallback, adaptive_caching, context_values, running_profile, start_time,
            )

        if block_type == "conditional":
            return await self._execute_conditional_block(
                block, run_with, ai_fallback, adaptive_caching, context_values, running_profile, start_time,
            )

        if block_type in ("task", "navigation", "extraction", "login", "action"):
            cached_script = block.get("cached_script")
            if cached_script and run_with != "agent":
                try:
                    result = await self._execute_script_path(
                        cached_script, running_profile, context_values,
                    )
                    result.block_label = block_label
                    result.duration_seconds = time.monotonic() - start_time
                    return result
                except Exception as e:
                    if not ai_fallback:
                        return BlockResult(
                            block_label=block_label,
                            status="failed",
                            execution_path="script",
                            error=str(e),
                            duration_seconds=time.monotonic() - start_time,
                        )
                    logger.warning(
                        "Script path failed for block %s, falling back to agent: %s",
                        block_label, e,
                    )
                    agent_result = await self._execute_agent_path(
                        block, running_profile, context_values,
                    )
                    agent_result.block_label = block_label
                    agent_result.execution_path = "agent_fallback"
                    agent_result.duration_seconds = time.monotonic() - start_time
                    return agent_result

            agent_result = await self._execute_agent_path(
                block, running_profile, context_values,
            )
            agent_result.block_label = block_label
            agent_result.duration_seconds = time.monotonic() - start_time

            if adaptive_caching and agent_result.status == "completed":
                await self._maybe_generate_script(block, agent_result)

            return agent_result

        return BlockResult(
            block_label=block_label,
            status="completed",
            execution_path="agent",
            duration_seconds=time.monotonic() - start_time,
        )

    async def _execute_agent_path(
        self,
        block: dict[str, Any],
        running_profile: Any,
        context_values: dict[str, Any],
    ) -> BlockResult:
        block_label = block.get("label", "unknown")

        if not self._llm_config.is_configured():
            return BlockResult(
                block_label=block_label,
                status="failed",
                execution_path="agent",
                error="LLM is not configured. Set LLM_API_KEY environment variable.",
            )

        try:
            context = running_profile.context
            page = context.pages[0] if context.pages else await context.new_page()

            url = block.get("url")
            if url:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            navigation_goal = block.get("navigation_goal", "")
            data_extraction_goal = block.get("data_extraction_goal", "")
            max_steps = block.get("max_steps", 25)

            llm_caller = self._get_llm_caller()
            total_tokens = 0
            actions_executed: list[AgentStep] = []
            screenshots_taken = 0
            extracted_data: dict[str, Any] | None = None

            for step_num in range(max_steps):
                screenshot_bytes = await page.screenshot(type="png", full_page=False)
                screenshots_taken += 1

                prompt = self._build_agent_prompt(
                    navigation_goal=navigation_goal,
                    data_extraction_goal=data_extraction_goal,
                    url=page.url,
                    step_num=step_num + 1,
                    max_steps=max_steps,
                )

                system_prompt = (
                    "You are a browser automation agent. Analyze the screenshot and determine the next action. "
                    "Respond with a JSON object containing:\n"
                    '- "action": one of "click", "fill", "select_option", "goto", "wait", "complete", "extract"\n'
                    '- "selector": CSS selector for the target element (if applicable)\n'
                    '- "value": value to input (for fill/select_option)\n'
                    '- "url": URL to navigate to (for goto)\n'
                    '- "reasoning": brief explanation of why this action\n'
                    '- "data": extracted data (for extract/complete)\n'
                    "Always respond with valid JSON only."
                )

                llm_response = await llm_caller.call(
                    prompt=prompt,
                    screenshots=[screenshot_bytes],
                    system_prompt=system_prompt,
                )
                total_tokens += llm_response.get("tokens_used", 0)
                self._resource_manager.record_llm_usage(
                    llm_response.get("tokens_used", 0),
                    cost_usd=llm_response.get("tokens_used", 0) * 0.000005,
                )
                if not self._resource_manager.check_llm_budget():
                    return BlockResult(
                        block_label=block_label,
                        status="failed",
                        execution_path="agent",
                        error="LLM budget exceeded",
                        llm_tokens_used=total_tokens,
                        actions_executed=len(actions_executed),
                        screenshots_taken=screenshots_taken,
                    )

                action = self._parse_llm_response(llm_response.get("text", ""))
                if action is None:
                    logger.warning("Failed to parse LLM response at step %d", step_num + 1)
                    continue

                actions_executed.append(action)

                if action.action_type in ("complete", "extract"):
                    if action.action_params.get("data"):
                        extracted_data = action.action_params["data"]
                    break

                step_result = await self._execute_agent_action(page, action)
                if not step_result.success:
                    logger.warning(
                        "Action %s failed at step %d: %s",
                        action.action_type, step_num + 1, step_result.error,
                    )
                    if step_result.error and "crashed" in step_result.error.lower():
                        return BlockResult(
                            block_label=block_label,
                            status="failed",
                            execution_path="agent",
                            error=f"Browser crashed: {step_result.error}",
                            llm_tokens_used=total_tokens,
                            actions_executed=len(actions_executed),
                            screenshots_taken=screenshots_taken,
                        )

                await asyncio.sleep(0.5)

            return BlockResult(
                block_label=block_label,
                status="completed",
                execution_path="agent",
                output=extracted_data or {"navigation_goal": navigation_goal},
                llm_tokens_used=total_tokens,
                actions_executed=len(actions_executed),
                screenshots_taken=screenshots_taken,
            )

        except Exception as e:
            logger.error("Agent path failed for block %s: %s", block_label, traceback.format_exc())
            return BlockResult(
                block_label=block_label,
                status="failed",
                execution_path="agent",
                error=str(e),
            )

    async def _execute_script_path(
        self,
        script_code: str,
        running_profile: Any,
        context_values: dict[str, Any],
    ) -> BlockResult:
        try:
            context = running_profile.context
            page = context.pages[0] if context.pages else await context.new_page()

            result = await self._script_executor.execute(
                script_code=script_code,
                page=page,
                context_values=context_values,
            )

            return BlockResult(
                block_label="script",
                status="completed",
                execution_path="script",
                output=result,
            )

        except Exception as e:
            logger.error("Script path failed: %s", traceback.format_exc())
            return BlockResult(
                block_label="script",
                status="failed",
                execution_path="script",
                error=str(e),
            )

    async def _execute_code_block(
        self,
        block: dict[str, Any],
        context_values: dict[str, Any],
        start_time: float,
    ) -> BlockResult:
        block_label = block.get("label", "unknown")
        code = block.get("code", "")

        if not code:
            return BlockResult(
                block_label=block_label,
                status="completed",
                execution_path="agent",
                duration_seconds=time.monotonic() - start_time,
            )

        try:
            safe_builtins = {
                "int": int, "float": float, "str": str, "bool": bool,
                "list": list, "dict": dict, "tuple": tuple, "set": set,
                "len": len, "range": range, "enumerate": enumerate,
                "zip": zip, "sorted": sorted, "min": min, "max": max,
                "abs": abs, "round": round, "isinstance": isinstance,
                "sum": sum, "any": any, "all": all, "print": print,
                "True": True, "False": False, "None": None,
            }
            local_vars: dict[str, Any] = {
                "__builtins__": safe_builtins,
                "context": context_values,
            }
            exec(code, local_vars)
            output = local_vars.get("result", local_vars.get("output"))

            return BlockResult(
                block_label=block_label,
                status="completed",
                execution_path="agent",
                output=output if isinstance(output, dict) else {"value": output},
                duration_seconds=time.monotonic() - start_time,
            )
        except Exception as e:
            return BlockResult(
                block_label=block_label,
                status="failed",
                execution_path="agent",
                error=str(e),
                duration_seconds=time.monotonic() - start_time,
            )

    async def _execute_for_loop_block(
        self,
        block: dict[str, Any],
        run_with: str,
        ai_fallback: bool,
        adaptive_caching: bool,
        context_values: dict[str, Any],
        running_profile: Any,
        start_time: float,
    ) -> BlockResult:
        block_label = block.get("label", "unknown")
        loop_over = block.get("loop_over", [])
        loop_blocks = block.get("loop_blocks", [])
        max_iterations = min(len(loop_over), 500)

        all_outputs: list[Any] = []
        for i in range(max_iterations):
            context_values["current_item"] = loop_over[i]
            context_values["loop_index"] = i

            for child_block in loop_blocks:
                child_result = await self._execute_block(
                    block=child_block,
                    block_idx=i,
                    run_with=run_with,
                    ai_fallback=ai_fallback,
                    adaptive_caching=adaptive_caching,
                    context_values=context_values,
                    running_profile=running_profile,
                )
                if child_result.status == "failed":
                    return BlockResult(
                        block_label=block_label,
                        status="failed",
                        execution_path=child_result.execution_path,
                        error=f"Iteration {i} failed: {child_result.error}",
                        duration_seconds=time.monotonic() - start_time,
                    )
                all_outputs.append(child_result.output)

        return BlockResult(
            block_label=block_label,
            status="completed",
            execution_path="agent",
            output={"iterations": max_iterations, "results": all_outputs},
            duration_seconds=time.monotonic() - start_time,
        )

    async def _execute_conditional_block(
        self,
        block: dict[str, Any],
        run_with: str,
        ai_fallback: bool,
        adaptive_caching: bool,
        context_values: dict[str, Any],
        running_profile: Any,
        start_time: float,
    ) -> BlockResult:
        block_label = block.get("label", "unknown")
        condition = block.get("condition", "")
        then_blocks = block.get("then_blocks", [])
        else_blocks = block.get("else_blocks", [])

        condition_met = self._evaluate_condition(condition, context_values)

        blocks_to_execute = then_blocks if condition_met else else_blocks
        for child_block in blocks_to_execute:
            child_result = await self._execute_block(
                block=child_block,
                block_idx=0,
                run_with=run_with,
                ai_fallback=ai_fallback,
                adaptive_caching=adaptive_caching,
                context_values=context_values,
                running_profile=running_profile,
            )
            if child_result.status == "failed":
                return BlockResult(
                    block_label=block_label,
                    status="failed",
                    execution_path=child_result.execution_path,
                    error=child_result.error,
                    duration_seconds=time.monotonic() - start_time,
                )

        return BlockResult(
            block_label=block_label,
            status="completed",
            execution_path="agent",
            output={"condition_met": condition_met},
            duration_seconds=time.monotonic() - start_time,
        )

    def _evaluate_condition(self, condition: str, context_values: dict[str, Any]) -> bool:
        if not condition:
            return False
        try:
            safe_builtins = {"True": True, "False": False, "None": None, "len": len}
            local_vars: dict[str, Any] = {"__builtins__": safe_builtins}
            local_vars.update(context_values)
            return bool(eval(condition, local_vars))
        except Exception:
            return False

    def _build_agent_prompt(
        self,
        navigation_goal: str,
        data_extraction_goal: str,
        url: str,
        step_num: int,
        max_steps: int,
    ) -> str:
        parts = [
            f"Current URL: {url}",
            f"Step: {step_num}/{max_steps}",
        ]
        if navigation_goal:
            parts.append(f"Navigation Goal: {navigation_goal}")
        if data_extraction_goal:
            parts.append(f"Data Extraction Goal: {data_extraction_goal}")

        parts.append(
            "Analyze the screenshot and determine the next action to achieve the goal. "
            "If the goal is achieved, respond with action 'complete' or 'extract' and include the extracted data. "
            "Respond with valid JSON only."
        )
        return "\n".join(parts)

    def _parse_llm_response(self, text: str) -> AgentStep | None:
        try:
            json_str = text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
            action_type = data.get("action", "").lower()

            return AgentStep(
                action_type=action_type,
                action_params={
                    "selector": data.get("selector"),
                    "value": data.get("value"),
                    "url": data.get("url"),
                    "data": data.get("data"),
                },
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning("Failed to parse LLM response as JSON: %s", e)
            return None

    async def _execute_agent_action(
        self,
        page: Any,
        action: AgentStep,
    ) -> AgentStepResult:
        try:
            if action.action_type == "click":
                selector = action.action_params.get("selector")
                if selector:
                    await page.click(selector, timeout=10000)
                    return AgentStepResult(success=True, action=action)

            elif action.action_type == "fill":
                selector = action.action_params.get("selector")
                value = action.action_params.get("value", "")
                if selector:
                    await page.fill(selector, str(value), timeout=10000)
                    return AgentStepResult(success=True, action=action)

            elif action.action_type == "select_option":
                selector = action.action_params.get("selector")
                value = action.action_params.get("value", "")
                if selector:
                    await page.select_option(selector, str(value), timeout=10000)
                    return AgentStepResult(success=True, action=action)

            elif action.action_type == "goto":
                url = action.action_params.get("url", "")
                if url:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    return AgentStepResult(success=True, action=action)

            elif action.action_type == "wait":
                await page.wait_for_timeout(3000)
                return AgentStepResult(success=True, action=action)

            elif action.action_type in ("complete", "extract"):
                return AgentStepResult(
                    success=True,
                    action=action,
                    extracted_data=action.action_params.get("data"),
                    is_complete=True,
                )

            else:
                logger.warning("Unknown action type: %s", action.action_type)
                return AgentStepResult(success=False, error=f"Unknown action: {action.action_type}")

            return AgentStepResult(success=False, error=f"Missing required params for {action.action_type}")

        except Exception as e:
            return AgentStepResult(success=False, error=str(e))

    async def _maybe_generate_script(
        self,
        block: dict[str, Any],
        result: BlockResult,
    ) -> None:
        if result.actions_executed == 0:
            return

        actions = []
        if hasattr(result, '_agent_steps'):
            actions = result._agent_steps

        try:
            script = await self._script_generator.generate_from_actions(
                url=block.get("url", ""),
                actions=actions,
                extraction_result=result.output,
            )
            block["cached_script"] = script
            logger.info(
                "Generated cached script for block %s (%d actions)",
                block.get("label", "unknown"), len(actions),
            )
        except Exception as e:
            logger.warning("Failed to generate script for block %s: %s", block.get("label"), e)
