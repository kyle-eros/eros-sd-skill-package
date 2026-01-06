#!/bin/bash
# EROS v5.0 Test Runner
# Usage: ./run_tests.sh [mode]
# Modes: unit, integration, mcp, benchmark, full, coverage

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "EROS v5.0 Test Suite"
echo "========================================"

MODE="${1:-unit}"

case "$MODE" in
    unit)
        echo -e "${GREEN}Running unit tests (no integration, no MCP)...${NC}"
        python -m pytest tests/ -m "not integration and not requires_mcp" -v
        ;;
    integration)
        echo -e "${GREEN}Running integration tests (with mocks)...${NC}"
        python -m pytest tests/ -m "integration and not requires_mcp" -v
        ;;
    mcp)
        echo -e "${YELLOW}Running real creator tests (requires MCP)...${NC}"
        export EROS_MCP_AVAILABLE=1
        python -m pytest tests/ -m "requires_mcp" -v
        ;;
    benchmark)
        echo -e "${GREEN}Running performance benchmarks...${NC}"
        python -m pytest tests/ -m "benchmark" -v -s
        ;;
    full)
        echo -e "${GREEN}Running full test suite...${NC}"
        python -m pytest tests/ -v
        ;;
    coverage)
        echo -e "${GREEN}Running tests with coverage...${NC}"
        python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing -v
        echo -e "${GREEN}Coverage report: htmlcov/index.html${NC}"
        ;;
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo "Available modes: unit, integration, mcp, benchmark, full, coverage"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo -e "${GREEN}Tests completed!${NC}"
echo "========================================"
