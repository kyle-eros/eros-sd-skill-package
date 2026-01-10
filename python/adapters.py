"""EROS v1.0 Production Adapters for MCP and Task Tool (<150 lines).

Connects v1.0 orchestrator to:
1. Real MCP server (via existing client)
2. Real Task tool (Claude Code sub-agents)

Includes:
- Retry logic with exponential backoff
- Timeout handling
- Request/response logging
"""
from __future__ import annotations
import asyncio, functools, logging, time, uuid
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

logger = logging.getLogger("eros.adapters")
T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    timeout: float = 120.0

def with_retry(config: RetryConfig = None):
    """Decorator for retry with exponential backoff."""
    cfg = config or RetryConfig()
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exc = None
            for attempt in range(cfg.max_retries + 1):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=cfg.timeout)
                except asyncio.TimeoutError as e:
                    last_exc = e
                    logger.warning(f"{func.__name__} timeout (attempt {attempt + 1}/{cfg.max_retries + 1})")
                except Exception as e:
                    last_exc = e
                    if attempt == cfg.max_retries: break
                    delay = min(cfg.base_delay * (cfg.exponential_base ** attempt), cfg.max_delay)
                    logger.warning(f"{func.__name__} failed (attempt {attempt + 1}), retry in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
            raise last_exc or RuntimeError("Retry exhausted")
        return wrapper
    return decorator

class ProductionMCPClient:
    """Wraps existing MCP client to match v1.0 Protocol with retry and logging.

    MCP Server: eros-db
    Tool Naming: mcp__eros-db__<tool-name>
    Total Tools: 15 (get_creator_profile now bundled with analytics+volume+rankings)
    """

    def __init__(self, mcp_tools: Any, retry_config: RetryConfig = None):
        """Initialize with existing MCP tools object (Claude Code mcp__eros-db__ namespace)."""
        self._mcp = mcp_tools
        self._cfg = retry_config or RetryConfig()
        self._call_count = 0

    def _log_call(self, method: str, args: dict, result: Any, duration_ms: float) -> None:
        self._call_count += 1
        trace_id = uuid.uuid4().hex[:8]
        logger.debug(f"MCP[{trace_id}] {method}({args}) -> {len(str(result))} chars in {duration_ms:.0f}ms")

    async def _call(self, method: str, **kwargs) -> dict:
        start = time.time()
        fn = getattr(self._mcp, method, None)
        if not fn: raise AttributeError(f"MCP method not found: {method}")
        result = await fn(**kwargs) if asyncio.iscoroutinefunction(fn) else fn(**kwargs)
        self._log_call(method, kwargs, result, (time.time() - start) * 1000)
        return result if isinstance(result, dict) else {"data": result}

    # ============================================================
    # CREATOR TOOLS (5)
    # ============================================================

    @with_retry()
    async def get_creator_profile(
        self,
        creator_id: str,
        include_analytics: bool = True,
        include_volume: bool = True,
        include_content_rankings: bool = True,
        include_vault: bool = True,
        include_persona: bool = True
    ) -> dict:
        """MCP: mcp__eros-db__get_creator_profile (bundled)

        Returns comprehensive bundle with analytics, volume, content rankings, vault, and persona.
        Reduces preflight from 4 MCP calls to 3.

        NEW in v1.3.0: include_vault=True bundles allowed_content_types data for HARD GATE validation.
        NEW in v1.4.0: include_persona=True bundles persona data for voice matching.
        """
        return await self._call(
            "get_creator_profile",
            creator_id=creator_id,
            include_analytics=include_analytics,
            include_volume=include_volume,
            include_content_rankings=include_content_rankings,
            include_vault=include_vault,
            include_persona=include_persona
        )

    @with_retry()
    async def get_active_creators(
        self,
        limit: int = 100,
        offset: int = 0,
        tier: str = None,
        page_type: str = None,
        min_revenue: float = None,
        max_revenue: float = None,
        min_fan_count: int = None,
        sort_by: str = "revenue",
        sort_order: str = "desc",
        include_volume_details: bool = False
    ) -> dict:
        """MCP: mcp__eros-db__get_active_creators

        Returns paginated list of active creators with comprehensive metrics.
        Supports filtering by tier, page_type, revenue range, and fan count.

        New in v1.2.0:
        - Pagination: offset, total_count, has_more
        - Sorting: sort_by (revenue/fan_count/name/tier), sort_order (asc/desc)
        - Filters: page_type, min_revenue, max_revenue, min_fan_count
        - Volume details: include_volume_details flag
        """
        return await self._call(
            "get_active_creators",
            limit=limit,
            offset=offset,
            tier=tier,
            page_type=page_type,
            min_revenue=min_revenue,
            max_revenue=max_revenue,
            min_fan_count=min_fan_count,
            sort_by=sort_by,
            sort_order=sort_order,
            include_volume_details=include_volume_details
        )

    @with_retry()
    async def get_allowed_content_types(
        self,
        creator_id: str,
        include_category: bool = True
    ) -> dict:
        """MCP: mcp__eros-db__get_allowed_content_types (HARD GATE)

        Returns content types a creator allows for PPV/revenue-based sends.
        A creator "allows" a content type when has_content=1 in vault_matrix.
        """
        return await self._call(
            "get_allowed_content_types",
            creator_id=creator_id,
            include_category=include_category
        )

    @with_retry()
    async def get_content_type_rankings(self, creator_id: str) -> dict:
        """MCP: mcp__eros-db__get_content_type_rankings (HARD GATE)"""
        return await self._call("get_content_type_rankings", creator_id=creator_id)

    @with_retry()
    async def get_persona_profile(self, creator_id: str) -> dict:
        """MCP: mcp__eros-db__get_persona_profile"""
        return await self._call("get_persona_profile", creator_id=creator_id)

    # ============================================================
    # SCHEDULE TOOLS (5)
    # ============================================================

    @with_retry()
    async def get_volume_config(
        self,
        creator_id: str,
        week_start: str,
        trigger_overrides: list[dict] | None = None
    ) -> dict:
        """MCP: mcp__eros-db__get_volume_config"""
        kwargs = {"creator_id": creator_id, "week_start": week_start}
        if trigger_overrides is not None:
            kwargs["trigger_overrides"] = trigger_overrides
        return await self._call("get_volume_config", **kwargs)

    @with_retry()
    async def get_active_volume_triggers(self, creator_id: str) -> dict:
        """MCP: mcp__eros-db__get_active_volume_triggers"""
        return await self._call("get_active_volume_triggers", creator_id=creator_id)

    @with_retry()
    async def get_performance_trends(self, creator_id: str, period: str = "14d") -> dict:
        """MCP: mcp__eros-db__get_performance_trends"""
        return await self._call("get_performance_trends", creator_id=creator_id, period=period)

    @with_retry(RetryConfig(max_retries=1, timeout=60.0))  # Save has stricter timeout
    async def save_schedule(self, creator_id: str, week_start: str, items: list,
                            validation_certificate: dict | None = None) -> dict:
        """MCP: mcp__eros-db__save_schedule"""
        return await self._call("save_schedule", creator_id=creator_id, week_start=week_start,
                                items=items, validation_certificate=validation_certificate or {})

    @with_retry(RetryConfig(max_retries=1, timeout=60.0))
    async def save_volume_triggers(self, creator_id: str, triggers: list) -> dict:
        """MCP: mcp__eros-db__save_volume_triggers"""
        return await self._call("save_volume_triggers", creator_id=creator_id, triggers=triggers)

    # ============================================================
    # CAPTION TOOLS (3)
    # ============================================================

    @with_retry()
    async def get_batch_captions_by_content_types(self, creator_id: str, content_types: list,
                                                   limit_per_type: int = 5) -> dict:
        """MCP: mcp__eros-db__get_batch_captions_by_content_types"""
        return await self._call("get_batch_captions_by_content_types", creator_id=creator_id,
                                content_types=content_types, limit_per_type=limit_per_type)

    @with_retry()
    async def get_send_type_captions(self, creator_id: str, send_type: str, limit: int = 10) -> dict:
        """MCP: mcp__eros-db__get_send_type_captions"""
        return await self._call("get_send_type_captions", creator_id=creator_id,
                                send_type=send_type, limit=limit)

    @with_retry()
    async def validate_caption_structure(self, caption_text: str, send_type: str) -> dict:
        """MCP: mcp__eros-db__validate_caption_structure"""
        return await self._call("validate_caption_structure", caption_text=caption_text, send_type=send_type)

    # ============================================================
    # CONFIG TOOLS (1)
    # ============================================================

    @with_retry()
    async def get_send_types(self, page_type: str = None) -> dict:
        """MCP: mcp__eros-db__get_send_types"""
        return await self._call("get_send_types", page_type=page_type)

    @property
    def call_count(self) -> int: return self._call_count

class ProductionTaskTool:
    """Wraps Claude Code task invocation for v1.0 agents."""

    def __init__(self, task_invoker: Callable, retry_config: RetryConfig = None):
        """Initialize with task invocation function (Task tool from Claude Code)."""
        self._invoke = task_invoker
        self._cfg = retry_config or RetryConfig(timeout=300.0)  # Agents need longer timeout

    @with_retry(RetryConfig(max_retries=2, timeout=300.0))
    async def invoke(self, subagent_type: str, prompt: str, model: str = "sonnet") -> dict:
        """Invoke a sub-agent and parse JSON response."""
        start = time.time()
        logger.info(f"TaskTool invoking {subagent_type} ({model})")
        result = await self._invoke(subagent_type=subagent_type, prompt=prompt, model=model)
        duration_ms = (time.time() - start) * 1000
        logger.info(f"TaskTool {subagent_type} completed in {duration_ms:.0f}ms")
        # Parse JSON from agent response if needed
        if isinstance(result, str):
            import json
            try:
                # Find JSON in response
                start_idx = result.find("{")
                end_idx = result.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    return json.loads(result[start_idx:end_idx])
            except json.JSONDecodeError:
                pass
            return {"raw_response": result}
        return result if isinstance(result, dict) else {"data": result}

def create_production_adapters(mcp_tools: Any, task_invoker: Callable) -> tuple[ProductionMCPClient, ProductionTaskTool]:
    """Factory function to create production adapters."""
    return ProductionMCPClient(mcp_tools), ProductionTaskTool(task_invoker)

__all__ = ["ProductionMCPClient", "ProductionTaskTool", "RetryConfig", "with_retry", "create_production_adapters"]
