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
from datetime import date, timedelta
from typing import Final, Literal

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
