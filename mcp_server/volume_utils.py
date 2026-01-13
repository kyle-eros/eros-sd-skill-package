"""
Volume Configuration Utilities - SINGLE SOURCE OF TRUTH

This module contains all tier thresholds, volume ranges, and calculation
functions used throughout the EROS pipeline. All consumers MUST import
from here to prevent drift.

Consumers:
- mcp_server/main.py: get_volume_config, get_creator_profile
- python/preflight.py: tier constants and calculation functions

Reference: docs/DOMAIN_KNOWLEDGE.md Section 2 (Volume Tiers)
"""
from __future__ import annotations

import calendar
import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Final, Literal, TypedDict

# =============================================================================
# TIER CONSTANTS - THE CANONICAL DEFINITION
# =============================================================================

# Format: tier -> (min_revenue, max_revenue, rev_range, eng_range, ret_range)
TIERS: Final[dict[str, tuple[int, float, tuple[int, int], tuple[int, int], tuple[int, int]]]] = {
    "MINIMAL": (0, 149, (1, 2), (1, 2), (1, 1)),
    "LITE": (150, 799, (2, 4), (2, 4), (1, 2)),
    "STANDARD": (800, 2999, (4, 6), (4, 6), (2, 3)),
    "HIGH_VALUE": (3000, 7999, (6, 9), (5, 8), (2, 4)),
    "PREMIUM": (8000, float("inf"), (8, 12), (6, 10), (3, 5)),
}

# Ordered for hysteresis lookups (lowest to highest)
TIER_ORDER: Final[tuple[str, ...]] = (
    "MINIMAL", "LITE", "STANDARD", "HIGH_VALUE", "PREMIUM"
)

# Hysteresis buffer to prevent tier flip-flopping at boundaries
HYSTERESIS_BUFFER: Final[float] = 0.15  # 15%

# =============================================================================
# CALENDAR CONSTANTS
# =============================================================================

# Fixed holidays (month, day) - return 1.30x boost
HOLIDAYS: Final[frozenset[tuple[int, int]]] = frozenset({
    (1, 1),    # New Year's Day
    (2, 14),   # Valentine's Day
    (7, 4),    # Independence Day
    (10, 31),  # Halloween
    (12, 25),  # Christmas
})

# Payday dates (1st, 15th, last of month) - return 1.20x boost
PAYDAY_DAYS: Final[frozenset[int]] = frozenset({1, 15})  # Last day computed dynamically

# Calendar boost multipliers
HOLIDAY_BOOST: Final[float] = 1.30
PAYDAY_BOOST: Final[float] = 1.20
WEEKEND_BOOST: Final[float] = 1.10

# =============================================================================
# PRIME HOURS BY DAY OF WEEK (STRING KEYS - matches preflight.py)
# =============================================================================

# Prime hours for revenue sends by day name
# Format: day_name -> list of (start_hour, end_hour) tuples
# CRITICAL: Use string keys to match preflight.py pattern
PRIME_HOURS: Final[dict[str, list[tuple[int, int]]]] = {
    "monday": [(12, 14), (19, 22), (10, 11)],
    "tuesday": [(12, 14), (20, 23), (10, 11)],
    "wednesday": [(12, 14), (20, 23), (18, 19)],
    "thursday": [(12, 14), (20, 23), (18, 19)],
    "friday": [(12, 14), (21, 24), (17, 19)],
    "saturday": [(11, 14), (22, 25), (16, 18)],
    "sunday": [(11, 14), (20, 23), (16, 18)],
}

# Day name lookup for weekday() integer -> string
DAY_NAMES: Final[tuple[str, ...]] = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
)

# =============================================================================
# BUMP MULTIPLIERS BY CONTENT CATEGORY
# =============================================================================

BUMP_MULT: Final[dict[str, float]] = {
    "lifestyle": 1.0,
    "softcore": 1.5,
    "amateur": 2.0,
    "explicit": 2.67,
}

# =============================================================================
# HEALTH STATUS THRESHOLDS
# =============================================================================

HealthStatus = Literal["HEALTHY", "WARNING", "DEATH_SPIRAL"]

DEATH_SPIRAL_WEEKS: Final[int] = 4
WARNING_WEEKS: Final[int] = 2
SATURATION_THRESHOLD: Final[int] = 30  # Below this = healthy opportunity

