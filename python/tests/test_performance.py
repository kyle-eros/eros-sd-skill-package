"""Performance benchmarks for EROS v1.0 Pipeline (<100 lines)."""
from __future__ import annotations
import asyncio
import time
import tracemalloc
import pytest
from ..orchestrator import EROSOrchestrator
from ..preflight import PreflightEngine
from .mocks import MockMCPClient, MockTaskTool, TestDataFactory


@pytest.mark.asyncio
@pytest.mark.benchmark
class TestPerformance:
    """Performance benchmarks against v1.0 targets."""

    async def test_preflight_under_2_seconds(self):
        """Phase 1 target: Preflight < 2 seconds."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        engine = PreflightEngine(mcp)

        start = time.perf_counter()
        ctx = await engine.execute("alexia", "2026-01-06")
        duration = time.perf_counter() - start

        assert duration < 2.0, f"Preflight took {duration:.2f}s, target < 2s"
        assert ctx.preflight_duration_ms < 2000

    async def test_full_pipeline_under_90_seconds(self):
        """Total target: Full pipeline < 90 seconds."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)

        start = time.perf_counter()
        result = await EROSOrchestrator(mcp, task).run("alexia", "2026-01-06")
        duration = time.perf_counter() - start

        assert duration < 90.0, f"Pipeline took {duration:.2f}s, target < 90s"
        assert result.success is True
        # With mocks, should be sub-second
        assert result.metrics["total_duration_ms"] < 5000

    async def test_mcp_call_count(self):
        """Target: ~8 MCP calls (vs v4.0: 50+)."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)

        mcp.call_log.clear()
        await EROSOrchestrator(mcp, task).run("alexia", "2026-01-06")

        # Preflight: 4 calls (bundled get_creator_profile) + save: 1 call = 5 total from orchestrator
        # Generator/validator agent calls tracked separately
        # v1.1.0: Reduced from 7 to 4 preflight calls via bundled get_creator_profile
        assert len(mcp.call_log) <= 8, f"MCP calls: {len(mcp.call_log)}, target <= 8"
        print(f"\nMCP Calls Made: {len(mcp.call_log)}")
        print(f"Call Breakdown: {mcp.call_log}")

    async def test_memory_usage(self):
        """No memory leaks in context - should stay under 50MB."""
        tracemalloc.start()

        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)

        # Run multiple iterations
        for i in range(10):
            await EROSOrchestrator(mcp, task).run("alexia", "2026-01-06")

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024
        assert peak_mb < 50, f"Peak memory {peak_mb:.2f}MB, target < 50MB"
        print(f"\nPeak Memory: {peak_mb:.2f}MB")


@pytest.mark.asyncio
@pytest.mark.benchmark
class TestPhaseTimings:
    """Detailed phase-by-phase timing analysis."""

    async def test_phase_breakdown(self):
        """Report timing breakdown for each phase."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        task = MockTaskTool(quality_score=90)

        result = await EROSOrchestrator(mcp, task).run("alexia", "2026-01-06")
        metrics = result.metrics

        print("\n=== Phase Timing Breakdown ===")
        for phase in ["preflight", "generator", "validator", "save"]:
            if phase in metrics:
                ms = metrics[phase].get("duration_ms", 0)
                calls = metrics[phase].get("mcp_calls", 0)
                print(f"{phase:12}: {ms:8.1f}ms | MCP calls: {calls}")

        print(f"{'TOTAL':12}: {metrics.get('total_duration_ms', 0):8.1f}ms")

        # Verify all phases completed
        assert metrics["preflight"]["status"] == "success"
        assert metrics["generator"]["status"] == "success"
        assert metrics["validator"]["status"] == "success"


@pytest.mark.asyncio
@pytest.mark.benchmark
class TestScalability:
    """Test performance across different creator profiles."""

    async def test_all_creator_types(self):
        """Benchmark across STANDARD, HIGH_VALUE, FREE page creators."""
        results = {}

        for name in ["STANDARD", "HIGH_VALUE", "FREE_PAGE"]:
            cfg = TestDataFactory.get_config(name)
            mcp = MockMCPClient(cfg)
            task = MockTaskTool(quality_score=90)

            start = time.perf_counter()
            result = await EROSOrchestrator(mcp, task).run(cfg.creator_id, "2026-01-06")
            duration = time.perf_counter() - start

            results[name] = {"duration": duration, "success": result.success}

        print("\n=== Creator Type Benchmark ===")
        for name, data in results.items():
            print(f"{name:15}: {data['duration']*1000:.1f}ms | Success: {data['success']}")

        # All should complete quickly with mocks
        for name, data in results.items():
            assert data["duration"] < 1.0, f"{name} took too long"
