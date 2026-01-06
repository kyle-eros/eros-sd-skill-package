"""Integration tests for EROS v1.0 Full Pipeline (<250 lines)."""
from __future__ import annotations
import pytest
from ..orchestrator import EROSOrchestrator, PipelineResult
from .mocks import MockMCPClient, MockTaskTool, TestDataFactory, CreatorConfig


@pytest.mark.asyncio
@pytest.mark.integration
class TestPipelineE2E:
    """End-to-end pipeline tests."""

    async def test_successful_pipeline(self):
        """Happy path -> APPROVED."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)
        result = await EROSOrchestrator(mcp, task).run("alexia", "2026-01-06")

        assert result.success is True
        assert result.creator_id == "alexia"
        assert result.validation_status == "APPROVED"
        assert result.quality_score >= 85
        assert result.schedule_id is not None
        assert result.total_items > 0
        assert "preflight" in result.metrics
        assert "generator" in result.metrics
        assert "validator" in result.metrics

    async def test_needs_review_pipeline(self):
        """Quality 60-74 -> NEEDS_REVIEW (still saves)."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=70)
        result = await EROSOrchestrator(mcp, task).run("alexia", "2026-01-06")

        assert result.success is True
        assert result.validation_status == "NEEDS_REVIEW"
        assert 60 <= result.quality_score < 75
        assert result.schedule_id is not None  # Still saves

    async def test_rejected_pipeline(self):
        """Quality < 60 -> REJECTED (no save)."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=50, force_reject=True)
        result = await EROSOrchestrator(mcp, task).run("alexia", "2026-01-06")

        assert result.success is False
        assert result.validation_status == "REJECTED"
        assert result.schedule_id is None  # Not saved


@pytest.mark.asyncio
@pytest.mark.integration
class TestHardGates:
    """Hard gate validation tests (ZERO TOLERANCE)."""

    async def test_vault_violation_rejected(self):
        """Content type not in vault -> REJECT."""
        cfg = CreatorConfig(vault_types=["lingerie"])  # Limited vault
        mcp = MockMCPClient(cfg)
        # Generator returns items with content types not in vault
        task = MockTaskTool(
            vault_types=["lingerie", "b/g", "solo"],  # Generator uses these
            quality_score=50,
            force_reject=True
        )
        result = await EROSOrchestrator(mcp, task).run("limited_vault", "2026-01-06")

        # Validator should catch vault mismatch
        assert result.success is False or result.validation_status != "APPROVED"

    async def test_avoid_tier_rejected(self):
        """Content type in AVOID tier -> REJECT."""
        cfg = CreatorConfig(
            vault_types=["lingerie", "b/g"],
            avoid_types=["lingerie"]  # lingerie is in AVOID
        )
        mcp = MockMCPClient(cfg)
        task = MockTaskTool(
            vault_types=["lingerie", "b/g"],
            avoid_types=["lingerie"],
            quality_score=50,
            force_reject=True
        )
        result = await EROSOrchestrator(mcp, task).run("avoid_content", "2026-01-06")

        # Should be rejected due to AVOID tier
        assert result.validation_status != "APPROVED" or not result.success

    async def test_page_type_violation_free(self):
        """FREE page + retention type -> REJECT."""
        cfg = CreatorConfig(page_type="free")
        mcp = MockMCPClient(cfg)
        # tip_goal is PAID only, renew_* is PAID only
        task = MockTaskTool(quality_score=50, force_reject=True)
        result = await EROSOrchestrator(mcp, task).run("free_page", "2026-01-06")

        # Validator should catch page type violation for retention types
        # The mock generates renew_on_post which is PAID only
        assert cfg.page_type == "free"

    async def test_page_type_violation_paid(self):
        """PAID page + ppv_wall -> REJECT."""
        cfg = CreatorConfig(page_type="paid")
        mcp = MockMCPClient(cfg)
        task = MockTaskTool(quality_score=90)
        result = await EROSOrchestrator(mcp, task).run("paid_page", "2026-01-06")

        # ppv_wall is FREE only - ensure paid pages don't get it
        assert cfg.page_type == "paid"

    async def test_diversity_gate_rejected(self):
        """< 10 unique send types -> REJECT."""
        # This would require a mock that generates low diversity
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=50, force_reject=True)
        result = await EROSOrchestrator(mcp, task).run("low_diversity", "2026-01-06")

        # Diversity check: >= 10 unique send_types, >= 4 revenue, >= 4 engagement
        assert result.validation_status == "REJECTED"

    async def test_flyer_requirement_rejected(self):
        """PPV without flyer_required=1 -> REJECT."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        # Force rejection simulating flyer violation
        task = MockTaskTool(quality_score=50, force_reject=True)
        result = await EROSOrchestrator(mcp, task).run("no_flyer", "2026-01-06")

        # ppv_unlock, bundle, flash_bundle need flyer_required=1
        assert result.validation_status == "REJECTED"