# =============================================================================
# PURE CALCULATION FUNCTIONS
# =============================================================================

def get_tier(revenue: float, previous_tier: str | None = None) -> str:
    """
    Calculate volume tier from monthly MM revenue with 15% hysteresis.

    The hysteresis buffer prevents tier flip-flopping when revenue hovers
    near a boundary. If a previous tier exists and current revenue is within
    15% of that tier's minimum, the previous tier is retained.

    Args:
        revenue: Monthly MM revenue in dollars
        previous_tier: Previous tier assignment (enables hysteresis)

    Returns:
        Tier name: MINIMAL, LITE, STANDARD, HIGH_VALUE, or PREMIUM

    Example:
        >>> get_tier(2500)
        'STANDARD'
        >>> get_tier(750, previous_tier='STANDARD')  # Within 15% of $800
        'STANDARD'  # Hysteresis retains previous tier
        >>> get_tier(600, previous_tier='STANDARD')  # Below 15% buffer
        'LITE'  # Drops to lower tier
    """
    if revenue < 0:
        revenue = 0

    # Calculate tier from revenue thresholds
    calculated_tier = "MINIMAL"
    for tier_name in TIER_ORDER:
        min_rev = TIERS[tier_name][0]
        if revenue >= min_rev:
            calculated_tier = tier_name

    # Apply hysteresis if previous tier exists
    if previous_tier and previous_tier in TIERS:
        prev_idx = TIER_ORDER.index(previous_tier)
        calc_idx = TIER_ORDER.index(calculated_tier)

        # Only apply hysteresis when dropping tiers
        if prev_idx > calc_idx:
            prev_min = TIERS[previous_tier][0]
            buffer_threshold = prev_min * (1 - HYSTERESIS_BUFFER)
            if revenue >= buffer_threshold:
                return previous_tier

    return calculated_tier


def get_tier_ranges(tier: str) -> dict[str, tuple[int, int]]:
    """
    Get volume ranges for a given tier.

    Args:
        tier: Tier name (MINIMAL, LITE, STANDARD, HIGH_VALUE, PREMIUM)

    Returns:
        Dict with 'revenue', 'engagement', 'retention' keys mapping to (min, max) tuples

    Example:
        >>> get_tier_ranges('STANDARD')
        {'revenue': (4, 6), 'engagement': (4, 6), 'retention': (2, 3)}
    """
    if tier not in TIERS:
        tier = "MINIMAL"

    _, _, rev_range, eng_range, ret_range = TIERS[tier]
    return {
        "revenue": rev_range,
        "engagement": eng_range,
        "retention": ret_range,
    }


def calc_calendar_boost(target_date: date) -> float:
    """
    Calculate calendar boost multiplier for a specific date.

    Checks for holidays (1.30x) and paydays (1.20x). If both apply,
    returns the higher boost (not cumulative).

    Args:
        target_date: Date to check for boosts

    Returns:
        Boost multiplier (1.0 if no boost, 1.20 for payday, 1.30 for holiday)

    Example:
        >>> calc_calendar_boost(date(2026, 1, 1))  # New Year's Day
        1.30
        >>> calc_calendar_boost(date(2026, 1, 15))  # Payday
        1.20
        >>> calc_calendar_boost(date(2026, 1, 8))   # Regular day
        1.0
    """
    month_day = (target_date.month, target_date.day)

    # Check for Thanksgiving (4th Thursday of November)
    if target_date.month == 11 and target_date.weekday() == 3:  # Thursday
        # Find the 4th Thursday
        first_day = date(target_date.year, 11, 1)
        first_thursday = (3 - first_day.weekday()) % 7 + 1
        fourth_thursday = first_thursday + 21
        if target_date.day == fourth_thursday:
            return HOLIDAY_BOOST

    # Check for Black Friday (day after Thanksgiving)
    if target_date.month == 11 and target_date.weekday() == 4:  # Friday
        first_day = date(target_date.year, 11, 1)
        first_thursday = (3 - first_day.weekday()) % 7 + 1
        fourth_thursday = first_thursday + 21
        if target_date.day == fourth_thursday + 1:
            return HOLIDAY_BOOST

    # Check fixed holidays
    if month_day in HOLIDAYS:
        return HOLIDAY_BOOST

    # Check paydays (1st, 15th, last day of month)
    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
    if target_date.day in PAYDAY_DAYS or target_date.day == last_day:
        return PAYDAY_BOOST

    return 1.0


