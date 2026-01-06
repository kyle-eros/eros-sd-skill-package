"""EROS v1.0 Test Configuration - Shared fixtures and hooks."""
from __future__ import annotations
import os
import pytest
from .mocks import MockMCPClient, MockTaskTool, TestDataFactory, CreatorConfig


# --- Pytest Configuration ---
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "requires_mcp: marks tests requiring live MCP connection")
    config.addinivalue_line("markers", "benchmark: marks tests as performance benchmarks")


def pytest_collection_modifyitems(config, items):
    """Skip tests based on markers and environment."""
    skip_mcp = pytest.mark.skip(reason="MCP connection not available")
    for item in items:
        if "requires_mcp" in item.keywords:
            if not os.environ.get("EROS_MCP_AVAILABLE"):
                item.add_marker(skip_mcp)


# --- Common Fixtures ---
@pytest.fixture
def standard_config() -> CreatorConfig:
    """Standard tier creator configuration."""
    return TestDataFactory.STANDARD


@pytest.fixture
def high_value_config() -> CreatorConfig:
    """High value tier creator configuration."""
    return TestDataFactory.HIGH_VALUE


@pytest.fixture
def free_page_config() -> CreatorConfig:
    """Free page creator configuration."""
    return TestDataFactory.FREE_PAGE


@pytest.fixture
def mock_mcp(standard_config: CreatorConfig) -> MockMCPClient:
    """Mock MCP client with standard config."""
    return MockMCPClient(standard_config)


@pytest.fixture
def mock_task_tool() -> MockTaskTool:
    """Mock Task tool with default settings."""
    return MockTaskTool(quality_score=90)


@pytest.fixture
def week_start() -> str:
    """Default week start date for tests."""
    return "2026-01-06"


# --- Async Fixtures ---
@pytest.fixture
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


# --- Test Output Helpers ---
@pytest.fixture
def report_metrics(request):
    """Fixture for reporting test metrics."""
    metrics = {}
    yield metrics
    if metrics:
        print(f"\n--- Test Metrics: {request.node.name} ---")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
