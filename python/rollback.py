"""EROS v1.0 Automated Rollback System (<80 lines).

Triggers:
1. Manual: Operator sets EROS_V5_ENABLED=false
2. Automatic: Monitoring thresholds exceeded
3. Graceful: Complete in-flight requests before rollback

Procedure: DETECT -> PAUSE -> DRAIN -> DISABLE -> ALERT -> LOG -> VERIFY
"""
from __future__ import annotations
import asyncio, json, logging, os, time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .monitoring import PipelineMonitor

logger = logging.getLogger("eros.rollback")

class RollbackState(Enum):
    ACTIVE = "active"; PAUSED = "paused"; DRAINING = "draining"; DISABLED = "disabled"

@dataclass
class RollbackEvent:
    timestamp: str; reason: str; metrics_snapshot: dict
    initiated_by: str = "automatic"; drain_duration_ms: float = 0

@dataclass
class RollbackResult:
    success: bool; state: RollbackState; reason: str
    event: RollbackEvent | None = None; error: str | None = None

class RollbackController:
    """Automated rollback with graceful drain."""
    def __init__(self, monitor: "PipelineMonitor" = None, drain_timeout: float = 60.0):
        self.monitor = monitor
        self.drain_timeout = drain_timeout
        self.state = RollbackState.ACTIVE
        self.in_flight = 0
        self.history: list[RollbackEvent] = []
        self._lock = asyncio.Lock()

    def acquire_request(self) -> bool:
        """Track in-flight request. Returns False if draining/disabled."""
        if self.state in (RollbackState.DRAINING, RollbackState.DISABLED):
            return False
        self.in_flight += 1
        return True

    def release_request(self) -> None:
        self.in_flight = max(0, self.in_flight - 1)

    async def execute_rollback(self, reason: str, initiated_by: str = "automatic") -> RollbackResult:
        """Execute graceful rollback: pause, drain, disable."""
        async with self._lock:
            if self.state == RollbackState.DISABLED:
                return RollbackResult(False, self.state, "already_disabled")

            # 1. PAUSE - Stop accepting new v5 requests
            self.state = RollbackState.PAUSED
            logger.warning(f"Rollback initiated: {reason} (by: {initiated_by})")

            # 2. DRAIN - Wait for in-flight requests
            self.state = RollbackState.DRAINING
            drain_start = time.time()
            while self.in_flight > 0 and (time.time() - drain_start) < self.drain_timeout:
                await asyncio.sleep(0.5)
            drain_ms = (time.time() - drain_start) * 1000

            # 3. DISABLE - Set feature flag
            os.environ["EROS_V5_ENABLED"] = "false"
            self.state = RollbackState.DISABLED

            # 4. LOG - Record event
            metrics = self.monitor.get_status() if self.monitor else {}
            event = RollbackEvent(datetime.now().isoformat(), reason, metrics, initiated_by, drain_ms)
            self.history.append(event)
            logger.critical(f"Rollback complete: {json.dumps({'reason': reason, 'drain_ms': drain_ms, 'in_flight_remaining': self.in_flight})}")

            return RollbackResult(True, self.state, reason, event)

    async def restore_v5(self, confirmation: str) -> RollbackResult:
        """Restore v5 routing (requires explicit confirmation)."""
        if confirmation != "RESTORE_V5_CONFIRMED":
            return RollbackResult(False, self.state, "invalid_confirmation")
        async with self._lock:
            os.environ["EROS_V5_ENABLED"] = "true"
            self.state = RollbackState.ACTIVE
            logger.info("V5 routing restored")
            return RollbackResult(True, self.state, "restored")

    async def check_auto_rollback(self) -> RollbackResult | None:
        """Check if automatic rollback should trigger."""
        if not self.monitor or self.state != RollbackState.ACTIVE:
            return None
        should_rollback, reason = self.monitor.should_rollback()
        if should_rollback:
            return await self.execute_rollback(reason, "automatic")
        return None

    def get_history(self) -> list[dict]:
        return [{"timestamp": e.timestamp, "reason": e.reason, "initiated_by": e.initiated_by,
                 "drain_ms": e.drain_duration_ms} for e in self.history]

__all__ = ["RollbackController", "RollbackState", "RollbackEvent", "RollbackResult"]