def calc_weekend_boost(target_date: date) -> float:
    """
    Calculate weekend boost multiplier.

    Friday, Saturday, Sunday get a 1.1x boost for revenue/engagement.

    Args:
        target_date: Date to check

    Returns:
        1.1 for Fri/Sat/Sun, 1.0 for Mon-Thu
    """
    # weekday(): 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
    if target_date.weekday() >= 4:  # Friday or later
        return WEEKEND_BOOST
    return 1.0


def calc_bump_multiplier(content_category: str, tier: str) -> float:
    """
    Calculate bump volume multiplier based on content category and tier.

    MINIMAL tier allows full category multiplier. Other tiers cap at 1.5x.

    Args:
        content_category: Creator's content category (lifestyle, softcore, amateur, explicit)
        tier: Current volume tier

    Returns:
        Bump multiplier (1.0 to 2.67 depending on category and tier)

    Example:
        >>> calc_bump_multiplier('explicit', 'MINIMAL')
        2.67
        >>> calc_bump_multiplier('explicit', 'STANDARD')
        1.5  # Capped for non-MINIMAL tiers
    """
    base_mult = BUMP_MULT.get(content_category, 1.5)

    # MINIMAL tier gets full multiplier, others capped at 1.5
    if tier != "MINIMAL":
        base_mult = min(base_mult, 1.5)

    return base_mult


def calc_health_status(
    saturation_score: int | None,
    decline_weeks: int | None
) -> dict[str, int | str]:
    """
    Calculate health status and volume adjustment from performance metrics.

    Matches preflight.py _calc_health() logic exactly.

    Args:
        saturation_score: Fused saturation score (0-100, None if unavailable)
        decline_weeks: Consecutive weeks of declining performance

    Returns:
        Dict with 'status' (HEALTHY/WARNING/DEATH_SPIRAL) and 'volume_adjustment' (int)

    Example:
        >>> calc_health_status(saturation_score=25, decline_weeks=0)
        {'status': 'HEALTHY', 'volume_adjustment': 1}
        >>> calc_health_status(saturation_score=50, decline_weeks=5)
        {'status': 'DEATH_SPIRAL', 'volume_adjustment': -1}
    """
    sat = saturation_score if saturation_score is not None else 50
    weeks = decline_weeks if decline_weeks is not None else 0

    # Determine status and adjustment (matches preflight.py exactly)
    if weeks >= DEATH_SPIRAL_WEEKS:
        status: HealthStatus = "DEATH_SPIRAL"
        volume_adjustment = -1  # Reduce volume in death spiral
    elif weeks >= WARNING_WEEKS:
        status = "WARNING"
        volume_adjustment = 0
    else:
        status = "HEALTHY"
        # +1 if healthy AND low saturation (opportunity to increase)
        volume_adjustment = 1 if sat < SATURATION_THRESHOLD else 0

    return {
        "status": status,
        "volume_adjustment": volume_adjustment,
    }


def calc_consecutive_decline_weeks(weekly_earnings: list[dict]) -> int:
    """
    Calculate consecutive weeks of declining revenue from most recent week.

    Args:
        weekly_earnings: List of dicts with 'week' and 'weekly_earnings' keys,
                        ordered DESC (most recent first)

    Returns:
        Count of consecutive declining weeks (0 if no decline or insufficient data)

    Example:
        >>> data = [{"week": "2026-02", "weekly_earnings": 900},
        ...         {"week": "2026-01", "weekly_earnings": 1000}]
        >>> calc_consecutive_decline_weeks(data)
        1
    """
    if len(weekly_earnings) < 2:
        return 0

    decline = 0
    for i in range(len(weekly_earnings) - 1):
        curr = weekly_earnings[i].get("weekly_earnings") or 0
        prev = weekly_earnings[i + 1].get("weekly_earnings") or 0
        if curr < prev:
            decline += 1
        else:
            break  # Consecutive chain broken
    return decline