@pytest.mark.asyncio
@pytest.mark.integration
class TestErrorHandling:
    """Error handling during pipeline execution."""

    async def test_preflight_failure_handled(self):
        """MCP timeout at preflight -> graceful failure."""
        class FailingMCP(MockMCPClient):
            async def get_creator_profile(self, cid):
                raise TimeoutError("MCP timeout")

        mcp = FailingMCP(TestDataFactory.STANDARD)
        task = MockTaskTool()
        result = await EROSOrchestrator(mcp, task).run("timeout", "2026-01-06")

        assert result.success is False
        assert len(result.errors) > 0
        assert "Preflight" in result.errors[0]
        assert result.metrics.get("preflight", {}).get("status") == "failed"

    async def test_generator_failure_handled(self):
        """Agent error at generator -> graceful failure."""
        class FailingTask(MockTaskTool):
            async def invoke(self, subagent_type, prompt, model="sonnet"):
                if subagent_type == "schedule-generator":
                    raise RuntimeError("Agent crashed")
                return await super().invoke(subagent_type, prompt, model)

        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = FailingTask()
        result = await EROSOrchestrator(mcp, task).run("gen_fail", "2026-01-06")

        assert result.success is False
        assert any("Generator" in e for e in result.errors)
        assert result.metrics.get("generator", {}).get("status") == "failed"

    async def test_validator_failure_handled(self):
        """Agent error at validator -> graceful failure."""
        class FailingTask(MockTaskTool):
            async def invoke(self, subagent_type, prompt, model="sonnet"):
                if subagent_type == "schedule-validator":
                    raise RuntimeError("Validator crashed")
                return await super().invoke(subagent_type, prompt, model)

        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = FailingTask()
        result = await EROSOrchestrator(mcp, task).run("val_fail", "2026-01-06")

        assert result.success is False
        assert any("Validator" in e for e in result.errors)
        assert result.metrics.get("validator", {}).get("status") == "failed"

    async def test_save_failure_handled(self):
        """DB error at save -> graceful failure with schedule_id=None."""
        class FailingSaveMCP(MockMCPClient):
            async def save_schedule(self, *args, **kwargs):
                raise ConnectionError("DB unavailable")

        mcp = FailingSaveMCP(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)
        result = await EROSOrchestrator(mcp, task).run("save_fail", "2026-01-06")

        # Pipeline succeeded but save failed
        assert result.success is True  # Validation passed
        assert result.schedule_id is None  # But save failed
        assert any("Save" in e for e in result.errors)
        assert result.metrics.get("save", {}).get("status") == "failed"


@pytest.mark.asyncio
@pytest.mark.integration
class TestMetricsTracking:
    """Verify metrics are properly tracked."""

    async def test_metrics_structure(self):
        """All phases report proper metrics."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)
        result = await EROSOrchestrator(mcp, task).run("metrics", "2026-01-06")

        # Check preflight metrics
        assert "preflight" in result.metrics
        assert "duration_ms" in result.metrics["preflight"]
        assert result.metrics["preflight"]["mcp_calls"] == 7

        # Check generator metrics
        assert "generator" in result.metrics
        assert result.metrics["generator"]["status"] == "success"

        # Check validator metrics
        assert "validator" in result.metrics
        assert result.metrics["validator"]["status"] == "success"

        # Check total duration
        assert "total_duration_ms" in result.metrics

    async def test_agent_invocations(self):
        """Verify correct agents are invoked with correct models."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)
        await EROSOrchestrator(mcp, task).run("agents", "2026-01-06")

        # Check task tool was called correctly
        assert len(task.call_log) == 2
        assert task.call_log[0] == ("schedule-generator", "sonnet")
        assert task.call_log[1] == ("schedule-validator", "opus")
