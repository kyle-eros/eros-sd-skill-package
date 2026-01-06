"""EROS v1.0 Python modules - Minimal 3-phase schedule generation with production migration."""
from .preflight import CreatorContext, PreflightEngine
from .orchestrator import EROSOrchestrator, PipelineResult, generate_schedule
from .router import PipelineRouter, FeatureFlags, RoutingDecision, Pipeline
from .comparator import ComparisonResult, compare, run_shadow_comparison, get_metrics
from .monitoring import PipelineMonitor, PipelineMetrics, SLOConfig, HealthStatus
from .rollback import RollbackController, RollbackState, RollbackResult
from .adapters import ProductionMCPClient, ProductionTaskTool, create_production_adapters
from .rollout import RolloutManager, Phase, PhaseCriteria, PhaseResult
from .feedback import FeedbackCapture, LearningSignal
from .performance_tracker import PerformanceTracker, SchedulePerformance

__all__ = [
    # Core pipeline
    "CreatorContext", "PreflightEngine",
    "EROSOrchestrator", "PipelineResult", "generate_schedule",
    # Router
    "PipelineRouter", "FeatureFlags", "RoutingDecision", "Pipeline",
    # Comparator
    "ComparisonResult", "compare", "run_shadow_comparison", "get_metrics",
    # Monitoring
    "PipelineMonitor", "PipelineMetrics", "SLOConfig", "HealthStatus",
    # Rollback
    "RollbackController", "RollbackState", "RollbackResult",
    # Adapters
    "ProductionMCPClient", "ProductionTaskTool", "create_production_adapters",
    # Rollout
    "RolloutManager", "Phase", "PhaseCriteria", "PhaseResult",
    # Feedback
    "FeedbackCapture", "LearningSignal",
    # Performance Tracking
    "PerformanceTracker", "SchedulePerformance",
]
__version__ = "5.1.0"