def compute_volume_config_hash(
    tier: str,
    trigger_multiplier: float,
    health_adjustment: int,
    week_start: str,
    boost_dates: list[str]
) -> str:
    """
    Compute deterministic hash for volume configuration audit trail.

    Args:
        tier: Volume tier
        trigger_multiplier: Compound trigger multiplier
        health_adjustment: Health-based volume adjustment
        week_start: Week start date (YYYY-MM-DD)
        boost_dates: List of dates with calendar boosts

    Returns:
        Hash string in format "sha256:<16-char-hex>"

    Example:
        >>> compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", ["2026-01-01"])
        'sha256:abc123def456...'
    """
    config_input = (
        f"{tier}|{trigger_multiplier}|{health_adjustment}|"
        f"{week_start}|{','.join(sorted(boost_dates))}"
    )
    hash_hex = hashlib.sha256(config_input.encode()).hexdigest()[:16]
    return f"sha256:{hash_hex}"


def get_week_dates(week_start: str) -> list[date]:
    """
    Generate list of 7 dates for a week starting from week_start.

    Args:
        week_start: Start date in YYYY-MM-DD format

    Returns:
        List of 7 date objects
    """
    start = date.fromisoformat(week_start)
    return [start + timedelta(days=i) for i in range(7)]


def get_day_name(target_date: date) -> str:
    """
    Get lowercase day name for a date.

    Args:
        target_date: Date object

    Returns:
        Day name string: 'monday', 'tuesday', etc.
    """
    return DAY_NAMES[target_date.weekday()]


# =============================================================================
# TRIGGER SYSTEM CONSTANTS - SINGLE SOURCE OF TRUTH
# =============================================================================

TRIGGER_MULT_MIN: Final[float] = 0.50
TRIGGER_MULT_MAX: Final[float] = 2.00
TRIGGER_DEFAULT_TTL_DAYS: Final[int] = 7

VALID_TRIGGER_TYPES: Final[frozenset] = frozenset({
    "HIGH_PERFORMER",
    "TRENDING_UP",
    "EMERGING_WINNER",
    "SATURATING",
    "AUDIENCE_FATIGUE"
})

# Scale-aware detection thresholds (conversion-first, not RPS-first)
# Reference: docs/DOMAIN_KNOWLEDGE.md Section 8
TRIGGER_THRESHOLDS: Final[dict] = {
    "HIGH_PERFORMER": {
        "min_conversion": 6.0,  # PRIMARY - scale-independent
        "min_weekly_revenue_percentile": 80,  # OR top 20% of own history
        "min_rps_normalized": 1.5,  # Per 1k fans (secondary)
        "multiplier": 1.20
    },
    "TRENDING_UP": {
        "min_wow_revenue_change": 15,  # Week-over-week revenue growth
        "min_wow_conversion_change": 10,  # OR conversion improving
        "multiplier": 1.10
    },
    "EMERGING_WINNER": {
        "min_conversion": 5.0,  # Good conversion
        "max_uses_30d": 3,  # Underutilized
        "min_rps_normalized": 1.0,
        "multiplier": 1.30
    },
    "SATURATING": {
        "min_decline_days": 3,  # Declining conversion days
        "metric": "conversion_rate",
        "multiplier": 0.85
    },
    "AUDIENCE_FATIGUE": {
        "max_open_rate_change": -10,  # Open rate dropped
        "max_conversion_change": -15,  # OR conversion dropped
        "multiplier": 0.75
    },
}

CONFIDENCE_THRESHOLDS: Final[dict] = {
    "high": 10,      # > 10 sends analyzed
    "moderate": 5,   # 5-10 sends
    "low": 0         # < 5 sends
}

ZERO_TRIGGER_REASONS: Final[dict] = {
    "all_expired": "All triggers have passed their expires_at",
    "never_had_triggers": "No trigger history for this creator",
    "all_inactive": "Triggers exist but all marked is_active=0",
    "creator_new": "Creator has < 7 days of performance data",
    "no_qualifying_performance": "Historical triggers but none currently active"
}


class TriggerInput(TypedDict, total=False):
    """Input schema for save_volume_triggers validation."""
    trigger_type: Literal["HIGH_PERFORMER", "TRENDING_UP", "EMERGING_WINNER", "SATURATING", "AUDIENCE_FATIGUE"]
    content_type: str
    adjustment_multiplier: float
    confidence: Literal["low", "moderate", "high"]
    reason: str
    expires_at: str
    metrics_json: dict


def validate_trigger(trigger: dict, index: int = 0) -> tuple[bool, dict | str]:
    """
    Validate and normalize a trigger object for save_volume_triggers.

    Args:
        trigger: Raw trigger dict from caller
        index: Position in batch for error messages

    Returns:
        (True, normalized_trigger) on success
        (False, error_message) on validation failure

    Validation Tiers:
        STRICT (reject): trigger_type, content_type, adjustment_multiplier
        LENIENT (default): confidence, reason, expires_at, metrics_json
    """
    errors = []
    warnings = []

    # TIER 1: Required fields - strict reject
    trigger_type = trigger.get("trigger_type")
    if not trigger_type:
        errors.append(f"trigger[{index}]: missing required field 'trigger_type'")
    elif trigger_type not in VALID_TRIGGER_TYPES:
        errors.append(f"trigger[{index}]: invalid trigger_type '{trigger_type}', must be one of {VALID_TRIGGER_TYPES}")

    content_type = trigger.get("content_type")
    if not content_type or not str(content_type).strip():
        errors.append(f"trigger[{index}]: missing required field 'content_type'")

    multiplier = trigger.get("adjustment_multiplier")
    if multiplier is None:
        errors.append(f"trigger[{index}]: missing required field 'adjustment_multiplier'")
    elif not isinstance(multiplier, (int, float)):
        errors.append(f"trigger[{index}]: adjustment_multiplier must be numeric, got {type(multiplier).__name__}")
    elif not (TRIGGER_MULT_MIN <= multiplier <= TRIGGER_MULT_MAX):
        errors.append(f"trigger[{index}]: adjustment_multiplier {multiplier} outside valid range [{TRIGGER_MULT_MIN}, {TRIGGER_MULT_MAX}]")

    # Fail fast on required field errors
    if errors:
        return (False, "; ".join(errors))

    # TIER 2: Optional fields - coerce/default
    confidence = trigger.get("confidence", "moderate")
    if confidence not in ("low", "moderate", "high"):
        confidence = "moderate"
        warnings.append(f"trigger[{index}]: invalid confidence '{trigger.get('confidence')}', defaulting to 'moderate'")

    reason = str(trigger.get("reason", ""))[:500]  # Truncate to max length

    expires_at = trigger.get("expires_at")
    if not expires_at:
        expires_at = (datetime.now() + timedelta(days=TRIGGER_DEFAULT_TTL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    metrics_json = trigger.get("metrics_json", {})
    if not isinstance(metrics_json, dict):
        metrics_json = {}
        warnings.append(f"trigger[{index}]: invalid metrics_json type, defaulting to empty")

    # TIER 3: Warnings for suspicious values (don't reject)
    if multiplier < 0.70 or multiplier > 1.50:
        warnings.append(f"trigger[{index}]: extreme multiplier {multiplier} - verify intentional")

    if not metrics_json:
        warnings.append(f"trigger[{index}]: missing metrics_json - detection evidence not recorded")

    # Return normalized trigger
    normalized = {
        "trigger_type": trigger_type,
        "content_type": content_type.strip(),
        "adjustment_multiplier": round(float(multiplier), 4),
        "confidence": confidence,
        "reason": reason,
        "expires_at": expires_at,
        "metrics_json": metrics_json,
        "_warnings": warnings if warnings else None
    }

    return (True, normalized)


def calculate_compound_multiplier(triggers: list[dict]) -> tuple[float, list[dict], bool]:
    """
    Calculate compound multiplier with per-content-type grouping.

    Args:
        triggers: List of trigger dicts with content_type and adjustment_multiplier

    Returns:
        (global_compound, compound_calculation, has_conflicting_signals)

    Example:
        >>> triggers = [
        ...     {"content_type": "lingerie", "trigger_type": "HIGH_PERFORMER", "adjustment_multiplier": 1.2},
        ...     {"content_type": "lingerie", "trigger_type": "SATURATING", "adjustment_multiplier": 0.85}
        ... ]
        >>> calculate_compound_multiplier(triggers)
        (1.02, [{"content_type": "lingerie", "compound": 1.02, "clamped": False}], True)
    """
    from collections import defaultdict

    if not triggers:
        return (1.0, [], False)

    by_content_type = defaultdict(list)
    for t in triggers:
        by_content_type[t.get("content_type", "_unknown")].append(t)

    compound_calculation = []
    has_conflict = False

    for ct, ct_triggers in by_content_type.items():
        boost = [t for t in ct_triggers if t.get("adjustment_multiplier", 1.0) > 1.0]
        reduce = [t for t in ct_triggers if t.get("adjustment_multiplier", 1.0) < 1.0]

        if boost and reduce:
            has_conflict = True

        compound = 1.0
        trigger_strs = []
        for t in ct_triggers:
            mult = t.get("adjustment_multiplier", 1.0)
            compound *= mult
            trigger_strs.append(f"{t.get('trigger_type', 'UNKNOWN')}:{mult}")

        # Clamp to bounds
        clamped = False
        if compound < TRIGGER_MULT_MIN:
            compound = TRIGGER_MULT_MIN
            clamped = True
        elif compound > TRIGGER_MULT_MAX:
            compound = TRIGGER_MULT_MAX
            clamped = True

        compound_calculation.append({
            "content_type": ct,
            "triggers": trigger_strs,
            "compound": round(compound, 4),
            "clamped": clamped
        })

    # Global compound (multiply all per-content-type compounds)
    global_compound = 1.0
    for calc in compound_calculation:
        global_compound *= calc["compound"]
    global_compound = max(TRIGGER_MULT_MIN, min(TRIGGER_MULT_MAX, round(global_compound, 4)))

    return (global_compound, compound_calculation, has_conflict)


# =============================================================================
# SCHEDULE VALIDATION FUNCTIONS (for save_schedule v2.0.0)
# =============================================================================

SCHEDULE_ITEM_REQUIRED_KEYS: Final[frozenset[str]] = frozenset({
    "send_type_key", "scheduled_date", "scheduled_time"
})

SCHEDULE_DATE_REGEX: Final[re.Pattern] = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCHEDULE_TIME_REGEX: Final[re.Pattern] = re.compile(r"^\d{2}:\d{2}$")

SCHEDULE_PRICE_MIN: Final[float] = 5.0
SCHEDULE_PRICE_MAX: Final[float] = 50.0


class ScheduleItemInput(TypedDict, total=False):
    """Input schema for schedule item validation."""
    send_type_key: str
    scheduled_date: str
    scheduled_time: str
    content_type: str
    price: float
    caption_id: int
    flyer_required: int


def validate_schedule_items(items: list) -> tuple[bool, list[str]]:
    """
    Validate schedule items for structural correctness before persistence.

    Performs STRUCTURAL validation only - does not validate business rules
    (that's the Validator agent's job).

    Args:
        items: List of schedule item dictionaries

    Returns:
        (True, []) on success
        (False, [error1, ...]) on failure
    """
    if not items:
        return (False, ["items list is empty"])

    if not isinstance(items, list):
        return (False, [f"items must be a list, got {type(items).__name__}"])

    errors: list[str] = []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"item[{idx}]: must be a dict, got {type(item).__name__}")
            continue

        # Check required keys
        missing_keys = SCHEDULE_ITEM_REQUIRED_KEYS - set(item.keys())
        if missing_keys:
            errors.append(f"item[{idx}]: missing required keys: {', '.join(sorted(missing_keys))}")
            continue

        # Validate date format
        scheduled_date = item.get("scheduled_date", "")
        if not SCHEDULE_DATE_REGEX.match(str(scheduled_date)):
            errors.append(f"item[{idx}]: scheduled_date '{scheduled_date}' must match YYYY-MM-DD")

        # Validate time format
        scheduled_time = item.get("scheduled_time", "")
        if not SCHEDULE_TIME_REGEX.match(str(scheduled_time)):
            errors.append(f"item[{idx}]: scheduled_time '{scheduled_time}' must match HH:MM")

        # Validate price bounds (if present)
        if "price" in item and item["price"] is not None:
            try:
                price = float(item["price"])
                if not (SCHEDULE_PRICE_MIN <= price <= SCHEDULE_PRICE_MAX):
                    errors.append(
                        f"item[{idx}]: price {price} outside bounds "
                        f"[{SCHEDULE_PRICE_MIN}, {SCHEDULE_PRICE_MAX}]"
                    )
            except (TypeError, ValueError):
                errors.append(f"item[{idx}]: price must be numeric, got {type(item['price']).__name__}")

        # Validate flyer_required (if present)
        if "flyer_required" in item and item["flyer_required"] is not None:
            flyer = item["flyer_required"]
            if flyer not in (0, 1, True, False):
                errors.append(f"item[{idx}]: flyer_required must be 0 or 1, got {flyer}")

    return (len(errors) == 0, errors)


def validate_certificate_freshness(
    certificate: dict | None,
    max_age_seconds: int = 300,
    tolerance_seconds: int = 30
) -> tuple[bool, str | None]:
    """
    Validate that a ValidationCertificate is fresh enough for persistence.

    SOFT GATE: Expired certificates don't reject - they downgrade status to 'draft'.

    Args:
        certificate: ValidationCertificate dict or None
        max_age_seconds: Maximum allowed age (default 300 = 5 minutes)
        tolerance_seconds: Future timestamp tolerance (default 30s for clock skew)

    Returns:
        (True, None) - Certificate is fresh or not provided
        (False, error_message) - Certificate is stale/invalid
    """
    if not certificate:
        return (True, None)

    timestamp_str = certificate.get("validation_timestamp")
    if not timestamp_str:
        return (False, "certificate missing validation_timestamp")

    try:
        if isinstance(timestamp_str, str):
            timestamp_str = timestamp_str.replace("Z", "+00:00")
            cert_time = datetime.fromisoformat(timestamp_str)
        else:
            return (False, f"validation_timestamp must be string, got {type(timestamp_str).__name__}")

        now = datetime.now(cert_time.tzinfo) if cert_time.tzinfo else datetime.now()
        age_seconds = (now - cert_time).total_seconds()

        if age_seconds < -tolerance_seconds:
            return (False, f"certificate timestamp is {abs(age_seconds):.0f}s in the future")

        if age_seconds > max_age_seconds:
            return (False, f"certificate expired (age: {age_seconds:.0f}s > {max_age_seconds}s)")

    except ValueError as e:
        return (False, f"certificate has invalid timestamp format: {e}")

    return (True, None)


def compute_schedule_hash(items: list) -> str:
    """
    Compute deterministic hash of schedule items for audit trail.

    Args:
        items: List of schedule item dictionaries

    Returns:
        Hash string in format "sha256:{16-char-hex}"
    """
    if not items:
        return "sha256:empty"

    sorted_items = sorted(
        items,
        key=lambda x: (x.get("scheduled_date", ""), x.get("scheduled_time", ""))
    )

    hash_components: list[str] = []
    for item in sorted_items:
        components = [
            str(item.get("send_type_key", "")),
            str(item.get("scheduled_date", "")),
            str(item.get("scheduled_time", "")),
            str(item.get("content_type", "")),
            str(item.get("price", "")),
            str(item.get("caption_id", ""))
        ]
        hash_components.append("|".join(components))

    hash_input = "\n".join(hash_components).encode("utf-8")
    hash_digest = hashlib.sha256(hash_input).hexdigest()[:16]

    return f"sha256:{hash_digest}"


# =============================================================================
# CAPTION TOOL CONSTANTS (added for get_batch_captions_by_content_types v2.0)
# =============================================================================

CAPTION_TIER_LABELS: Final[dict[int, str]] = {
    1: "ELITE",
    2: "PROVEN",
    3: "STANDARD",
    4: "UNPROVEN"
}

CAPTION_TIER_SCORES: Final[dict[int, int]] = {
    1: 100,
    2: 75,
    3: 50,
    4: 25
}

EFFECTIVELY_FRESH_DAYS: Final[int] = 90

CAPTION_TOOL_ERROR_CODES: Final[frozenset] = frozenset({
    "INVALID_CREATOR_ID",
    "INVALID_CREATOR_ID_FORMAT",
    "CREATOR_NOT_FOUND",
    "INVALID_CONTENT_TYPES",
    "EMPTY_CONTENT_TYPES",
    "CONTENT_TYPES_LIMIT_EXCEEDED",
    "INVALID_CONTENT_TYPE_ELEMENTS",
    "INVALID_SCHEDULABLE_TYPE",
    "DATABASE_ERROR"
})

VALID_SCHEDULABLE_TYPES: Final[frozenset] = frozenset({'ppv', 'ppv_bump', 'wall'})

MAX_CONTENT_TYPES: Final[int] = 50
