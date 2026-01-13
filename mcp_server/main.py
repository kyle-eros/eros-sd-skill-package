"""EROS Schedule Generator MCP Server.

Provides database tools for the EROS schedule generation pipeline.
MCP Specification: 2025-11-25
Server Name: eros-db
Tool Naming Convention: mcp__eros-db__<tool-name>

Tools (15 total):
  Creator (5): get_creator_profile, get_active_creators, get_allowed_content_types,
               get_content_type_rankings, get_persona_profile
  Schedule (5): get_volume_config, get_active_volume_triggers, get_performance_trends,
                save_schedule, save_volume_triggers
  Caption (3): get_batch_captions_by_content_types, get_send_type_captions,
               validate_caption_structure
  Config (2): get_send_types_constraints (lightweight), get_send_types (full)

IMPORTANT: This server uses ACTUAL table names from the database:
  - caption_bank (not captions)
  - vault_matrix (not vault_content)
  - top_content_types (not content_type_rankings)
  - creator_personas (not personas)
  - volume_assignments (not volume_configs)
"""
import os
import sys
import json
import re
import sqlite3
import logging
import hashlib
import time
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

from .volume_utils import (
    TIERS, TIER_ORDER, PRIME_HOURS, DAY_NAMES,
    get_tier, get_tier_ranges, calc_calendar_boost, calc_weekend_boost,
    calc_bump_multiplier, calc_health_status, calc_consecutive_decline_weeks,
    compute_volume_config_hash, get_week_dates, get_day_name,
    # Caption tool constants (v2.0)
    CAPTION_TIER_LABELS, CAPTION_TIER_SCORES, EFFECTIVELY_FRESH_DAYS,
    VALID_SCHEDULABLE_TYPES, MAX_CONTENT_TYPES,
    # Caption validation constants (v2.0.0)
    CAPTION_LENGTH_THRESHOLDS, CAPTION_SPAM_PATTERNS, SALES_LANGUAGE_TOLERANT,
    CAPTION_SCORE_THRESHOLDS, CAPTION_MAX_INPUT_LENGTH, CAPTION_VALIDATION_ERROR_CODES
)

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("eros-mcp")

# Verify MCP SDK installation
try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    logger.error("MCP SDK not installed. Run: pip install mcp")
    logger.error(f"Import error: {e}")
    sys.exit(1)

# Initialize MCP server
mcp = FastMCP("eros-db")

# Database path resolution (with fallbacks)
DB_PATH = os.environ.get("EROS_DB_PATH")
if not DB_PATH:
    # Try relative path from project root
    DB_PATH = str(Path(__file__).parent.parent / "data" / "eros_sd_main.db")
if not os.path.exists(DB_PATH):
    # Try absolute fallback
    DB_PATH = "/Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db"

logger.info(f"Database path: {DB_PATH}")
logger.info(f"Database exists: {os.path.exists(DB_PATH)}")


# ============================================================
# DATABASE UTILITIES
# ============================================================

@contextmanager
def get_db_connection():
    """Create database connection with proper cleanup and settings."""
    conn = None
    try:
        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(f"Database not found: {DB_PATH}")

        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row

        # Configure SQLite for optimal performance
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")

        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def db_query(query: str, params: tuple = ()) -> list:
    """Execute a read query and return results as list of dicts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def db_execute(query: str, params: tuple = ()) -> int:
    """Execute a write query and return last row id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid


def safe_get(d: dict, key: str, default=None):
    """Safely get dict value with default."""
    return d.get(key, default) if d else default


# ============================================================
# CREATOR RESOLUTION HELPERS
# ============================================================

def validate_creator_id(creator_id: str) -> tuple[bool, str]:
    """Validate creator_id format.

    Returns:
        (is_valid, error_message or cleaned_id)
    """
    if not creator_id:
        return False, "creator_id cannot be empty"

    # Strip whitespace
    cleaned = creator_id.strip()

    # Check length
    if len(cleaned) < 2 or len(cleaned) > 100:
        return False, f"creator_id length must be 2-100 chars, got {len(cleaned)}"

    # Allow alphanumeric, underscore, hyphen only
    if not re.match(r'^[a-zA-Z0-9_-]+$', cleaned):
        return False, f"creator_id contains invalid characters: {cleaned}"

    return True, cleaned


def resolve_creator_id(creator_id: str) -> dict:
    """Resolve creator_id or page_name to full creator record.

    Returns:
        {"found": True, "creator_id": str, "page_name": str, ...} or
        {"found": False, "error": str}
    """
    is_valid, result = validate_creator_id(creator_id)
    if not is_valid:
        return {"found": False, "error": result}

    cleaned_id = result

    try:
        # Try exact creator_id match first, then page_name
        results = db_query(
            """SELECT creator_id, page_name, display_name, is_active
               FROM creators
               WHERE creator_id = ? OR page_name = ?
               LIMIT 1""",
            (cleaned_id, cleaned_id)
        )

        if not results:
            # Try case-insensitive page_name match
            results = db_query(
                """SELECT creator_id, page_name, display_name, is_active
                   FROM creators
                   WHERE LOWER(page_name) = LOWER(?)
                   LIMIT 1""",
                (cleaned_id,)
            )

        if not results:
            return {"found": False, "error": f"Creator not found: {creator_id}"}

        row = results[0]
        return {
            "found": True,
            "creator_id": row["creator_id"],
            "page_name": row["page_name"],
            "display_name": row.get("display_name"),
            "is_active": row.get("is_active", True)
        }

    except Exception as e:
        logger.error(f"resolve_creator_id error: {e}")
        return {"found": False, "error": f"Database error: {str(e)}"}


def get_mm_revenue_with_fallback(creator_id: str) -> dict:
    """Get MM revenue using 3-level fallback chain.

    Fallback levels:
        1. Recent mass_messages (≤7 days old, ≥3 messages) - HIGH confidence
        2. creators.current_message_net + current_posts_net - MEDIUM confidence
        3. Fan count estimate (fan_count × $2.50) - LOW confidence

    Returns:
        {
            "mm_revenue_30d": float,
            "mm_revenue_confidence": "high" | "medium" | "low",
            "mm_revenue_source": str,
            "mm_data_age_days": int | None,
            "mm_message_count_30d": int
        }
    """
    try:
        # Level 1: Try recent mass_messages aggregation
        level1 = db_query("""
            SELECT
                SUM(earnings) as total_earnings,
                COUNT(*) as message_count,
                MAX(imported_at) as last_import,
                julianday('now') - julianday(MAX(imported_at)) as days_since_last
            FROM mass_messages
            WHERE creator_id = ?
            AND imported_at >= date('now', '-30 days')
        """, (creator_id,))

        if level1 and level1[0].get('message_count', 0) >= 3:
            row = level1[0]
            days_old = row.get('days_since_last') or 0

            if days_old <= 7:  # Data is fresh enough
                return {
                    "mm_revenue_30d": round(row.get('total_earnings', 0) or 0, 2),
                    "mm_revenue_confidence": "high",
                    "mm_revenue_source": "mass_messages_30d",
                    "mm_data_age_days": int(days_old),
                    "mm_message_count_30d": row.get('message_count', 0)
                }

        # Level 2: Use creator's stored metrics
        level2 = db_query("""
            SELECT
                current_message_net,
                current_posts_net,
                current_total_earnings,
                metrics_snapshot_date,
                julianday('now') - julianday(metrics_snapshot_date) as days_old
            FROM creators
            WHERE creator_id = ?
        """, (creator_id,))

        if level2 and level2[0]:
            row = level2[0]
            msg_net = row.get('current_message_net') or 0
            posts_net = row.get('current_posts_net') or 0

            if msg_net > 0 or posts_net > 0:
                days_old = row.get('days_old')
                return {
                    "mm_revenue_30d": round(msg_net + posts_net, 2),
                    "mm_revenue_confidence": "medium",
                    "mm_revenue_source": "creator_metrics",
                    "mm_data_age_days": int(days_old) if days_old else None,
                    "mm_message_count_30d": level1[0].get('message_count', 0) if level1 else 0
                }

        # Level 3: Fan count estimate
        level3 = db_query(
            "SELECT current_fan_count FROM creators WHERE creator_id = ?",
            (creator_id,)
        )

        fan_count = (level3[0].get('current_fan_count', 0) if level3 else 0) or 0
        estimated_revenue = fan_count * 2.50  # $2.50 per fan estimate

        return {
            "mm_revenue_30d": round(estimated_revenue, 2),
            "mm_revenue_confidence": "low",
            "mm_revenue_source": "fan_count_estimate",
            "mm_data_age_days": None,
            "mm_message_count_30d": 0
        }

    except Exception as e:
        logger.error(f"get_mm_revenue_with_fallback error: {e}")
        return {
            "mm_revenue_30d": 0,
            "mm_revenue_confidence": "error",
            "mm_revenue_source": f"error: {str(e)}",
            "mm_data_age_days": None,
            "mm_message_count_30d": 0
        }


# ============================================================
# CREATOR TOOLS (5)
# ============================================================

@mcp.tool()
def get_creator_profile(
    creator_id: str,
    include_analytics: bool = True,
    include_volume: bool = True,
    include_content_rankings: bool = True,
    include_vault: bool = True,
    include_persona: bool = True
) -> dict:
    """Retrieves comprehensive creator profile with analytics, volume, content rankings, vault, and persona.

    MCP Name: mcp__eros-db__get_creator_profile

    This is the PRIMARY data-fetching tool for pipeline preflight. Returns a bundled
    response to minimize MCP calls during execution.

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        include_analytics: Include 30-day performance metrics with confidence (default: True)
        include_volume: Include volume tier and daily distribution (default: True)
        include_content_rankings: Include TOP/MID/LOW/AVOID content types (default: True)
        include_vault: Include vault availability from vault_matrix (default: True)
        include_persona: Include tone, emoji, slang settings for voice matching (default: True)

    Returns:
        Comprehensive profile bundle:
        {
            "found": bool,
            "creator": {
                "creator_id", "page_name", "display_name", "page_type",
                "subscription_price", "timezone", "content_category",
                "current_fan_count", "current_total_earnings",
                "is_active", "base_price"
            },
            "analytics_summary": {  # if include_analytics=True
                "mm_revenue_30d", "mm_revenue_confidence", "mm_revenue_source",
                "mm_data_age_days", "mm_message_count_30d",
                "avg_rps", "avg_conversion", "avg_open_rate",
                "total_sends", "total_earnings"
            },
            "volume_assignment": {  # if include_volume=True
                "volume_level", "revenue_per_day", "engagement_per_day",
                "retention_per_day", "ppv_per_day", "bump_per_day"
            },
            "top_content_types": [  # if include_content_rankings=True
                {"type_name", "performance_tier", "rps", "conversion_rate", "send_count"}
            ],
            "allowed_content_types": {  # if include_vault=True
                "allowed_types", "allowed_type_names",
                "type_count", "vault_hash"
            },
            "persona": {  # if include_persona=True
                "primary_tone", "secondary_tone", "emoji_frequency",
                "slang_level", "avg_sentiment", "avg_caption_length"
            },
            "metadata": {
                "fetched_at", "data_sources_used", "mcp_calls_saved"
            }
        }
    """
    logger.info(f"get_creator_profile: creator_id={creator_id}, analytics={include_analytics}, volume={include_volume}, rankings={include_content_rankings}, vault={include_vault}, persona={include_persona}")

    fetched_at = datetime.now().isoformat()
    data_sources = []

    # Step 1: Resolve and validate creator
    resolved = resolve_creator_id(creator_id)
    if not resolved.get("found"):
        return {
            "found": False,
            "error": resolved.get("error", f"Creator not found: {creator_id}"),
            "creator": None
        }

    creator_pk = resolved["creator_id"]
    data_sources.append("creators")

    try:
        # Step 2: Get full creator profile
        creator_rows = db_query("""
            SELECT
                c.creator_id, c.page_name, c.display_name, c.page_type,
                c.subscription_price, c.timezone, c.content_category,
                c.current_fan_count, c.current_active_fans,
                c.current_total_earnings, c.current_message_net, c.current_posts_net,
                c.is_active, c.metrics_snapshot_date, c.performance_tier
            FROM creators c
            WHERE c.creator_id = ?
        """, (creator_pk,))

        if not creator_rows:
            return {"found": False, "error": f"Creator data not found: {creator_id}", "creator": None}

        creator_data = dict(creator_rows[0])

        # Build response
        response = {
            "found": True,
            "creator": {
                "creator_id": creator_data["creator_id"],
                "page_name": creator_data["page_name"],
                "display_name": creator_data.get("display_name"),
                "page_type": creator_data.get("page_type", "paid"),
                "subscription_price": creator_data.get("subscription_price"),
                "timezone": creator_data.get("timezone", "America/Los_Angeles"),
                "content_category": creator_data.get("content_category", "softcore"),
                "current_fan_count": creator_data.get("current_fan_count", 0),
                "current_active_fans": creator_data.get("current_active_fans", 0),
                "current_total_earnings": creator_data.get("current_total_earnings", 0),
                "is_active": creator_data.get("is_active", True),
                "performance_tier": creator_data.get("performance_tier", 3)
            }
        }

        # Step 3: Get analytics with fallback (if requested)
        if include_analytics:
            # Get MM revenue with 3-level fallback
            mm_revenue = get_mm_revenue_with_fallback(creator_pk)
            data_sources.append(mm_revenue["mm_revenue_source"])

            # Get additional performance metrics
            perf_metrics = db_query("""
                SELECT
                    CASE WHEN SUM(purchased_count) > 0
                         THEN SUM(earnings) / SUM(purchased_count)
                         ELSE 0 END as avg_rps,
                    CASE WHEN SUM(viewed_count) > 0
                         THEN 1.0 * SUM(purchased_count) / SUM(viewed_count)
                         ELSE 0 END as avg_conversion,
                    CASE WHEN SUM(sent_count) > 0
                         THEN 1.0 * SUM(viewed_count) / SUM(sent_count)
                         ELSE 0 END as avg_open_rate,
                    SUM(earnings) as total_earnings,
                    COUNT(*) as total_sends
                FROM mass_messages
                WHERE creator_id = ?
                AND imported_at >= date('now', '-30 days')
            """, (creator_pk,))

            perf = perf_metrics[0] if perf_metrics else {}

            response["analytics_summary"] = {
                "mm_revenue_30d": mm_revenue["mm_revenue_30d"],
                "mm_revenue_confidence": mm_revenue["mm_revenue_confidence"],
                "mm_revenue_source": mm_revenue["mm_revenue_source"],
                "mm_data_age_days": mm_revenue["mm_data_age_days"],
                "mm_message_count_30d": mm_revenue["mm_message_count_30d"],
                "avg_rps": round(perf.get("avg_rps", 0) or 0, 2),
                "avg_conversion": round(perf.get("avg_conversion", 0) or 0, 4),
                "avg_open_rate": round(perf.get("avg_open_rate", 0) or 0, 4),
                "total_earnings": round(perf.get("total_earnings", 0) or 0, 2),
                "total_sends": perf.get("total_sends", 0) or 0
            }

        # Step 4: Get volume assignment (if requested)
        if include_volume:
            vol_rows = db_query("""
                SELECT
                    va.volume_level, va.ppv_per_day, va.bump_per_day,
                    va.is_active as vol_active
                FROM volume_assignments va
                WHERE va.creator_id = ? AND va.is_active = 1
                ORDER BY va.assigned_at DESC
                LIMIT 1
            """, (creator_pk,))

            # Calculate tier from revenue if not in volume_assignments
            mm_rev = response.get("analytics_summary", {}).get("mm_revenue_30d", 0) if include_analytics else (creator_data.get("current_message_net", 0) or 0)

            # Use shared tier calculation from volume_utils (eliminates BUG 1 - duplicate tier logic)
            existing_tier = vol_rows[0].get("volume_level") if vol_rows else None
            tier = get_tier(mm_rev, previous_tier=existing_tier)
            ranges = get_tier_ranges(tier)

            if vol_rows:
                data_sources.append("volume_assignments")

            response["volume_assignment"] = {
                "volume_level": tier,
                "mm_revenue_used": mm_rev,
                "revenue_per_day": list(ranges["revenue"]),
                "engagement_per_day": list(ranges["engagement"]),
                "retention_per_day": list(ranges["retention"]),
                "ppv_per_day": vol_rows[0].get("ppv_per_day") if vol_rows else None,
                "bump_per_day": vol_rows[0].get("bump_per_day") if vol_rows else None
            }

        # Step 5a: Get content type rankings (if requested)
        if include_content_rankings:
            import hashlib
            from datetime import date

            rankings = db_query("""
                SELECT
                    content_type as type_name,
                    performance_tier,
                    avg_rps as rps,
                    avg_purchase_rate as conversion_rate,
                    send_count as sends_last_30d,
                    total_earnings,
                    confidence_score,
                    analysis_date
                FROM top_content_types
                WHERE creator_id = ?
                  AND analysis_date = (
                      SELECT MAX(analysis_date)
                      FROM top_content_types
                      WHERE creator_id = ?
                  )
                ORDER BY avg_rps DESC
            """, (creator_pk, creator_pk))

            if rankings:
                data_sources.append("top_content_types")

            # Pre-compute tier lists
            avoid_types = [r["type_name"] for r in rankings if r.get("performance_tier") == "AVOID"]
            top_types = [r["type_name"] for r in rankings if r.get("performance_tier") == "TOP"]

            # Compute avoid_types_hash for ValidationCertificate
            avoid_input = "|".join(sorted(avoid_types))
            avoid_types_hash = f"sha256:{hashlib.sha256(avoid_input.encode()).hexdigest()[:16]}"

            # Get analysis date and staleness
            analysis_date = rankings[0].get("analysis_date") if rankings else None
            data_age_days = None
            is_stale = False

            if analysis_date:
                try:
                    if isinstance(analysis_date, str):
                        analysis_dt = date.fromisoformat(analysis_date)
                    else:
                        analysis_dt = analysis_date
                    data_age_days = (date.today() - analysis_dt).days
                    is_stale = data_age_days > 14
                except (ValueError, TypeError):
                    pass

            response["content_type_rankings"] = {
                "rankings": rankings or [],
                "avoid_types": avoid_types,
                "top_types": top_types,
                "total_types": len(rankings),
                "avoid_types_hash": avoid_types_hash,
                "analysis_date": str(analysis_date) if analysis_date else None,
                "data_age_days": data_age_days,
                "is_stale": is_stale
            }

            # Also keep flat lists at root for backward compatibility
            response["top_content_types"] = rankings or []  # Deprecated, use content_type_rankings
            response["avoid_types"] = avoid_types
            response["top_types"] = top_types

        # Step 5b: Get allowed content types (if requested)
        if include_vault:
            import hashlib

            vault_types = db_query("""
                SELECT ct.type_name, ct.type_category, ct.is_explicit
                FROM vault_matrix vm
                JOIN content_types ct ON vm.content_type_id = ct.content_type_id
                WHERE vm.creator_id = ? AND vm.has_content = 1
                ORDER BY ct.type_name ASC
            """, (creator_pk,))

            if vault_types:
                data_sources.append("vault_matrix")

            allowed_type_names = [v["type_name"] for v in vault_types]

            # Compute vault hash for ValidationCertificate
            hash_input = "|".join(sorted(allowed_type_names))
            vault_hash = f"sha256:{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

            response["allowed_content_types"] = {
                "allowed_types": [
                    {
                        "type_name": v["type_name"],
                        "type_category": v.get("type_category"),
                        "is_explicit": bool(v.get("is_explicit", 1))
                    }
                    for v in vault_types
                ],
                "allowed_type_names": allowed_type_names,
                "type_count": len(allowed_type_names),
                "vault_hash": vault_hash
            }

        # Step 5c: Get persona profile (if requested)
        if include_persona:
            persona_query = """
                SELECT
                    persona_id, creator_id, primary_tone, secondary_tone,
                    emoji_frequency, favorite_emojis, slang_level,
                    avg_sentiment, avg_caption_length, last_analyzed,
                    validation_status
                FROM creator_personas
                WHERE creator_id = ?
            """
            persona_results = db_query(persona_query, (creator_pk,))

            if persona_results:
                persona_data = dict(persona_results[0])
                persona_data["_default"] = False
                data_sources.append("creator_personas")
            else:
                # Default fallback for missing persona
                persona_data = {
                    "creator_id": creator_pk,
                    "primary_tone": "playful",
                    "secondary_tone": None,
                    "emoji_frequency": "moderate",
                    "slang_level": "light",
                    "_default": True
                }

            response["persona"] = persona_data

        # Step 6: Add metadata
        mcp_calls_saved = 0
        if include_analytics: mcp_calls_saved += 1
        if include_volume: mcp_calls_saved += 1
        if include_content_rankings: mcp_calls_saved += 1
        if include_vault: mcp_calls_saved += 1
        if include_persona: mcp_calls_saved += 1

        response["metadata"] = {
            "fetched_at": fetched_at,
            "data_sources_used": list(set(data_sources)),
            "mcp_calls_saved": mcp_calls_saved,
            "include_flags": {
                "analytics": include_analytics,
                "volume": include_volume,
                "content_rankings": include_content_rankings,
                "vault": include_vault,
                "persona": include_persona
            }
        }

        return response

    except Exception as e:
        logger.error(f"get_creator_profile error: {e}")
        return {
            "found": False,
            "error": str(e),
            "creator": None
        }


@mcp.tool()
def get_active_creators(
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
    """Returns paginated list of active creators with comprehensive metrics.

    MCP Name: mcp__eros-db__get_active_creators

    This is the PRIMARY tool for batch/admin operations, creator discovery,
    tier-based reporting, and multi-creator workflow initialization.

    Args:
        limit: Maximum creators to return (default 100, max 500)
        offset: Pagination offset for large result sets (default 0)
        tier: Filter by volume tier (Low/Mid/High/Ultra)
        page_type: Filter by page type ("paid" or "free")
        min_revenue: Minimum monthly MM revenue filter
        max_revenue: Maximum monthly MM revenue filter
        min_fan_count: Minimum fan count filter
        sort_by: Sort field - "revenue", "fan_count", "name", "tier" (default: "revenue")
        sort_order: Sort direction - "asc" or "desc" (default: "desc")
        include_volume_details: Include daily volume breakdown (ppv_per_day, etc.)

    Returns:
        {
            "creators": [
                {
                    "creator_id", "page_name", "display_name", "page_type",
                    "subscription_price", "timezone", "content_category",
                    "current_fan_count", "mm_revenue_monthly", "volume_tier",
                    "metrics_snapshot_date", "performance_tier",
                    "volume_details": {...}  // if include_volume_details=True
                }
            ],
            "count": int,           // Results in this response
            "total_count": int,     // Total matching records (for pagination)
            "limit": int,
            "offset": int,
            "metadata": {
                "fetched_at": "ISO timestamp",
                "filters_applied": {...},
                "sort": {"by": "revenue", "order": "desc"},
                "has_more": bool
            }
        }

    Example Usage:
        # Basic: Get top 10 creators by revenue
        get_active_creators(limit=10)

        # Filtered: Get Ultra tier creators only
        get_active_creators(tier="Ultra", limit=50)

        # Paginated: Get page 2 of results (items 100-199)
        get_active_creators(limit=100, offset=100)

        # Complex: High-revenue paid creators sorted by fan count
        get_active_creators(
            page_type="paid",
            min_revenue=3000,
            sort_by="fan_count",
            sort_order="desc",
            include_volume_details=True
        )
    """
    logger.info(f"get_active_creators: limit={limit}, offset={offset}, tier={tier}, "
                f"page_type={page_type}, sort_by={sort_by}")
    fetched_at = datetime.now().isoformat()

    try:
        # ============================================================
        # INPUT VALIDATION
        # ============================================================

        # Clamp limit between 1-500
        limit = min(max(1, limit), 500)
        offset = max(0, offset)

        # Validate tier parameter (actual database values)
        valid_tiers = ('Low', 'Mid', 'High', 'Ultra')
        if tier is not None and tier not in valid_tiers:
            return {
                "error": f"Invalid tier '{tier}'. Valid values: {', '.join(valid_tiers)}",
                "creators": [],
                "count": 0,
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "metadata": {"fetched_at": fetched_at, "validation_error": True}
            }

        # Validate page_type parameter
        if page_type is not None and page_type not in ('paid', 'free'):
            return {
                "error": f"Invalid page_type '{page_type}'. Valid values: paid, free",
                "creators": [],
                "count": 0,
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "metadata": {"fetched_at": fetched_at, "validation_error": True}
            }

        # Validate and map sort_by parameter
        sort_columns = {
            "revenue": "c.current_message_net",
            "fan_count": "c.current_fan_count",
            "name": "c.page_name",
            "tier": "va.volume_level"
        }
        if sort_by not in sort_columns:
            sort_by = "revenue"  # Default fallback

        # Normalize sort_order
        sort_order_sql = "ASC" if sort_order.lower() == "asc" else "DESC"

        # ============================================================
        # BUILD QUERY
        # ============================================================

        # Base SELECT with comprehensive fields
        base_select = """
            SELECT c.creator_id, c.page_name, c.display_name, c.page_type,
                   c.subscription_price, c.timezone, c.content_category,
                   c.current_fan_count, c.current_active_fans,
                   c.current_message_net as mm_revenue_monthly,
                   c.current_total_earnings,
                   c.metrics_snapshot_date, c.performance_tier,
                   va.volume_level as volume_tier
        """

        # Add volume details if requested
        if include_volume_details:
            base_select += """,
                   va.ppv_per_day, va.bump_per_day
            """

        base_from = """
            FROM creators c
            LEFT JOIN volume_assignments va
                ON c.creator_id = va.creator_id AND va.is_active = 1
        """

        # Build WHERE clause dynamically
        where_clauses = ["c.is_active = 1"]
        params = []
        filters_applied = {}

        if tier is not None:
            where_clauses.append("va.volume_level = ?")
            params.append(tier)
            filters_applied["tier"] = tier

        if page_type is not None:
            where_clauses.append("c.page_type = ?")
            params.append(page_type)
            filters_applied["page_type"] = page_type

        if min_revenue is not None:
            where_clauses.append("c.current_message_net >= ?")
            params.append(min_revenue)
            filters_applied["min_revenue"] = min_revenue

        if max_revenue is not None:
            where_clauses.append("c.current_message_net <= ?")
            params.append(max_revenue)
            filters_applied["max_revenue"] = max_revenue

        if min_fan_count is not None:
            where_clauses.append("c.current_fan_count >= ?")
            params.append(min_fan_count)
            filters_applied["min_fan_count"] = min_fan_count

        where_sql = " WHERE " + " AND ".join(where_clauses)

        # ============================================================
        # EXECUTE COUNT QUERY (for pagination metadata)
        # ============================================================

        count_query = f"SELECT COUNT(*) as total {base_from} {where_sql}"
        count_result = db_query(count_query, tuple(params))
        total_count = count_result[0]['total'] if count_result else 0

        # ============================================================
        # EXECUTE MAIN QUERY
        # ============================================================

        # Handle NULL values in sort (push to end)
        order_sql = f" ORDER BY {sort_columns[sort_by]} {sort_order_sql} NULLS LAST"
        limit_sql = " LIMIT ? OFFSET ?"

        full_query = base_select + base_from + where_sql + order_sql + limit_sql
        query_params = params + [limit, offset]

        results = db_query(full_query, tuple(query_params))

        # ============================================================
        # PROCESS RESULTS
        # ============================================================

        creators = []
        for row in results:
            creator_data = {
                "creator_id": row["creator_id"],
                "page_name": row["page_name"],
                "display_name": row.get("display_name"),
                "page_type": row.get("page_type", "paid"),
                "subscription_price": row.get("subscription_price"),
                "timezone": row.get("timezone", "America/Los_Angeles"),
                "content_category": row.get("content_category"),
                "current_fan_count": row.get("current_fan_count", 0),
                "current_active_fans": row.get("current_active_fans", 0),
                "mm_revenue_monthly": row.get("mm_revenue_monthly", 0),
                "current_total_earnings": row.get("current_total_earnings", 0),
                "volume_tier": row.get("volume_tier"),  # May be None if no assignment
                "metrics_snapshot_date": row.get("metrics_snapshot_date"),
                "performance_tier": row.get("performance_tier")
            }

            # Add volume details if requested AND creator has volume assignment
            if include_volume_details and row.get("volume_tier"):
                creator_data["volume_details"] = {
                    "ppv_per_day": row.get("ppv_per_day"),
                    "bump_per_day": row.get("bump_per_day")
                }

            creators.append(creator_data)

        # ============================================================
        # BUILD RESPONSE
        # ============================================================

        return {
            "creators": creators,
            "count": len(creators),
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "metadata": {
                "fetched_at": fetched_at,
                "filters_applied": filters_applied if filters_applied else None,
                "sort": {
                    "by": sort_by,
                    "order": sort_order.lower()
                },
                "has_more": (offset + len(creators)) < total_count,
                "page_info": {
                    "current_page": (offset // limit) + 1 if limit > 0 else 1,
                    "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1
                }
            }
        }

    except Exception as e:
        logger.error(f"get_active_creators error: {e}")
        return {
            "error": str(e),
            "creators": [],
            "count": 0,
            "total_count": 0,
            "limit": limit,
            "offset": offset,
            "metadata": {
                "fetched_at": fetched_at,
                "error": True
            }
        }


@mcp.tool()
def get_allowed_content_types(
    creator_id: str,
    include_category: bool = True
) -> dict:
    """Returns content types a creator allows for PPV/revenue-based sends.

    MCP Name: mcp__eros-db__get_allowed_content_types
    HARD GATE DATA - Zero tolerance validation

    A creator "allows" a content type when has_content=1 in vault_matrix.
    This determines:
    1. What content types can be scheduled for this creator
    2. What caption themes are appropriate for their sends

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        include_category: Include type_category and is_explicit per type (default: True)

    Returns:
        Allowed content types for the creator:
        {
            "creator_id": str,
            "allowed_types": [
                {
                    "type_name": str,
                    "type_category": str | None,  # if include_category
                    "is_explicit": bool           # if include_category
                }
            ],
            "allowed_type_names": [str, ...],    # Simple list for quick validation
            "type_count": int,
            "metadata": {
                "fetched_at": str,
                "vault_hash": str,
                "creator_resolved": str
            }
        }

        Error response:
        {
            "error": str,
            "allowed_types": [],
            "allowed_type_names": [],
            "type_count": 0,
            "metadata": {"fetched_at": str, "error": True}
        }
    """
    import hashlib

    logger.info(f"get_allowed_content_types: creator_id={creator_id}, include_category={include_category}")
    fetched_at = datetime.now().isoformat()

    try:
        # ============================================================
        # STEP 1: RESOLVE CREATOR
        # ============================================================
        resolved = resolve_creator_id(creator_id)
        if not resolved.get("found"):
            return {
                "error": f"Creator not found: {creator_id}",
                "allowed_types": [],
                "allowed_type_names": [],
                "type_count": 0,
                "metadata": {"fetched_at": fetched_at, "error": True}
            }

        creator_pk = resolved["creator_id"]

        # ============================================================
        # STEP 2: BUILD QUERY (only types with has_content=1)
        # ============================================================
        select_fields = ["ct.type_name"]

        if include_category:
            select_fields.extend(["ct.type_category", "ct.is_explicit"])

        query = f"""
            SELECT {', '.join(select_fields)}
            FROM vault_matrix vm
            JOIN content_types ct ON vm.content_type_id = ct.content_type_id
            WHERE vm.creator_id = ? AND vm.has_content = 1
            ORDER BY ct.type_name ASC
        """

        types = db_query(query, (creator_pk,))

        # ============================================================
        # STEP 3: BUILD RESPONSE
        # ============================================================
        allowed_types = []
        allowed_type_names = []

        for t in types:
            type_data = {"type_name": t["type_name"]}

            if include_category:
                type_data["type_category"] = t.get("type_category")
                type_data["is_explicit"] = bool(t.get("is_explicit", 1))

            allowed_types.append(type_data)
            allowed_type_names.append(t["type_name"])

        # ============================================================
        # STEP 4: COMPUTE VAULT HASH (for ValidationCertificate)
        # ============================================================
        hash_input = "|".join(sorted(allowed_type_names))
        vault_hash = f"sha256:{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

        return {
            "creator_id": creator_id,
            "allowed_types": allowed_types,
            "allowed_type_names": allowed_type_names,
            "type_count": len(allowed_type_names),
            "metadata": {
                "fetched_at": fetched_at,
                "vault_hash": vault_hash,
                "creator_resolved": creator_pk
            }
        }

    except Exception as e:
        logger.error(f"get_allowed_content_types error: {e}")
        return {
            "error": str(e),
            "allowed_types": [],
            "allowed_type_names": [],
            "type_count": 0,
            "metadata": {"fetched_at": fetched_at, "error": True}
        }


@mcp.tool()
def get_content_type_rankings(
    creator_id: str,
    include_metrics: bool = True
) -> dict:
    """Returns content type performance rankings with TOP/MID/LOW/AVOID tiers.

    MCP Name: mcp__eros-db__get_content_type_rankings
    HARD GATE DATA - Used for validation (AVOID tier = zero tolerance)

    The AVOID tier is sacred - any content type with performance_tier = 'AVOID'
    must NEVER appear in a generated schedule. This is one of the four-layer
    defense system gates.

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        include_metrics: Include detailed RPS, conversion metrics (default: True)
                        Set False for lightweight validation-only calls

    Returns:
        Content type rankings for the creator:
        {
            "creator_id": str,
            "rankings": [
                {
                    "type_name": str,
                    "performance_tier": "TOP" | "MID" | "LOW" | "AVOID",
                    "rps": float,              # if include_metrics
                    "conversion_rate": float,  # if include_metrics
                    "sends_last_30d": int,     # if include_metrics
                    "total_earnings": float,   # if include_metrics
                    "confidence_score": float  # if include_metrics
                }
            ],
            "avoid_types": [str, ...],      # Pre-computed AVOID list (HARD GATE)
            "top_types": [str, ...],        # Pre-computed TOP list
            "total_types": int,
            "metadata": {
                "fetched_at": str,
                "rankings_hash": str,        # For ValidationCertificate
                "avoid_types_hash": str,     # For HARD GATE verification
                "creator_resolved": str,
                "analysis_date": str,        # When analysis was run
                "data_age_days": int,        # Days since analysis
                "is_stale": bool             # True if > 14 days old
            }
        }

        Error response:
        {
            "error": str,
            "rankings": [],
            "avoid_types": [],
            "top_types": [],
            "total_types": 0,
            "metadata": {"fetched_at": str, "error": True}
        }
    """
    import hashlib
    from datetime import date

    logger.info(f"get_content_type_rankings: creator_id={creator_id}, include_metrics={include_metrics}")
    fetched_at = datetime.now().isoformat()

    try:
        # ============================================================
        # STEP 1: RESOLVE CREATOR (use helper like get_allowed_content_types)
        # ============================================================
        resolved = resolve_creator_id(creator_id)
        if not resolved.get("found"):
            return {
                "error": f"Creator not found: {creator_id}",
                "rankings": [],
                "avoid_types": [],
                "top_types": [],
                "total_types": 0,
                "metadata": {"fetched_at": fetched_at, "error": True}
            }

        creator_pk = resolved["creator_id"]

        # ============================================================
        # STEP 2: BUILD QUERY (filter by latest analysis_date)
        # ============================================================
        select_fields = ["content_type as type_name", "performance_tier", "analysis_date"]

        if include_metrics:
            select_fields.extend([
                "avg_rps as rps",
                "avg_purchase_rate as conversion_rate",
                "send_count as sends_last_30d",
                "total_earnings",
                "confidence_score"
            ])

        query = f"""
            SELECT {', '.join(select_fields)}
            FROM top_content_types
            WHERE creator_id = ?
              AND analysis_date = (
                  SELECT MAX(analysis_date)
                  FROM top_content_types
                  WHERE creator_id = ?
              )
            ORDER BY avg_rps DESC
        """

        rankings = db_query(query, (creator_pk, creator_pk))

        # ============================================================
        # STEP 3: BUILD RESPONSE LISTS
        # ============================================================
        avoid_types = []
        top_types = []
        ranking_list = []
        analysis_date = None

        for r in rankings:
            # Capture analysis_date from first row
            if analysis_date is None and r.get("analysis_date"):
                analysis_date = r["analysis_date"]

            type_name = r.get("type_name", "")
            tier = r.get("performance_tier", "MID")

            if tier == "AVOID":
                avoid_types.append(type_name)
            elif tier == "TOP":
                top_types.append(type_name)

            # Build ranking entry
            entry = {
                "type_name": type_name,
                "performance_tier": tier
            }

            if include_metrics:
                entry.update({
                    "rps": r.get("rps", 0.0),
                    "conversion_rate": r.get("conversion_rate", 0.0),
                    "sends_last_30d": r.get("sends_last_30d", 0),
                    "total_earnings": r.get("total_earnings", 0.0),
                    "confidence_score": r.get("confidence_score", 0.0)
                })

            ranking_list.append(entry)

        # ============================================================
        # STEP 4: COMPUTE HASHES (for ValidationCertificate)
        # ============================================================
        # Rankings hash (all types sorted)
        all_type_names = sorted([r["type_name"] for r in ranking_list])
        rankings_input = "|".join(all_type_names)
        rankings_hash = f"sha256:{hashlib.sha256(rankings_input.encode()).hexdigest()[:16]}"

        # AVOID types hash (critical for HARD GATE verification)
        avoid_input = "|".join(sorted(avoid_types))
        avoid_types_hash = f"sha256:{hashlib.sha256(avoid_input.encode()).hexdigest()[:16]}"

        # ============================================================
        # STEP 5: CALCULATE DATA FRESHNESS
        # ============================================================
        data_age_days = None
        is_stale = False

        if analysis_date:
            try:
                if isinstance(analysis_date, str):
                    analysis_dt = date.fromisoformat(analysis_date)
                else:
                    analysis_dt = analysis_date
                data_age_days = (date.today() - analysis_dt).days
                is_stale = data_age_days > 14
            except (ValueError, TypeError):
                pass

        # ============================================================
        # STEP 6: BUILD FINAL RESPONSE
        # ============================================================
        return {
            "creator_id": creator_id,
            "rankings": ranking_list,
            "avoid_types": avoid_types,
            "top_types": top_types,
            "total_types": len(ranking_list),
            "metadata": {
                "fetched_at": fetched_at,
                "rankings_hash": rankings_hash,
                "avoid_types_hash": avoid_types_hash,
                "creator_resolved": creator_pk,
                "analysis_date": str(analysis_date) if analysis_date else None,
                "data_age_days": data_age_days,
                "is_stale": is_stale
            }
        }

    except Exception as e:
        logger.error(f"get_content_type_rankings error: {e}")
        return {
            "error": str(e),
            "rankings": [],
            "avoid_types": [],
            "top_types": [],
            "total_types": 0,
            "metadata": {"fetched_at": fetched_at, "error": True}
        }


@mcp.tool()
def get_persona_profile(creator_id: str) -> dict:
    """Returns creator persona including tone, archetype, and voice settings.

    MCP Name: mcp__eros-db__get_persona_profile

    Args:
        creator_id: Creator identifier

    Returns:
        Persona configuration for caption generation
    """
    logger.info(f"get_persona_profile: creator_id={creator_id}")
    try:
        # Query creator_personas (actual table name, not personas)
        results = db_query("""
            SELECT cp.* FROM creator_personas cp
            WHERE cp.creator_id = ?
            LIMIT 1
        """, (creator_id,))

        if not results:
            # Try by page_name
            creator = db_query(
                "SELECT creator_id FROM creators WHERE page_name = ? LIMIT 1",
                (creator_id,)
            )
            if creator:
                results = db_query(
                    "SELECT * FROM creator_personas WHERE creator_id = ? LIMIT 1",
                    (creator[0]['creator_id'],)
                )

        if not results:
            # Return sensible defaults if no persona configured
            return {
                "creator_id": creator_id,
                "primary_tone": "playful",       # FIXED: Valid tone from (aggressive, playful, seductive, sultry)
                "secondary_tone": None,          # FIXED: No assumption about secondary when using defaults
                "emoji_frequency": "moderate",
                "slang_level": "light",          # FIXED: Valid value from CHECK (none, light, heavy)
                "_default": True
            }

        return dict(results[0])

    except Exception as e:
        logger.error(f"get_persona_profile error: {e}")
        return {"error": str(e)}


# ============================================================
# SCHEDULE TOOLS (5)
# ============================================================

@mcp.tool()
def get_volume_config(
    creator_id: str,
    week_start: str,
    include_trigger_breakdown: bool = False,
    trigger_overrides: list[dict] | None = None,
    tier_override: str | None = None,
    health_override: dict | None = None,
) -> dict:
    """
    Returns comprehensive week-specific volume configuration with all adjustments applied.

    This is the POWER TOOL for volume calculations. Unlike the bundled response in
    get_creator_profile, this tool returns pre-calculated weekly distribution with
    calendar boosts, trigger multipliers, and health adjustments all applied.

    MCP Name: mcp__eros-db__get_volume_config

    Use Cases:
    - Schedule generation: Get final daily targets for a specific week
    - Debugging: Understand WHY a schedule has certain volume density
    - Simulation: Test "what-if" scenarios without touching DB
    - Historical: Reconstruct past week configurations (calendar exact, tier current)

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        week_start: Week start date in YYYY-MM-DD format (REQUIRED - enables calendar awareness)
        include_trigger_breakdown: If True, includes trigger_details array for auditing
        trigger_overrides: Optional list of triggers to use INSTEAD of DB lookup
            Format: [{"trigger_type": "HIGH_PERFORMER", "adjustment_multiplier": 1.2}]
        tier_override: Optional tier to use INSTEAD of calculated tier (for simulation)
        health_override: Optional health status override for simulation
            Format: {"status": "WARNING", "volume_adjustment": 0}

    Returns:
        Comprehensive volume configuration dict (see response structure below)

    Example:
        # Standard usage for schedule generation
        get_volume_config("alexia", "2026-01-06")

        # Simulation: What if alexia had HIGH_PERFORMER trigger?
        get_volume_config("alexia", "2026-01-06",
            trigger_overrides=[{"trigger_type": "HIGH_PERFORMER", "adjustment_multiplier": 1.2}])

        # Debug: Full breakdown of why volumes are what they are
        get_volume_config("alexia", "2026-01-06", include_trigger_breakdown=True)
    """
    from datetime import datetime, date as date_type, timedelta

    logger.info(f"get_volume_config: creator_id={creator_id}, week_start={week_start}")
    fetched_at = datetime.utcnow().isoformat() + "Z"

    # =========================================================================
    # INPUT VALIDATION
    # =========================================================================
    is_valid, validation_result = validate_creator_id(creator_id)
    if not is_valid:
        return {"error": f"Invalid creator_id format: {validation_result}"}

    try:
        week_start_date = date_type.fromisoformat(week_start)
    except ValueError:
        return {"error": f"Invalid week_start format: {week_start}. Expected YYYY-MM-DD"}

    # Resolve creator
    resolved = resolve_creator_id(creator_id)
    if not resolved.get("found"):
        return {"error": resolved.get("error", f"Creator not found: {creator_id}")}

    creator_id_resolved = resolved["creator_id"]

    # Determine temporal context
    today = date_type.today()
    week_end = week_start_date + timedelta(days=6)
    if week_end < today:
        week_type = "past"
    elif week_start_date > today:
        week_type = "future"
    else:
        week_type = "current"

    # =========================================================================
    # TIER DETERMINATION (4-level fallback chain)
    # =========================================================================
    tier = None
    tier_source = None
    tier_confidence = None
    mm_revenue = None
    fan_count = None
    page_type = None
    content_category = None
    previous_tier = None

    # Override takes precedence
    if tier_override and tier_override in TIER_ORDER:
        tier = tier_override
        tier_source = "override"
        tier_confidence = "high"

    try:
        with get_db_connection() as conn:
            # Get creator data
            creator_row = conn.execute("""
                SELECT
                    page_type, content_category, current_fan_count,
                    current_message_net, current_posts_net
                FROM creators
                WHERE creator_id = ?
            """, (creator_id_resolved,)).fetchone()

            if creator_row:
                page_type = creator_row["page_type"]
                content_category = creator_row["content_category"] or "softcore"
                fan_count = creator_row["current_fan_count"]
                msg_net = creator_row["current_message_net"] or 0
                posts_net = creator_row["current_posts_net"] or 0
                mm_revenue = msg_net + posts_net

            if tier is None:
                # Level 1: Check volume_assignments
                vol_row = conn.execute("""
                    SELECT volume_level, ppv_per_day, bump_per_day
                    FROM volume_assignments
                    WHERE creator_id = ? AND is_active = 1
                    ORDER BY assigned_at DESC LIMIT 1
                """, (creator_id_resolved,)).fetchone()

                if vol_row and vol_row["volume_level"]:
                    previous_tier = vol_row["volume_level"]
                    tier = vol_row["volume_level"]
                    tier_source = "volume_assignments"
                    tier_confidence = "high"

                # Level 2: Calculate from MM revenue
                elif mm_revenue and mm_revenue > 0:
                    tier = get_tier(mm_revenue, previous_tier)
                    tier_source = "mm_revenue"
                    tier_confidence = "high"

                # Level 3: Estimate from fan count
                elif fan_count and fan_count > 0:
                    estimated_revenue = fan_count * 2.50
                    tier = get_tier(estimated_revenue, previous_tier)
                    mm_revenue = estimated_revenue
                    tier_source = "fan_count_estimate"
                    tier_confidence = "medium"

                # Level 4: Default
                else:
                    tier = "MINIMAL"
                    tier_source = "default"
                    tier_confidence = "low"
                    fan_count = fan_count or 1000
                    mm_revenue = fan_count * 2.50

    except Exception as e:
        logger.error(f"get_volume_config DB error: {e}")
        return {"error": f"Database error: {str(e)}"}

    # Get tier ranges
    base_ranges = get_tier_ranges(tier)

    # =========================================================================
    # TRIGGER INTEGRATION
    # =========================================================================
    triggers_data = []
    trigger_multiplier = 1.0
    triggers_applied = 0
    triggers_source = "current_state"

    if trigger_overrides is not None:
        # Simulation mode: use provided triggers
        triggers_data = trigger_overrides
        for tr in triggers_data:
            trigger_multiplier *= tr.get("adjustment_multiplier", 1.0)
            triggers_applied += 1
        triggers_source = "simulated"
    else:
        # Fetch from database
        try:
            with get_db_connection() as conn:
                rows = conn.execute("""
                    SELECT trigger_type, adjustment_multiplier, content_type,
                           confidence, reason, expires_at
                    FROM volume_triggers
                    WHERE creator_id = ?
                      AND is_active = 1
                      AND (expires_at IS NULL OR expires_at > datetime('now'))
                    ORDER BY adjustment_multiplier DESC
                """, (creator_id_resolved,)).fetchall()

                for row in rows:
                    tr = dict(row)
                    triggers_data.append(tr)
                    trigger_multiplier *= tr.get("adjustment_multiplier", 1.0)
                    triggers_applied += 1
        except Exception as e:
            logger.warning(f"Could not fetch triggers: {e}")

    trigger_details = triggers_data if include_trigger_breakdown else None

    # =========================================================================
    # HEALTH STATUS
    # =========================================================================
    health_source = "current_state"

    if health_override:
        health = {
            "status": health_override.get("status", "HEALTHY"),
            "saturation_score": health_override.get("saturation_score", 50),
            "opportunity_score": health_override.get("opportunity_score", 50),
            "decline_weeks": health_override.get("decline_weeks", 0),
            "volume_adjustment": health_override.get("volume_adjustment", 0),
        }
        health_source = "simulated"
    else:
        # Calculate from mass_messages performance data (matching get_performance_trends pattern)
        sat, opp, decline = 50, 50, 0

        try:
            with get_db_connection() as conn:
                # Get saturation from recent send density
                density_row = conn.execute("""
                    SELECT
                        COUNT(*) as send_count,
                        AVG(CASE WHEN view_rate IS NOT NULL THEN view_rate ELSE 0 END) as avg_view_rate
                    FROM mass_messages
                    WHERE creator_id = ?
                      AND sent_date >= date('now', '-14 days')
                """, (creator_id_resolved,)).fetchone()

                if density_row and density_row["send_count"]:
                    sends_14d = density_row["send_count"]
                    # Saturation estimate: high sends = high saturation
                    sat = min(100, int((sends_14d / 28) * 100))  # 2 sends/day = 100%
                    opp = 100 - sat

                # Get decline weeks from weekly earnings trend
                weekly_rows = conn.execute("""
                    SELECT
                        strftime('%Y-%W', sent_date) as week,
                        SUM(earnings) as weekly_earnings
                    FROM mass_messages
                    WHERE creator_id = ?
                      AND sent_date >= date('now', '-56 days')
                    GROUP BY week
                    ORDER BY week DESC
                    LIMIT 8
                """, (creator_id_resolved,)).fetchall()

                # Convert to expected format and use shared function
                weekly_data = [{"week": row["week"], "weekly_earnings": row["weekly_earnings"]}
                               for row in weekly_rows]
                decline = calc_consecutive_decline_weeks(weekly_data)

        except Exception as e:
            logger.warning(f"Could not calculate health: {e}")

        health_calc = calc_health_status(sat, decline)
        health = {
            "status": health_calc["status"],
            "saturation_score": sat,
            "opportunity_score": opp,
            "decline_weeks": decline,
            "volume_adjustment": health_calc["volume_adjustment"],
        }

    # =========================================================================
    # BUMP MULTIPLIER
    # =========================================================================
    bump_multiplier = calc_bump_multiplier(content_category or "softcore", tier)

    # =========================================================================
    # WEEKLY DISTRIBUTION (THE KEY DIFFERENTIATOR)
    # =========================================================================
    week_dates = get_week_dates(week_start)
    weekly_distribution = {}
    calendar_boosts = []
    boost_dates = []

    for d in week_dates:
        day_name = get_day_name(d)

        # Calculate boosts
        cal_boost = calc_calendar_boost(d)
        wknd_boost = calc_weekend_boost(d)
        day_multiplier = cal_boost * wknd_boost * trigger_multiplier

        # Track calendar boosts
        if cal_boost > 1.0:
            reason = "holiday" if cal_boost >= 1.30 else "payday"
            calendar_boosts.append({
                "date": d.isoformat(),
                "boost": cal_boost,
                "reason": reason
            })
            boost_dates.append(d.isoformat())

        # Calculate adjusted volumes for the day
        # Base from tier midpoint + health adjustment, then apply day multiplier
        rev_base = (base_ranges["revenue"][0] + base_ranges["revenue"][1]) / 2
        eng_base = (base_ranges["engagement"][0] + base_ranges["engagement"][1]) / 2
        ret_base = (base_ranges["retention"][0] + base_ranges["retention"][1]) / 2

        rev_adjusted = int(round(rev_base * day_multiplier + health["volume_adjustment"]))
        eng_adjusted = int(round(eng_base * day_multiplier + health["volume_adjustment"]))
        ret_adjusted = int(round(ret_base * day_multiplier))  # Retention not boosted by health

        # Clamp to reasonable ranges (min 1, max 2x tier max)
        rev_adjusted = max(1, min(rev_adjusted, base_ranges["revenue"][1] * 2))
        eng_adjusted = max(1, min(eng_adjusted, base_ranges["engagement"][1] * 2))
        ret_adjusted = max(1, min(ret_adjusted, base_ranges["retention"][1] * 2))

        # Get prime hours for this day (using string key)
        prime = PRIME_HOURS.get(day_name, PRIME_HOURS["monday"])

        weekly_distribution[day_name] = {
            "date": d.isoformat(),
            "revenue": rev_adjusted,
            "engagement": eng_adjusted,
            "retention": ret_adjusted,
            "prime_hours": {
                "revenue": prime[:2] if len(prime) >= 2 else prime,
                "engagement": prime[1:] if len(prime) >= 2 else prime,
                "retention": [(8, 10), (18, 20)]  # Off-peak for retention
            },
            "calendar_boost": cal_boost,
            "weekend_boost": wknd_boost,
            "day_multiplier": round(day_multiplier, 3)
        }

    # =========================================================================
    # COMPUTE CONFIG HASH
    # =========================================================================
    config_hash = compute_volume_config_hash(
        tier=tier,
        trigger_multiplier=round(trigger_multiplier, 4),
        health_adjustment=health["volume_adjustment"],
        week_start=week_start,
        boost_dates=boost_dates
    )

    hash_inputs = [
        f"tier:{tier}",
        f"trigger_mult:{round(trigger_multiplier, 4)}",
        f"health_adj:{health['volume_adjustment']}",
        f"week:{week_start}",
        f"boosts:{','.join(sorted(boost_dates)) if boost_dates else 'none'}"
    ]

    # =========================================================================
    # BUILD RESPONSE
    # =========================================================================
    return {
        "creator_id": creator_id_resolved,
        "week_start": week_start,
        "tier": tier,
        "tier_source": tier_source,
        "tier_confidence": tier_confidence,

        "base_ranges": {
            "revenue": list(base_ranges["revenue"]),
            "engagement": list(base_ranges["engagement"]),
            "retention": list(base_ranges["retention"]),
        },

        "trigger_multiplier": round(trigger_multiplier, 4),
        "triggers_applied": triggers_applied,
        "trigger_details": trigger_details,

        "health": health,

        "bump_multiplier": round(bump_multiplier, 2),
        "content_category": content_category,

        "weekly_distribution": weekly_distribution,
        "calendar_boosts": calendar_boosts,

        "temporal_context": {
            "week_type": week_type,
            "data_accuracy": {
                "calendar_boosts": "exact",
                "tier": "exact" if tier_source == "override" else "current_state",
                "triggers": triggers_source,
                "health": health_source
            }
        },

        "metadata": {
            "fetched_at": fetched_at,
            "volume_config_hash": config_hash,
            "hash_inputs": hash_inputs,
            "mm_revenue_monthly": round(mm_revenue, 2) if mm_revenue else None,
            "current_fan_count": fan_count,
            "page_type": page_type
        }
    }


@mcp.tool()
def get_active_volume_triggers(creator_id: str) -> dict:
    """Returns active performance-based volume triggers with compound calculations.

    MCP Name: mcp__eros-db__get_active_volume_triggers
    Version: 2.0.0

    This tool retrieves PERSISTED triggers from the database only.
    Runtime trigger detection happens separately in preflight.py._detect_triggers().

    Args:
        creator_id: Creator identifier (creator_id or page_name)

    Returns:
        dict with structure:
        - creator_id: Input echoed
        - creator_id_resolved: Actual DB key used
        - triggers: List of active trigger objects
        - count: Number of triggers
        - compound_multiplier: Pre-calculated compound (clamped to [0.50, 2.00])
        - compound_calculation: Per-content-type breakdown
        - has_conflicting_signals: True if BOOST and REDUCE triggers coexist
        - creator_context: Fan count and tier for scale interpretation
        - zero_triggers_context: Diagnostics when count=0 (null otherwise)
        - metadata: Hash, timestamps, thresholds version

    Response Stability:
        STABLE: creator_id, triggers, count, all trigger fields
        ADDED v2.0: compound_*, metadata, creator_context, zero_triggers_context

    See Also:
        - save_volume_triggers: Persist new triggers
        - volume_utils.TRIGGER_THRESHOLDS: Detection criteria constants
        - preflight._detect_triggers: Runtime detection logic
    """
    import hashlib
    from datetime import datetime
    # CRITICAL: Use relative import (we're inside mcp_server/)
    from .volume_utils import (
        TRIGGER_MULT_MIN, TRIGGER_MULT_MAX,
        calculate_compound_multiplier,
        ZERO_TRIGGER_REASONS
    )

    start_time = datetime.now()
    logger.info(f"get_active_volume_triggers: creator_id={creator_id}")

    # Validate input
    if not creator_id or not creator_id.strip():
        return {
            "error": "creator_id is required",
            "error_code": "INVALID_INPUT",
            "creator_id": creator_id,
            "triggers": [],
            "count": 0
        }

    creator_id_resolved = None
    creator_context = {"fan_count": 0, "tier": "MINIMAL", "page_type": "paid"}

    try:
        with get_db_connection() as conn:
            # Resolve creator_id or page_name
            creator_row = conn.execute("""
                SELECT c.creator_id, c.page_name, c.current_fan_count, c.page_type,
                       (SELECT volume_level FROM volume_assignments
                        WHERE creator_id = c.creator_id AND is_active = 1
                        ORDER BY assigned_at DESC LIMIT 1) as tier
                FROM creators c
                WHERE c.creator_id = ? OR c.page_name = ?
                LIMIT 1
            """, (creator_id, creator_id)).fetchone()

            if not creator_row:
                return {
                    "error": f"Creator not found: {creator_id}",
                    "error_code": "CREATOR_NOT_FOUND",
                    "creator_id": creator_id,
                    "triggers": [],
                    "count": 0
                }

            creator_id_resolved = creator_row[0]
            creator_context = {
                "fan_count": creator_row[2] or 0,
                "tier": creator_row[4] or "MINIMAL",
                "page_type": creator_row[3] or "paid"
            }

            # Fetch active triggers
            triggers_rows = conn.execute("""
                SELECT
                    vt.trigger_id,
                    vt.content_type,
                    vt.trigger_type,
                    vt.adjustment_multiplier,
                    vt.confidence,
                    vt.reason,
                    vt.expires_at,
                    vt.detected_at,
                    vt.metrics_json,
                    vt.applied_count,
                    vt.last_applied_at,
                    vt.detection_count,
                    vt.first_detected_at,
                    CAST(julianday(vt.expires_at) - julianday('now') AS INTEGER) as days_until_expiry,
                    CAST(julianday('now') - julianday(vt.detected_at) AS INTEGER) as days_since_detected,
                    CAST(julianday('now') - julianday(vt.first_detected_at) AS INTEGER) as days_since_first_detected
                FROM volume_triggers vt
                WHERE vt.creator_id = ?
                  AND vt.is_active = 1
                  AND (vt.expires_at IS NULL OR vt.expires_at > datetime('now'))
                ORDER BY vt.adjustment_multiplier DESC
            """, (creator_id_resolved,)).fetchall()

            # Build trigger objects
            triggers = []
            trigger_ids = []
            for row in triggers_rows:
                metrics_json = {}
                if row[8]:
                    try:
                        metrics_json = json.loads(row[8])
                    except json.JSONDecodeError:
                        metrics_json = {}

                trigger_ids.append(row[0])
                triggers.append({
                    "trigger_id": row[0],
                    "content_type": row[1],
                    "trigger_type": row[2],
                    "adjustment_multiplier": row[3],
                    "confidence": row[4],
                    "reason": row[5],
                    "expires_at": row[6],
                    "detected_at": row[7],
                    "metrics_json": metrics_json,
                    "source": "database",
                    "applied_count": row[9] or 0,
                    "last_applied_at": row[10],
                    "detection_count": row[11] or 1,
                    "first_detected_at": row[12],
                    "days_until_expiry": row[13],
                    "days_since_detected": row[14],
                    "days_since_first_detected": row[15]
                })

            # Calculate compound multiplier
            compound_mult, compound_calc, has_conflict = calculate_compound_multiplier(triggers)

            # Zero triggers diagnostics (only when count=0)
            zero_context = None
            if not triggers:
                diag_row = conn.execute("""
                    SELECT
                        MAX(CASE WHEN expires_at <= datetime('now') OR is_active = 0
                            THEN expires_at END) as last_trigger_expired_at,
                        (SELECT trigger_type FROM volume_triggers
                         WHERE creator_id = ? ORDER BY detected_at DESC LIMIT 1) as last_trigger_type,
                        (SELECT content_type FROM volume_triggers
                         WHERE creator_id = ? ORDER BY detected_at DESC LIMIT 1) as last_trigger_content_type,
                        COUNT(*) as historical_trigger_count,
                        SUM(CASE WHEN expires_at > datetime('now', '-7 days')
                                 AND expires_at <= datetime('now') THEN 1 ELSE 0 END) as triggers_expired_last_7d
                    FROM volume_triggers
                    WHERE creator_id = ?
                """, (creator_id_resolved, creator_id_resolved, creator_id_resolved)).fetchone()

                # Determine reason
                hist_count = diag_row[3] or 0
                expired_7d = diag_row[4] or 0

                if hist_count == 0:
                    reason = "never_had_triggers"
                elif expired_7d > 0:
                    reason = "all_expired"
                else:
                    reason = "no_qualifying_performance"

                zero_context = {
                    "reason": reason,
                    "reason_description": ZERO_TRIGGER_REASONS.get(reason, ""),
                    "last_trigger_expired_at": diag_row[0],
                    "last_trigger_type": diag_row[1],
                    "last_trigger_content_type": diag_row[2],
                    "historical_trigger_count": hist_count,
                    "triggers_expired_last_7d": expired_7d
                }

            # Compute hash for cache invalidation
            hash_inputs = [
                f"creator:{creator_id_resolved}",
                f"trigger_ids:{sorted(trigger_ids)}",
                f"expires:{[t['expires_at'] for t in triggers]}"
            ]
            triggers_hash = hashlib.sha256(
                json.dumps(hash_inputs, sort_keys=True).encode()
            ).hexdigest()[:16]

            query_ms = (datetime.now() - start_time).total_seconds() * 1000

            return {
                "creator_id": creator_id,
                "creator_id_resolved": creator_id_resolved,
                "triggers": triggers,
                "count": len(triggers),
                "compound_multiplier": compound_mult,
                "compound_calculation": compound_calc,
                "has_conflicting_signals": has_conflict,
                "creator_context": creator_context,
                "zero_triggers_context": zero_context,
                "metadata": {
                    "fetched_at": datetime.now().isoformat() + "Z",
                    "triggers_hash": f"sha256:{triggers_hash}",
                    "hash_inputs": hash_inputs,
                    "query_ms": round(query_ms, 2),
                    "thresholds_version": "2.0",
                    "scale_aware": True
                }
            }

    except Exception as e:
        logger.error(f"get_active_volume_triggers error: {e}")
        return {
            "error": f"Database error: {str(e)}",
            "error_code": "DATABASE_ERROR",
            "creator_id": creator_id,
            "triggers": [],
            "count": 0
        }


@mcp.tool()
def get_performance_trends(creator_id: str, period: str = "14d") -> dict:
    """Returns performance trends for health and saturation detection.

    MCP Name: mcp__eros-db__get_performance_trends

    Args:
        creator_id: Creator identifier
        period: Analysis period ("7d", "14d", or "30d")

    Returns:
        Performance metrics including saturation indicators, health status,
        and volume adjustment recommendations.
    """
    start_time = time.time()
    logger.info(f"get_performance_trends: creator_id={creator_id}, period={period}")

    # Validate period parameter (BUG-004 fix)
    valid_periods = {"7d", "14d", "30d"}
    if period not in valid_periods:
        return {
            "error": f"Invalid period: {period}. Must be one of {valid_periods}",
            "error_code": "INVALID_PERIOD",
            "creator_id": creator_id
        }
    period_days = int(period.replace('d', ''))

    try:
        # Use resolve_creator_id helper for consistent creator resolution
        resolved = resolve_creator_id(creator_id)
        if not resolved.get("found"):
            return {
                "error": f"Creator not found: {creator_id}",
                "error_code": "CREATOR_NOT_FOUND",
                "creator_id": creator_id
            }
        creator_pk = resolved["creator_id"]

        # Query performance metrics (BUG-003 fix: use sent_date not imported_at)
        metrics = db_query("""
            SELECT
                CASE WHEN SUM(purchased_count) > 0
                     THEN SUM(earnings) / SUM(purchased_count)
                     ELSE 0 END as avg_rps,
                CASE WHEN SUM(viewed_count) > 0
                     THEN 1.0 * SUM(purchased_count) / SUM(viewed_count)
                     ELSE 0 END as avg_conversion,
                CASE WHEN SUM(sent_count) > 0
                     THEN 1.0 * SUM(viewed_count) / SUM(sent_count)
                     ELSE 0 END as avg_open_rate,
                SUM(earnings) as total_earnings,
                COUNT(*) as total_sends,
                MIN(sent_date) as first_send,
                MAX(sent_date) as last_send
            FROM mass_messages
            WHERE creator_id = ?
            AND sent_date >= date('now', ?)
        """, (creator_pk, f'-{period_days} days'))

        # Handle empty/insufficient data case
        sends_in_period = (metrics[0].get('total_sends') or 0) if metrics else 0
        if not metrics or sends_in_period == 0:
            logger.warning(f"get_performance_trends: insufficient data for {creator_id}, sends={sends_in_period}")
            empty_hash = hashlib.sha256(f'empty:{creator_pk}'.encode()).hexdigest()[:16]
            return {
                "creator_id": creator_id,
                "creator_id_resolved": creator_pk,
                "period": period,
                "health_status": "HEALTHY",
                "saturation_score": 50,
                "opportunity_score": 50,
                "consecutive_decline_weeks": 0,
                "volume_adjustment": 0,
                "avg_rps": 0.0,
                "avg_conversion": 0.0,
                "avg_open_rate": 0.0,
                "total_earnings": 0.0,
                "total_sends": 0,
                "date_range": {"start": None, "end": None},
                "revenue_trend_pct": None,
                "engagement_trend_pct": None,
                "trend_period": "wow",
                "data_confidence": "low",
                "insufficient_data": True,
                "metadata": {
                    "fetched_at": datetime.now().isoformat() + "Z",
                    "trends_hash": f"sha256:{empty_hash}",
                    "hash_inputs": [f"creator:{creator_pk}", "empty:true"],
                    "query_ms": round((time.time() - start_time) * 1000, 2),
                    "data_age_days": None,
                    "is_stale": True,
                    "has_period_data": False,
                    "sends_in_period": 0,
                    "period_days": period_days,
                    "expected_sends": period_days * 2,
                    "staleness_threshold_days": 14
                }
            }

        m = dict(metrics[0])

        # Calculate saturation dynamically (BUG-001 fix)
        expected_sends = period_days * 2  # 2 sends/day baseline
        saturation_score = min(100, int((sends_in_period / expected_sends) * 100)) if expected_sends > 0 else 0
        opportunity_score = 100 - saturation_score

        # Query for weekly earnings (8 weeks for decline detection) (BUG-002 fix)
        weekly_query = """
            SELECT
                strftime('%Y-%W', sent_date) as week,
                SUM(earnings) as weekly_earnings,
                SUM(COALESCE(viewed_count, 0)) as weekly_views
            FROM mass_messages
            WHERE creator_id = ?
              AND sent_date >= date('now', '-56 days')
            GROUP BY week
            ORDER BY week DESC
            LIMIT 8
        """
        weekly_rows = db_query(weekly_query, (creator_pk,))

        # Convert query results to expected format for shared function
        weekly_data = [{"week": row.get("week"), "weekly_earnings": row.get("weekly_earnings")}
                       for row in (weekly_rows or [])]

        # Use shared function for decline calculation
        consecutive_decline_weeks = calc_consecutive_decline_weeks(weekly_data)

        # Calculate health status using volume_utils (already imported)
        health_result = calc_health_status(saturation_score, consecutive_decline_weeks)
        health_status = health_result["status"]
        volume_adjustment = health_result["volume_adjustment"]

        # Get data age from metrics
        last_sent_date = m.get('last_send') or m.get('last_sent_date')
        if last_sent_date:
            try:
                if 'T' in str(last_sent_date):
                    data_age_days = (datetime.now() - datetime.fromisoformat(str(last_sent_date).replace('Z', '+00:00').replace('+00:00', ''))).days
                else:
                    data_age_days = (datetime.now().date() - datetime.strptime(str(last_sent_date), '%Y-%m-%d').date()).days
            except:
                data_age_days = None
        else:
            data_age_days = None

        # Data confidence based on sample size and age
        if sends_in_period >= 20 and data_age_days is not None and data_age_days <= 7:
            data_confidence = "high"
        elif sends_in_period >= 10 or (data_age_days is not None and data_age_days <= 14):
            data_confidence = "moderate"
        else:
            data_confidence = "low"

        # Insufficient data flag
        insufficient_data = sends_in_period < 10

        # Calculate WoW trends from weekly data
        if len(weekly_data) >= 2:
            curr_rev = weekly_data[0].get("weekly_earnings") or 0
            prev_rev = weekly_data[1].get("weekly_earnings") or 0
            revenue_trend_pct = round(((curr_rev - prev_rev) / prev_rev * 100), 1) if prev_rev > 0 else None

            # For engagement trend, use views from query
            if weekly_rows and len(weekly_rows) >= 2:
                curr_views = weekly_rows[0].get("weekly_views") or 0
                prev_views = weekly_rows[1].get("weekly_views") or 0
                engagement_trend_pct = round(((curr_views - prev_views) / prev_views * 100), 1) if prev_views > 0 else None
            else:
                engagement_trend_pct = None
        else:
            revenue_trend_pct = None
            engagement_trend_pct = None

        # Staleness flags
        STALENESS_THRESHOLD_DAYS = 14
        is_stale = data_age_days is None or data_age_days > STALENESS_THRESHOLD_DAYS
        has_period_data = sends_in_period > 0

        # Calculate hash for cache invalidation
        hash_inputs = [
            f"creator:{creator_pk}",
            f"period:{period}",
            f"saturation:{saturation_score}",
            f"decline:{consecutive_decline_weeks}",
            f"health:{health_status}",
            f"sends:{sends_in_period}",
            f"last_data:{last_sent_date or 'none'}"
        ]
        trends_hash = hashlib.sha256(
            json.dumps(hash_inputs, sort_keys=True).encode()
        ).hexdigest()[:16]

        # Query timing
        query_ms = round((time.time() - start_time) * 1000, 2)

        # Build metadata block
        metadata = {
            "fetched_at": datetime.now().isoformat() + "Z",
            "trends_hash": f"sha256:{trends_hash}",
            "hash_inputs": hash_inputs,
            "query_ms": query_ms,
            "data_age_days": data_age_days,
            "is_stale": is_stale,
            "has_period_data": has_period_data,
            "sends_in_period": sends_in_period,
            "period_days": period_days,
            "expected_sends": expected_sends,
            "staleness_threshold_days": STALENESS_THRESHOLD_DAYS
        }

        return {
            # Existing fields (MUST KEEP for backwards compatibility)
            "creator_id": creator_id,
            "creator_id_resolved": creator_pk,
            "period": period,
            "health_status": health_status,
            "avg_rps": round(m.get('avg_rps') or 0, 2),
            "avg_conversion": round((m.get('avg_conversion') or 0) * 100, 1),  # Convert to percentage
            "avg_open_rate": round((m.get('avg_open_rate') or 0) * 100, 1),    # Convert to percentage
            "total_earnings": round(m.get('total_earnings') or 0, 2),
            "total_sends": sends_in_period,
            "saturation_score": saturation_score,
            "opportunity_score": opportunity_score,
            "date_range": {
                "start": m.get('first_send'),
                "end": m.get('last_send')
            },

            # New fields from Phase 1/2
            "consecutive_decline_weeks": consecutive_decline_weeks,
            "volume_adjustment": volume_adjustment,

            # NEW: Enhanced fields from Phase 3
            "revenue_trend_pct": revenue_trend_pct,
            "engagement_trend_pct": engagement_trend_pct,
            "trend_period": "wow",  # Documents comparison type
            "data_confidence": data_confidence,
            "insufficient_data": insufficient_data,

            # NEW: Metadata block
            "metadata": metadata
        }

    except Exception as e:
        logger.error(f"get_performance_trends error: {e}")
        return {
            "error": str(e),
            "error_code": "DATABASE_ERROR",
            "creator_id": creator_id
        }


@mcp.tool()
def save_schedule(
    creator_id: str,
    week_start: str,
    items: list,
    validation_certificate: dict = None
) -> dict:
    """Persists generated schedule with validation certificate.

    MCP Name: mcp__eros-db__save_schedule
    Version: 2.0.0

    CRITICAL FIX v2.0: Corrected column names per schedule_templates schema:
    - week_start (NOT week_start_date)
    - generation_metadata (NOT schedule_json)
    - status (NOT validation_status)
    - total_items (NOT item_count)
    - generated_at (NOT created_at)
    - week_end (required, was missing)

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        week_start: Week start date (YYYY-MM-DD)
        items: List of schedule items from Generator phase
        validation_certificate: Optional ValidationCertificate from Validator phase

    Returns:
        Success: schedule_id, status, metadata, certificate_summary, replaced info
        Failure: error, error_code, validation_errors

    Error Codes:
        - CREATOR_NOT_FOUND: creator_id/page_name not in database
        - VALIDATION_ERROR: items failed structural validation
        - INVALID_DATE: week_start not in YYYY-MM-DD format
        - SCHEDULE_LOCKED: cannot replace schedule with status 'queued'
        - SCHEDULE_COMPLETED: cannot replace schedule with status 'completed'
        - DATABASE_ERROR: SQLite operation failed

    Duplicate Handling (UPSERT):
        - draft/approved: UPDATE existing (returns replaced=true)
        - queued: REJECT with SCHEDULE_LOCKED
        - completed: REJECT with SCHEDULE_COMPLETED
    """
    from .volume_utils import (
        validate_schedule_items,
        validate_certificate_freshness,
        compute_schedule_hash
    )
    import time
    from datetime import datetime, timedelta

    start_time = time.time()
    warnings: list[str] = []

    logger.info(f"save_schedule: creator_id={creator_id}, week_start={week_start}, items={len(items) if items else 0}")

    # ==========================================================================
    # LAYER 1: Input Validation
    # ==========================================================================

    if not creator_id or not str(creator_id).strip():
        return {
            "success": False,
            "error": "creator_id is required",
            "error_code": "VALIDATION_ERROR"
        }

    try:
        week_start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": f"week_start must be YYYY-MM-DD format, got: {week_start}",
            "error_code": "INVALID_DATE"
        }

    # ==========================================================================
    # LAYER 2: Items Validation
    # ==========================================================================

    is_valid, validation_errors = validate_schedule_items(items)
    if not is_valid:
        return {
            "success": False,
            "error": "Items validation failed",
            "error_code": "VALIDATION_ERROR",
            "validation_errors": validation_errors,
            "creator_id": creator_id
        }

    # ==========================================================================
    # LAYER 3: Certificate Freshness (soft gate)
    # ==========================================================================

    is_fresh, freshness_error = validate_certificate_freshness(validation_certificate)
    certificate_valid = is_fresh

    if not is_fresh and freshness_error:
        warnings.append(f"Certificate freshness: {freshness_error} - status downgraded to 'draft'")
        logger.warning(f"save_schedule: certificate not fresh - {freshness_error}")

    # Item count consistency check
    if validation_certificate:
        cert_item_count = validation_certificate.get("items_validated")
        if cert_item_count is not None and cert_item_count != len(items):
            warnings.append(f"Item count mismatch: certificate validated {cert_item_count}, received {len(items)}")

    # ==========================================================================
    # LAYER 4: Database Operations
    # ==========================================================================

    try:
        with get_db_connection() as conn:
            # Resolve creator_id
            creator_row = conn.execute("""
                SELECT creator_id FROM creators
                WHERE creator_id = ? OR page_name = ?
                LIMIT 1
            """, (creator_id, creator_id)).fetchone()

            if not creator_row:
                return {
                    "success": False,
                    "error": f"Creator not found: {creator_id}",
                    "error_code": "CREATOR_NOT_FOUND",
                    "creator_id": creator_id
                }

            creator_pk = creator_row[0]

            # Calculate week_end
            week_end_dt = week_start_dt + timedelta(days=6)
            week_end = week_end_dt.strftime("%Y-%m-%d")

            # Check for existing schedule (status-aware UPSERT)
            existing = conn.execute("""
                SELECT template_id, status, generation_metadata
                FROM schedule_templates
                WHERE creator_id = ? AND week_start = ?
            """, (creator_pk, week_start)).fetchone()

            replaced = False
            previous_template_id = None
            previous_status = None
            previous_hash = None

            if existing:
                previous_template_id = existing[0]
                previous_status = existing[1]
                previous_metadata_raw = existing[2]

                # Extract previous hash for audit
                if previous_metadata_raw:
                    try:
                        prev_meta = json.loads(previous_metadata_raw) if isinstance(previous_metadata_raw, str) else previous_metadata_raw
                        previous_hash = prev_meta.get("schedule_hash")
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Status-aware replacement rules
                if previous_status in ("queued", "completed"):
                    error_code = "SCHEDULE_LOCKED" if previous_status == "queued" else "SCHEDULE_COMPLETED"
                    return {
                        "success": False,
                        "error": f"Cannot replace schedule with status '{previous_status}'",
                        "error_code": error_code,
                        "creator_id": creator_id,
                        "week_start": week_start,
                        "existing_template_id": previous_template_id,
                        "existing_status": previous_status
                    }
                else:
                    replaced = True
                    logger.info(f"save_schedule: replacing template_id={previous_template_id} status={previous_status}")

            # Compute schedule hash
            schedule_hash = compute_schedule_hash(items)

            # Determine status
            if validation_certificate and certificate_valid:
                cert_status = validation_certificate.get("validation_status", "").upper()
                status = "approved" if cert_status == "APPROVED" else "draft"
            else:
                status = "draft"

            # Build generation_metadata
            generation_metadata = {
                "items": items,
                "schedule_hash": schedule_hash,
                "item_count": len(items),
                "generated_at": datetime.now().isoformat() + "Z"
            }

            if validation_certificate:
                generation_metadata["validation_certificate"] = validation_certificate

            if replaced:
                generation_metadata["revision"] = {
                    "replaced_at": datetime.now().isoformat() + "Z",
                    "previous_template_id": previous_template_id,
                    "previous_status": previous_status,
                    "previous_hash": previous_hash
                }

            # Execute INSERT or UPDATE
            cursor = conn.cursor()

            if replaced:
                cursor.execute("""
                    UPDATE schedule_templates
                    SET week_end = ?,
                        generated_at = datetime('now'),
                        total_items = ?,
                        status = ?,
                        generation_metadata = ?
                    WHERE template_id = ?
                """, (
                    week_end,
                    len(items),
                    status,
                    json.dumps(generation_metadata),
                    previous_template_id
                ))
                schedule_id = previous_template_id
            else:
                cursor.execute("""
                    INSERT INTO schedule_templates (
                        creator_id,
                        week_start,
                        week_end,
                        generated_at,
                        total_items,
                        status,
                        generation_metadata
                    ) VALUES (?, ?, ?, datetime('now'), ?, ?, ?)
                """, (
                    creator_pk,
                    week_start,
                    week_end,
                    len(items),
                    status,
                    json.dumps(generation_metadata)
                ))
                schedule_id = cursor.lastrowid

            conn.commit()
            logger.info(f"Schedule saved: id={schedule_id}, status={status}, items={len(items)}, replaced={replaced}")

            # ==========================================================================
            # Build Response
            # ==========================================================================

            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            response = {
                "success": True,
                "schedule_id": schedule_id,
                "template_id": schedule_id,  # Backwards compatibility
                "items_saved": len(items),
                "creator_id": creator_id,
                "creator_id_resolved": creator_pk,
                "week_start": week_start,
                "week_end": week_end,
                "status": status,
                "has_certificate": validation_certificate is not None,
                "metadata": {
                    "saved_at": datetime.now().isoformat() + "Z",
                    "query_ms": elapsed_ms,
                    "schedule_hash": schedule_hash
                }
            }

            # Certificate summary
            if validation_certificate:
                cert_age_seconds = None
                ts = validation_certificate.get("validation_timestamp")
                if ts:
                    try:
                        cert_time = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                        cert_age_seconds = round((datetime.now(cert_time.tzinfo) - cert_time).total_seconds())
                    except (ValueError, TypeError):
                        pass

                response["certificate_summary"] = {
                    "validation_status": validation_certificate.get("validation_status"),
                    "quality_score": validation_certificate.get("quality_score"),
                    "items_validated": validation_certificate.get("items_validated"),
                    "is_fresh": certificate_valid,
                    "age_seconds": cert_age_seconds
                }

            # Replacement info
            if replaced:
                response["replaced"] = True
                response["previous_template_id"] = previous_template_id
                response["previous_status"] = previous_status
                if previous_hash:
                    response["metadata"]["previous_schedule_hash"] = previous_hash
            else:
                response["replaced"] = False

            # Warnings
            if warnings:
                response["warnings"] = warnings

            return response

    except sqlite3.IntegrityError as e:
        error_msg = str(e)
        logger.error(f"save_schedule integrity error: {e}")

        if "UNIQUE constraint" in error_msg:
            return {
                "success": False,
                "error": f"Schedule already exists for {creator_id} week {week_start}",
                "error_code": "DUPLICATE_SCHEDULE",
                "creator_id": creator_id,
                "week_start": week_start
            }

        return {
            "success": False,
            "error": f"Integrity error: {error_msg}",
            "error_code": "DATABASE_ERROR",
            "creator_id": creator_id
        }

    except Exception as e:
        logger.error(f"save_schedule error: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}",
            "error_code": "DATABASE_ERROR",
            "creator_id": creator_id
        }


@mcp.tool()
def save_volume_triggers(creator_id: str, triggers: list) -> dict:
    """Persists detected volume triggers with validation and detection tracking.

    MCP Name: mcp__eros-db__save_volume_triggers
    Version: 3.0.0

    BREAKING CHANGE v3.0: Return schema now includes created_ids and updated_ids

    Changes from v2.0:
    - Replace INSERT OR REPLACE with ON CONFLICT DO UPDATE
    - Add detection_count increment on re-detection
    - Preserve first_detected_at on updates
    - Add structured overwrite_warnings for direction flip and large delta
    - Add metadata block with persisted_at, execution_ms, triggers_hash

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        triggers: List of trigger objects to persist

    Trigger Object Schema:
        REQUIRED: trigger_type, content_type, adjustment_multiplier
        OPTIONAL: confidence (default 'moderate'), reason, expires_at (default +7d), metrics_json

    Returns:
        dict with:
        - success: bool
        - triggers_saved: int (total created + updated)
        - created_ids: list[int] - trigger IDs for newly created triggers
        - updated_ids: list[int] - trigger IDs for updated triggers
        - creator_id: echoed input
        - creator_id_resolved: int - resolved creator PK
        - warnings: list[str] if suspicious values detected (backward compatible)
        - overwrite_warnings: list[dict] if direction flips or large deltas detected
        - metadata: dict with persisted_at, execution_ms, triggers_hash
        - error: str if failed
        - validation_errors: list[str] if validation failed

    Validation:
        - Rejects entire batch if ANY trigger has invalid required fields
        - Defaults optional fields gracefully
        - Warns but accepts extreme multiplier values

    See Also:
        - volume_utils.validate_trigger: Validation function
        - get_active_volume_triggers: Retrieve persisted triggers
    """
    # Timing instrumentation
    start_time = datetime.now()

    # CRITICAL: Use relative import (we're inside mcp_server/)
    from .volume_utils import validate_trigger

    logger.info(f"save_volume_triggers: creator_id={creator_id}, triggers={len(triggers)}")

    # ============================================================
    # LAYER 1: INPUT - Validate creator_id, empty list check
    # ============================================================
    if not triggers:
        return {
            "success": True,
            "triggers_saved": 0,
            "created_ids": [],
            "updated_ids": [],
            "creator_id": creator_id,
            "message": "No triggers to save"
        }

    try:
        with get_db_connection() as conn:
            creator_row = conn.execute("""
                SELECT creator_id FROM creators
                WHERE creator_id = ? OR page_name = ?
                LIMIT 1
            """, (creator_id, creator_id)).fetchone()

            if not creator_row:
                return {
                    "success": False,
                    "error": f"Creator not found: {creator_id}",
                    "error_code": "CREATOR_NOT_FOUND",
                    "creator_id": creator_id
                }

            creator_pk = creator_row[0]

            # ============================================================
            # LAYER 1.5: BATCH SIZE CHECK
            # ============================================================
            all_warnings = []
            LARGE_BATCH_THRESHOLD = 20
            if len(triggers) > LARGE_BATCH_THRESHOLD:
                all_warnings.append(
                    f"Large batch: {len(triggers)} triggers (threshold: {LARGE_BATCH_THRESHOLD}). "
                    f"Consider reviewing trigger detection logic."
                )

            # ============================================================
            # LAYER 2: VALIDATION - validate_trigger(), collect all errors
            # ============================================================
            validated = []
            validation_errors = []

            for i, trigger in enumerate(triggers):
                is_valid, result = validate_trigger(trigger, i)
                if is_valid:
                    validated.append(result)
                    if result.get("_warnings"):
                        all_warnings.extend(result["_warnings"])
                else:
                    validation_errors.append(result)

            # Reject entire batch if ANY trigger invalid
            if validation_errors:
                return {
                    "success": False,
                    "error": "Validation failed",
                    "error_code": "VALIDATION_ERROR",
                    "validation_errors": validation_errors,
                    "triggers_rejected": len(validation_errors),
                    "triggers_valid": len(validated),
                    "creator_id": creator_id
                }

            # ============================================================
            # LAYER 3: PRE-QUERY - Query existing rows, detect overwrites
            # ============================================================
            existing_triggers = {}
            if validated:
                # Build query for existing triggers by (content_type, trigger_type)
                params = [creator_pk]
                conditions = []
                for t in validated:
                    conditions.append("(content_type = ? AND trigger_type = ?)")
                    params.extend([t["content_type"], t["trigger_type"]])

                query = f"""
                    SELECT trigger_id, content_type, trigger_type, adjustment_multiplier,
                           detection_count, first_detected_at
                    FROM volume_triggers
                    WHERE creator_id = ? AND ({" OR ".join(conditions)})
                """

                rows = conn.execute(query, params).fetchall()

                for row in rows:
                    key = (row[1], row[2])  # (content_type, trigger_type)
                    existing_triggers[key] = {
                        "trigger_id": row[0],
                        "adjustment_multiplier": row[3],
                        "detection_count": row[4] or 1,
                        "first_detected_at": row[5]
                    }

            # ============================================================
            # LAYER 3.5: OVERWRITE ANALYSIS
            # ============================================================
            overwrite_warnings = []
            for t in validated:
                key = (t["content_type"], t["trigger_type"])
                if key in existing_triggers:
                    existing = existing_triggers[key]
                    old_mult = existing["adjustment_multiplier"]
                    new_mult = t["adjustment_multiplier"]

                    # Direction flip detection
                    direction_flip = (old_mult > 1.0 and new_mult < 1.0) or \
                                    (old_mult < 1.0 and new_mult > 1.0)

                    # Large delta detection (>50% change)
                    if old_mult != 0:
                        delta_percent = ((new_mult - old_mult) / old_mult) * 100
                    else:
                        delta_percent = 100.0 if new_mult != 0 else 0.0

                    large_delta = abs(delta_percent) > 50

                    if direction_flip or large_delta:
                        overwrite_warnings.append({
                            "trigger_id": existing["trigger_id"],
                            "content_type": t["content_type"],
                            "trigger_type": t["trigger_type"],
                            "old_multiplier": old_mult,
                            "new_multiplier": new_mult,
                            "direction_flip": direction_flip,
                            "delta_percent": round(delta_percent, 1)
                        })

                        # Also add to warnings list for backward compatibility
                        if direction_flip:
                            all_warnings.append(
                                f"direction flip detected ({old_mult} -> {new_mult}) "
                                f"for {t['content_type']}/{t['trigger_type']}"
                            )

            # ============================================================
            # LAYER 4: PERSISTENCE - BEGIN IMMEDIATE, ON CONFLICT UPSERT, COMMIT
            # ============================================================
            try:
                conn.execute("BEGIN IMMEDIATE")

                created_ids = []
                updated_ids = []

                for t in validated:
                    # Remove internal fields
                    t.pop("_warnings", None)

                    # Determine if this is create or update BEFORE INSERT
                    key = (t["content_type"], t["trigger_type"])
                    is_update = key in existing_triggers

                    cursor = conn.execute("""
                        INSERT INTO volume_triggers (
                            creator_id,
                            content_type,
                            trigger_type,
                            adjustment_multiplier,
                            confidence,
                            reason,
                            expires_at,
                            detected_at,
                            is_active,
                            metrics_json,
                            detection_count,
                            first_detected_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 1, ?, 1, datetime('now'))
                        ON CONFLICT (creator_id, content_type, trigger_type) DO UPDATE SET
                            adjustment_multiplier = excluded.adjustment_multiplier,
                            confidence = CASE
                                WHEN excluded.confidence > volume_triggers.confidence THEN excluded.confidence
                                ELSE volume_triggers.confidence
                            END,
                            reason = excluded.reason,
                            expires_at = excluded.expires_at,
                            detected_at = datetime('now'),
                            is_active = 1,
                            metrics_json = excluded.metrics_json,
                            detection_count = volume_triggers.detection_count + 1
                        RETURNING trigger_id
                    """, (
                        creator_pk,
                        t["content_type"],
                        t["trigger_type"],
                        t["adjustment_multiplier"],
                        t["confidence"],
                        t["reason"],
                        t["expires_at"],
                        json.dumps(t["metrics_json"]) if t["metrics_json"] else None
                    ))

                    trigger_id = cursor.fetchone()[0]

                    if is_update:
                        updated_ids.append(trigger_id)
                    else:
                        created_ids.append(trigger_id)
                        # Track for duplicates in same batch
                        existing_triggers[key] = {"trigger_id": trigger_id}

                conn.execute("COMMIT")

            except Exception as e:
                conn.execute("ROLLBACK")
                logger.error(f"save_volume_triggers rollback: {e}")
                raise

            # ============================================================
            # LAYER 5: RESPONSE - Build metadata, compute hash, return
            # ============================================================
            def compute_triggers_hash(validated_triggers: list) -> str:
                """Compute deterministic hash of normalized triggers."""
                # Normalize for hashing: sort by (content_type, trigger_type)
                sorted_triggers = sorted(
                    validated_triggers,
                    key=lambda t: (t["content_type"], t["trigger_type"])
                )

                # Include only fields that affect behavior
                hash_inputs = [
                    {
                        "content_type": t["content_type"],
                        "trigger_type": t["trigger_type"],
                        "adjustment_multiplier": t["adjustment_multiplier"],
                        "confidence": t["confidence"],
                        "expires_at": t["expires_at"]
                    }
                    for t in sorted_triggers
                ]

                hash_str = json.dumps(hash_inputs, sort_keys=True)
                return hashlib.sha256(hash_str.encode()).hexdigest()[:16]

            triggers_hash = compute_triggers_hash(validated)
            execution_ms = (datetime.now() - start_time).total_seconds() * 1000

            return {
                "success": True,
                "triggers_saved": len(created_ids) + len(updated_ids),
                "created_ids": created_ids,
                "updated_ids": updated_ids,
                "creator_id": creator_id,
                "creator_id_resolved": creator_pk,
                "warnings": all_warnings if all_warnings else None,
                "overwrite_warnings": overwrite_warnings if overwrite_warnings else None,
                "metadata": {
                    "persisted_at": datetime.now().isoformat() + "Z",
                    "execution_ms": round(execution_ms, 2),
                    "triggers_hash": f"sha256:{triggers_hash}"
                }
            }

    except Exception as e:
        logger.error(f"save_volume_triggers error: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}",
            "error_code": "DATABASE_ERROR",
            "creator_id": creator_id
        }


# ============================================================
# CAPTION TOOLS (3)
# ============================================================


def _build_caption_error_response(
    error_code: str,
    error_message: str,
    content_types: list
) -> dict:
    """Build consistent error response matching success schema."""
    return {
        "error": error_message,
        "error_code": error_code,
        "creator_id": None,
        "captions_by_type": {},
        "total_captions": 0,
        "types_requested": len(content_types) if isinstance(content_types, list) else 0,
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "error": True
        }
    }


def _build_send_type_error_response(
    error_code: str,
    error_message: str,
    send_type: str
) -> dict:
    """Build consistent error response for send_type caption retrieval."""
    return {
        "error": error_message,
        "error_code": error_code,
        "creator_id": None,
        "resolved_creator_id": None,
        "send_type": send_type,
        "captions": [],
        "count": 0,
        "pool_stats": {
            "total_available": 0,
            "fresh_for_creator": 0,
            "returned_count": 0,
            "has_more": False,
            "avg_pool_performance_tier": None,
            "freshness_ratio": None
        },
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "error": True
        }
    }


@mcp.tool()
def get_batch_captions_by_content_types(
    creator_id: str,
    content_types: list,
    limit_per_type: int = 5,
    schedulable_type: str = None
) -> dict:
    """Batch retrieves captions filtered by content types for PPV selection.

    MCP Name: mcp__eros-db__get_batch_captions_by_content_types
    Version: 2.0.0

    Args:
        creator_id: Creator identifier (required for per-creator freshness)
        content_types: List of content type names to filter (max 50)
        limit_per_type: Max captions per content type (clamped 1-20, default 5)
        schedulable_type: Filter by schedulable type ('ppv', 'ppv_bump', 'wall', or None)

    Returns:
        Dict with captions_by_type (including pool_stats), total_captions,
        types_requested, and metadata block for ValidationCertificate.

    Example:
        get_batch_captions_by_content_types(
            creator_id="alexia",
            content_types=["lingerie", "shower"],
            limit_per_type=5,
            schedulable_type="ppv"
        )
    """
    from datetime import date

    start_time = time.perf_counter()

    logger.info(f"get_batch_captions_by_content_types: creator_id={creator_id}, "
                f"types={len(content_types) if isinstance(content_types, list) else 'invalid'}, "
                f"schedulable_type={schedulable_type}")

    # =========================================================================
    # LAYER 1: Type validation
    # =========================================================================
    if not creator_id or not isinstance(creator_id, str):
        return _build_caption_error_response(
            "INVALID_CREATOR_ID",
            "creator_id must be a non-empty string",
            content_types if isinstance(content_types, list) else []
        )

    if not isinstance(content_types, list):
        return _build_caption_error_response(
            "INVALID_CONTENT_TYPES",
            "content_types must be a list",
            []
        )

    if len(content_types) == 0:
        return _build_caption_error_response(
            "EMPTY_CONTENT_TYPES",
            "content_types cannot be empty",
            []
        )

    if len(content_types) > MAX_CONTENT_TYPES:
        return _build_caption_error_response(
            "CONTENT_TYPES_LIMIT_EXCEEDED",
            f"content_types exceeds maximum of {MAX_CONTENT_TYPES}",
            content_types
        )

    if not all(isinstance(ct, str) for ct in content_types):
        return _build_caption_error_response(
            "INVALID_CONTENT_TYPE_ELEMENTS",
            "All content_types elements must be strings",
            content_types
        )

    if schedulable_type is not None and schedulable_type not in VALID_SCHEDULABLE_TYPES:
        return _build_caption_error_response(
            "INVALID_SCHEDULABLE_TYPE",
            f"schedulable_type must be one of: {', '.join(sorted(VALID_SCHEDULABLE_TYPES))}",
            content_types
        )

    # =========================================================================
    # LAYER 2: Format validation
    # =========================================================================
    is_valid, validation_result = validate_creator_id(creator_id)
    if not is_valid:
        return _build_caption_error_response(
            "INVALID_CREATOR_ID_FORMAT",
            validation_result,
            content_types
        )

    # =========================================================================
    # LAYER 3: Resolution
    # =========================================================================
    resolved = resolve_creator_id(creator_id)
    if not resolved["found"]:
        return _build_caption_error_response(
            "CREATOR_NOT_FOUND",
            f"Creator not found: {creator_id}",
            content_types
        )

    resolved_creator_id = resolved["creator_id"]

    # =========================================================================
    # LAYER 4: Normalize inputs
    # =========================================================================
    limit_per_type = max(1, min(20, limit_per_type))
    unique_content_types = list(dict.fromkeys(content_types))

    # =========================================================================
    # LAYER 5: Execute batched query
    # =========================================================================
    try:
        placeholders = ",".join("?" * len(unique_content_types))

        query_params = (
            [resolved_creator_id] +
            unique_content_types +
            [schedulable_type, schedulable_type] +
            [resolved_creator_id] +
            unique_content_types +
            [schedulable_type, schedulable_type] +
            [limit_per_type]
        )

        batched_query = f"""
        WITH pool_stats AS (
            SELECT
                ct.type_name,
                COUNT(*) as total_available,
                SUM(CASE WHEN ccp.times_used IS NULL OR ccp.times_used = 0 THEN 1 ELSE 0 END) as fresh_for_creator,
                AVG(cb.performance_tier) as avg_pool_performance_tier
            FROM caption_bank cb
            JOIN content_types ct ON cb.content_type_id = ct.content_type_id
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id AND ccp.creator_id = ?
            WHERE ct.type_name IN ({placeholders})
            AND cb.is_active = 1
            AND (? IS NULL OR cb.schedulable_type = ?)
            GROUP BY ct.type_name
        ),
        ranked_captions AS (
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.caption_type as category,
                cb.performance_tier,
                ct.type_name as content_type,
                cb.global_last_used_date as last_used_at,
                cb.global_times_used as use_count,
                cb.suggested_price,
                cb.price_range_min,
                cb.price_range_max,
                cb.avg_purchase_rate,
                ccp.last_used_date as creator_last_used_at,
                ccp.times_used as creator_use_count,
                ROW_NUMBER() OVER (
                    PARTITION BY ct.type_name
                    ORDER BY
                        ccp.last_used_date ASC NULLS FIRST,
                        cb.performance_tier ASC,
                        cb.global_last_used_date ASC NULLS FIRST
                ) as rn
            FROM caption_bank cb
            JOIN content_types ct ON cb.content_type_id = ct.content_type_id
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id AND ccp.creator_id = ?
            WHERE ct.type_name IN ({placeholders})
            AND cb.is_active = 1
            AND (? IS NULL OR cb.schedulable_type = ?)
        )
        SELECT rc.*, ps.total_available, ps.fresh_for_creator, ps.avg_pool_performance_tier
        FROM ranked_captions rc
        JOIN pool_stats ps ON rc.content_type = ps.type_name
        WHERE rc.rn <= ?
        ORDER BY rc.content_type, rc.rn
        """

        rows = db_query(batched_query, tuple(query_params))

        # =====================================================================
        # LAYER 6: Build response structure
        # =====================================================================

        def _compute_days_since(date_str):
            """Compute days since a date string, or None if no date."""
            if not date_str:
                return None
            try:
                used_date = datetime.fromisoformat(str(date_str).replace('Z', '')).date()
                return (date.today() - used_date).days
            except (ValueError, TypeError):
                return None

        captions_by_type = {}
        all_caption_ids = []

        for content_type in unique_content_types:
            type_rows = [r for r in rows if r["content_type"] == content_type]

            if not type_rows:
                captions_by_type[content_type] = {
                    "captions": [],
                    "pool_stats": {
                        "total_available": 0,
                        "fresh_for_creator": 0,
                        "returned_count": 0,
                        "has_more": False,
                        "avg_pool_performance_tier": None
                    }
                }
                continue

            type_captions = []
            for row in type_rows:
                days_since = _compute_days_since(row.get("creator_last_used_at"))
                tier = row.get("performance_tier", 4)

                caption_obj = {
                    "caption_id": row["caption_id"],
                    "caption_text": row["caption_text"],
                    "category": row["category"],
                    "content_type": row["content_type"],
                    "last_used_at": row["last_used_at"],
                    "use_count": row["use_count"] or 0,
                    "performance_tier": tier,
                    "tier_label": CAPTION_TIER_LABELS.get(tier, "UNKNOWN"),
                    "quality_score": CAPTION_TIER_SCORES.get(tier, 0),
                    "creator_last_used_at": row.get("creator_last_used_at"),
                    "creator_use_count": row.get("creator_use_count") or 0,
                    "days_since_creator_used": days_since,
                    "effectively_fresh": days_since is None or days_since >= EFFECTIVELY_FRESH_DAYS,
                    "pricing": {
                        "suggested_price": row.get("suggested_price"),
                        "price_range_min": row.get("price_range_min"),
                        "price_range_max": row.get("price_range_max"),
                        "avg_purchase_rate": row.get("avg_purchase_rate") or 0.0,
                        "has_price_history": row.get("suggested_price") is not None
                    }
                }
                type_captions.append(caption_obj)
                all_caption_ids.append(row["caption_id"])

            first_row = type_rows[0]
            total_available = first_row.get("total_available") or 0
            fresh_for_creator = first_row.get("fresh_for_creator") or 0
            avg_tier = first_row.get("avg_pool_performance_tier")

            captions_by_type[content_type] = {
                "captions": type_captions,
                "pool_stats": {
                    "total_available": total_available,
                    "fresh_for_creator": fresh_for_creator,
                    "returned_count": len(type_captions),
                    "has_more": len(type_captions) < total_available,
                    "avg_pool_performance_tier": round(avg_tier, 2) if avg_tier else None
                }
            }

        # =====================================================================
        # LAYER 7: Build metadata
        # =====================================================================

        def _compute_captions_hash(caption_ids):
            if not caption_ids:
                return "sha256:empty"
            sorted_ids = sorted(caption_ids)
            id_string = ",".join(str(cid) for cid in sorted_ids)
            return f"sha256:{hashlib.sha256(id_string.encode()).hexdigest()[:16]}"

        def _compute_content_types_hash(types):
            if not types:
                return "sha256:empty"
            sorted_types = sorted(types)
            type_string = ",".join(sorted_types)
            return f"sha256:{hashlib.sha256(type_string.encode()).hexdigest()[:16]}"

        query_ms = (time.perf_counter() - start_time) * 1000

        types_with_captions = [t for t, data in captions_by_type.items() if data["captions"]]
        types_without_captions = [t for t, data in captions_by_type.items() if not data["captions"]]

        has_per_creator = any(
            c.get("creator_last_used_at") is not None
            for data in captions_by_type.values()
            for c in data["captions"]
        )
        has_global_only = any(
            c.get("creator_last_used_at") is None and c.get("last_used_at") is not None
            for data in captions_by_type.values()
            for c in data["captions"]
        )

        if has_per_creator and has_global_only:
            freshness_source = "mixed"
        elif has_per_creator:
            freshness_source = "per_creator"
        else:
            freshness_source = "global_only"

        total_captions = sum(len(data["captions"]) for data in captions_by_type.values())

        metadata = {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "query_ms": round(query_ms, 2),
            "creator_resolved": resolved_creator_id,
            "captions_hash": _compute_captions_hash(all_caption_ids),
            "content_types_hash": _compute_content_types_hash(unique_content_types),
            "caption_ids_returned": all_caption_ids,
            "types_with_captions": len(types_with_captions),
            "types_without_captions": len(types_without_captions),
            "empty_types": types_without_captions,
            "per_creator_data_available": has_per_creator,
            "freshness_source": freshness_source,
            "filters_applied": {
                "content_types": unique_content_types,
                "schedulable_type": schedulable_type,
                "limit_per_type": limit_per_type
            }
        }

        # =====================================================================
        # LAYER 8: Return response
        # =====================================================================
        return {
            "creator_id": creator_id,
            "captions_by_type": captions_by_type,
            "total_captions": total_captions,
            "types_requested": len(unique_content_types),
            "metadata": metadata
        }

    except Exception as e:
        logger.error(f"get_batch_captions_by_content_types error: {e}")
        return _build_caption_error_response("DATABASE_ERROR", str(e), content_types)


@mcp.tool()
def get_send_type_captions(creator_id: str, send_type: str, limit: int = 10) -> dict:
    """Retrieves captions for a specific send type with per-creator freshness filtering.

    MCP Name: mcp__eros-db__get_send_type_captions
    Version: 2.0.0

    Args:
        creator_id: Creator identifier (required for per-creator freshness)
        send_type: Send type key from send_types table (e.g., 'ppv_unlock', 'bump_normal')
        limit: Maximum captions to return (clamped 1-50, default 10)

    Returns:
        Dict with captions (including freshness fields), pool_stats, and metadata.

    Response Schema:
        {
            "creator_id": str,           # Original input
            "resolved_creator_id": str,  # Resolved PK from creators table
            "send_type": str,
            "captions": [                # Ordered by freshness -> performance
                {
                    "caption_id": int,
                    "caption_text": str,
                    "category": str,     # Same as send_type (caption_type column)
                    "performance_tier": int,
                    "content_type_id": int,
                    "global_last_used_at": str|null,
                    "creator_last_used_at": str|null,
                    "creator_use_count": int,
                    "days_since_creator_used": int|null,
                    "effectively_fresh": int  # 1=fresh, 0=stale
                }
            ],
            "count": int,
            "pool_stats": {
                "total_available": int,
                "fresh_for_creator": int,
                "returned_count": int,
                "has_more": bool,
                "avg_pool_performance_tier": float|null,
                "freshness_ratio": float|null
            },
            "metadata": {
                "fetched_at": str,       # ISO timestamp
                "query_ms": float,
                "tool_version": str,
                "freshness_threshold_days": int
            }
        }

    Example:
        get_send_type_captions(
            creator_id="alexia",
            send_type="bump_normal",
            limit=5
        )
    """
    logger.info(f"get_send_type_captions: creator_id={creator_id}, send_type={send_type}")

    # =========================================================================
    # LAYER 1: Type validation
    # =========================================================================
    if not creator_id or not isinstance(creator_id, str):
        return _build_send_type_error_response(
            "INVALID_CREATOR_ID",
            "creator_id must be a non-empty string",
            send_type if isinstance(send_type, str) else ""
        )

    if not send_type or not isinstance(send_type, str):
        return _build_send_type_error_response(
            "INVALID_SEND_TYPE",
            "send_type must be a non-empty string",
            send_type if isinstance(send_type, str) else ""
        )

    # =========================================================================
    # LAYER 2: Format validation
    # =========================================================================
    is_valid, validation_result = validate_creator_id(creator_id)
    if not is_valid:
        return _build_send_type_error_response(
            "INVALID_CREATOR_ID_FORMAT",
            validation_result,
            send_type
        )

    if len(send_type) > 50 or not send_type.replace('_', '').isalnum():
        return _build_send_type_error_response(
            "INVALID_SEND_TYPE_FORMAT",
            "send_type must be alphanumeric with underscores, max 50 chars",
            send_type
        )

    # =========================================================================
    # LAYER 3: Resolution
    # =========================================================================
    resolved = resolve_creator_id(creator_id)
    if not resolved["found"]:
        return _build_send_type_error_response(
            "CREATOR_NOT_FOUND",
            f"Creator not found: {creator_id}",
            send_type
        )
    resolved_creator_id = resolved["creator_id"]

    # Validate send_type exists in send_types table
    send_type_check = db_query(
        "SELECT 1 FROM send_types WHERE send_type_key = ? AND is_active = 1 LIMIT 1",
        (send_type,)
    )
    if not send_type_check:
        valid_types = db_query(
            "SELECT send_type_key FROM send_types WHERE is_active = 1 ORDER BY sort_order LIMIT 30"
        )
        valid_list = [r["send_type_key"] for r in valid_types]
        return _build_send_type_error_response(
            "SEND_TYPE_NOT_FOUND",
            f"send_type '{send_type}' not found. Valid types: {', '.join(valid_list[:10])}...",
            send_type
        )

    # =========================================================================
    # LAYER 4: Normalize
    # =========================================================================
    limit = max(1, min(50, limit))

    try:
        start_time = time.perf_counter()

        # Calculate freshness threshold (90 days = effectively fresh)
        from datetime import date, timedelta
        freshness_threshold = (date.today() - timedelta(days=90)).isoformat()

        # Get pool statistics first
        pool_stats_result = db_query("""
            SELECT
                COUNT(*) as total_available,
                SUM(CASE
                    WHEN ccp.last_used_date IS NULL THEN 1
                    WHEN ccp.last_used_date < ? THEN 1
                    ELSE 0
                END) as fresh_for_creator,
                AVG(cb.performance_tier) as avg_pool_performance_tier
            FROM caption_bank cb
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.caption_type = ?
            AND cb.is_active = 1
        """, (freshness_threshold, resolved_creator_id, send_type))

        pool = pool_stats_result[0] if pool_stats_result else {
            "total_available": 0, "fresh_for_creator": 0, "avg_pool_performance_tier": None
        }

        # Get captions with freshness fields - exact send_type match only
        # Note: Category fallback removed in v2.0.0 - data shows caption_type
        # stores send_type_keys directly, not generic categories
        captions = db_query("""
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.caption_type as category,
                cb.performance_tier,
                cb.content_type_id,
                cb.global_last_used_date as global_last_used_at,
                ccp.last_used_date as creator_last_used_at,
                COALESCE(ccp.times_used, 0) as creator_use_count,
                CASE
                    WHEN ccp.last_used_date IS NULL THEN NULL
                    ELSE CAST(julianday('now') - julianday(ccp.last_used_date) AS INTEGER)
                END as days_since_creator_used,
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 1
                    WHEN ccp.last_used_date < ? THEN 1
                    ELSE 0
                END as effectively_fresh
            FROM caption_bank cb
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.caption_type = ?
            AND cb.is_active = 1
            ORDER BY
                effectively_fresh DESC,
                ccp.last_used_date ASC NULLS FIRST,
                cb.performance_tier ASC,
                cb.global_last_used_date ASC NULLS FIRST
            LIMIT ?
        """, (freshness_threshold, resolved_creator_id, send_type, limit))

        # Log warning if no captions found for monitoring
        if not captions:
            logger.warning(f"No captions found for send_type={send_type}, creator={resolved_creator_id}")

        query_ms = (time.perf_counter() - start_time) * 1000
        total_available = pool.get("total_available", 0) or 0
        fresh_for_creator = pool.get("fresh_for_creator", 0) or 0

        return {
            "creator_id": creator_id,
            "resolved_creator_id": resolved_creator_id,
            "send_type": send_type,
            "captions": captions,
            "count": len(captions),
            "pool_stats": {
                "total_available": total_available,
                "fresh_for_creator": fresh_for_creator,
                "returned_count": len(captions),
                "has_more": total_available > len(captions),
                "avg_pool_performance_tier": pool.get("avg_pool_performance_tier"),
                "freshness_ratio": round(fresh_for_creator / total_available, 3) if total_available > 0 else None
            },
            "metadata": {
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "query_ms": round(query_ms, 2),
                "tool_version": "2.0.0",
                "freshness_threshold_days": 90
            }
        }

    except Exception as e:
        logger.error(f"get_send_type_captions error: {e}")
        return _build_send_type_error_response("DATABASE_ERROR", str(e), send_type)


# =============================================================================
# CAPTION VALIDATION v2.0.0 - send_type cache and helper functions
# =============================================================================

# Module-level cache for send_types (loaded once per session)
_SEND_TYPES_CACHE: dict[str, dict] = {}


def _get_send_types_cache() -> dict[str, dict]:
    """Load and cache all send_types. Called once per session."""
    global _SEND_TYPES_CACHE
    if not _SEND_TYPES_CACHE:
        query = """
            SELECT send_type_key, category, page_type_restriction
            FROM send_types WHERE is_active = 1
        """
        rows = db_query(query, ())
        _SEND_TYPES_CACHE = {r["send_type_key"]: r for r in rows}
        logger.info(f"Loaded {len(_SEND_TYPES_CACHE)} send_types into cache")
    return _SEND_TYPES_CACHE


def _validate_send_type(send_type: str) -> tuple[bool, dict | None, str | None]:
    """Validate send_type and return (valid, send_type_row, error_code)."""
    cache = _get_send_types_cache()
    if send_type in cache:
        return (True, cache[send_type], None)
    return (False, None, "INVALID_SEND_TYPE")


def _get_thresholds(category: str | None) -> dict:
    """Get length thresholds for category."""
    return CAPTION_LENGTH_THRESHOLDS.get(
        category.lower() if category else "default",
        CAPTION_LENGTH_THRESHOLDS["default"]
    )


def _score_length(length: int, thresholds: dict) -> tuple[int, list[str]]:
    """Score caption length against thresholds. Returns (penalty, issues)."""
    issues = []
    penalty = 0

    if length < thresholds["min"]:
        penalty = 30
        issues.append(f"Caption too short (min {thresholds['min']} chars for this category)")
    elif length < thresholds["ideal_min"]:
        penalty = 10
        issues.append(f"Caption below ideal length (recommend {thresholds['ideal_min']}+ chars)")
    elif length > thresholds["max"]:
        penalty = 15
        issues.append(f"Caption too long (max {thresholds['max']} chars)")
    elif length > thresholds["ideal_max"]:
        penalty = 5
        issues.append(f"Caption above ideal length (recommend under {thresholds['ideal_max']} chars)")

    return (penalty, issues)


def _get_spam_patterns(category: str | None) -> list[tuple[str, int]]:
    """Get spam patterns applicable to category."""
    patterns = list(CAPTION_SPAM_PATTERNS["universal"])
    cat_lower = category.lower() if category else ""
    if cat_lower not in SALES_LANGUAGE_TOLERANT:
        patterns.extend(CAPTION_SPAM_PATTERNS["non_revenue"])
    return patterns


def _build_validation_error_response(
    error_code: str,
    error_msg: str,
    send_type: str,
    **kwargs
) -> dict:
    """Build standardized error response for validate_caption_structure."""
    return {
        "error": error_msg,
        "error_code": error_code,
        "valid": False,
        "score": None,
        "send_type": send_type,
        "category": None,
        "caption_length": None,
        "issues": [],
        "recommendation": "REJECT",
        "thresholds_applied": None,
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "tool_version": "2.0.0",
            "error": True
        },
        **kwargs
    }


def _build_validation_success_response(
    score: int,
    issues: list[str],
    send_type: str,
    category: str,
    caption_length: int,
    thresholds: dict,
    cache_hit: bool,
    start_time: float
) -> dict:
    """Build standardized success response for validate_caption_structure."""
    return {
        "valid": score >= CAPTION_SCORE_THRESHOLDS["review"],
        "score": score,
        "issues": issues,
        "send_type": send_type,
        "category": category,
        "caption_length": caption_length,
        "thresholds_applied": thresholds,
        "recommendation": (
            "PASS" if score >= CAPTION_SCORE_THRESHOLDS["pass"]
            else "REVIEW" if score >= CAPTION_SCORE_THRESHOLDS["review"]
            else "REJECT"
        ),
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "tool_version": "2.0.0",
            "query_ms": round((time.time() - start_time) * 1000, 2),
            "cache_hit": cache_hit
        }
    }


@mcp.tool()
def validate_caption_structure(caption_text: str, send_type: str) -> dict:
    """Validates caption structure against anti-patterization rules.

    MCP Name: mcp__eros-db__validate_caption_structure
    Version: 2.0.0

    This tool validates caption text for quality and returns a score with
    actionable issues. Validation rules vary by send_type category:
    - Revenue: Longer captions expected, sales language tolerated
    - Engagement: Moderate length, organic feel preferred
    - Retention: Personal tone, stricter spam detection

    Args:
        caption_text: The caption text to validate (required, max 2000 chars)
        send_type: The intended send type from send_types table (required)

    Returns:
        Success response:
        {
            "valid": bool,              # True if score >= 70
            "score": int,               # Quality score 0-100
            "issues": [str],            # List of specific issues found
            "send_type": str,           # Echoed input
            "category": str,            # Resolved category (revenue/engagement/retention)
            "caption_length": int,      # Character count
            "thresholds_applied": {     # Category-specific thresholds used
                "min": int, "ideal_min": int, "ideal_max": int, "max": int
            },
            "recommendation": str,      # PASS (>=85) / REVIEW (70-84) / REJECT (<70)
            "metadata": {...}
        }

        Error response (for invalid inputs):
        {
            "error": str,
            "error_code": str,          # EMPTY_CAPTION, INVALID_SEND_TYPE, CAPTION_EXCEEDS_LIMIT
            "valid": false,
            "score": null,
            ...
        }
    """
    start_time = time.time()
    cache_hit = bool(_SEND_TYPES_CACHE)  # True if cache already loaded

    logger.info(f"validate_caption_structure: send_type={send_type}, "
                f"length={len(caption_text) if caption_text else 0}")

    # ==========================================================================
    # Input Validation (Error responses for structural failures)
    # ==========================================================================

    # Check for empty caption
    if caption_text is None or not caption_text.strip():
        logger.warning("validate_caption_structure: empty caption")
        return _build_validation_error_response(
            "EMPTY_CAPTION",
            "Caption text is required",
            send_type
        )

    # Check for excessive length (guard against abuse)
    if len(caption_text) > CAPTION_MAX_INPUT_LENGTH:
        logger.warning(f"validate_caption_structure: caption exceeds {CAPTION_MAX_INPUT_LENGTH} chars")
        return _build_validation_error_response(
            "CAPTION_EXCEEDS_LIMIT",
            f"Caption exceeds {CAPTION_MAX_INPUT_LENGTH} character limit",
            send_type
        )

    # Validate send_type against database
    is_valid, send_type_row, error_code = _validate_send_type(send_type)
    if not is_valid:
        valid_types = sorted(_get_send_types_cache().keys())
        logger.warning(f"validate_caption_structure: invalid send_type '{send_type}'")
        return _build_validation_error_response(
            "INVALID_SEND_TYPE",
            f"Invalid send_type: {send_type}",
            send_type,
            valid_send_types=valid_types
        )

    # ==========================================================================
    # Validation Logic (Score responses for quality issues)
    # ==========================================================================

    category = send_type_row["category"]
    thresholds = _get_thresholds(category)
    caption_length = len(caption_text)

    issues = []
    score = 100

    # Length validation (category-aware)
    length_penalty, length_issues = _score_length(caption_length, thresholds)
    score -= length_penalty
    issues.extend(length_issues)

    # Spam pattern detection (category-aware)
    spam_patterns = _get_spam_patterns(category)
    caption_lower = caption_text.lower()
    for pattern, penalty in spam_patterns:
        if pattern in caption_lower:
            issues.append(f"Contains spam pattern: '{pattern}'")
            score -= penalty

    # Emoji density check
    emoji_count = sum(1 for c in caption_text if ord(c) > 0x1F300)
    if emoji_count > 10:
        issues.append(f"Excessive emojis ({emoji_count})")
        score -= 15
    elif emoji_count > 5:
        issues.append(f"High emoji count ({emoji_count})")
        score -= 5

    # Repetition check
    words = caption_text.lower().split()
    if len(words) > 5:
        word_counts = {}
        for w in words:
            if len(w) > 3:
                word_counts[w] = word_counts.get(w, 0) + 1
        repeated = [w for w, c in word_counts.items() if c > 2]
        if repeated:
            issues.append(f"Repeated words: {', '.join(repeated[:3])}")
            score -= 10

    # All caps check
    if caption_text.isupper() and len(caption_text) > 20:
        issues.append("All caps text")
        score -= 20

    # Clamp score to valid range
    score = max(0, min(100, score))

    return _build_validation_success_response(
        score=score,
        issues=issues,
        send_type=send_type,
        category=category,
        caption_length=caption_length,
        thresholds=thresholds,
        cache_hit=cache_hit,
        start_time=start_time
    )


# ============================================================
# CONFIG TOOLS (2)
# ============================================================

@mcp.tool()
def get_send_types_constraints(page_type: str = None) -> dict:
    """Returns minimal send type constraints for schedule generation.

    MCP Name: mcp__eros-db__get_send_types_constraints

    This is the PREFERRED tool for schedule generation. Returns only 9 essential
    fields instead of 53, reducing response from ~34k chars to ~6k chars (~80% reduction).

    Use full get_send_types() only when you need description, strategy, weights,
    channel configs, or other detailed fields.

    Args:
        page_type: Optional filter ('paid' or 'free')

    Returns:
        Minimal send type data with scheduling constraints only:
        - send_type_key, category, page_type_restriction
        - max_per_day, max_per_week, min_hours_between
        - requires_media, requires_price, requires_flyer
    """
    logger.info(f"get_send_types_constraints: page_type={page_type}")
    try:
        # Select ONLY the 9 essential fields for schedule generation
        query = """
            SELECT
                send_type_key,
                category,
                page_type_restriction,
                max_per_day,
                max_per_week,
                min_hours_between,
                requires_media,
                requires_price,
                requires_flyer
            FROM send_types
            WHERE is_active = 1
        """

        if page_type == 'free':
            query += " AND page_type_restriction IN ('both', 'free')"
        elif page_type == 'paid':
            query += " AND page_type_restriction IN ('both', 'paid')"

        query += " ORDER BY category, sort_order"

        types = db_query(query, tuple())

        # Group by category for easy lookup
        by_category = {
            "revenue": [],
            "engagement": [],
            "retention": []
        }
        for t in types:
            cat = t.get('category', 'engagement').lower()
            if cat in by_category:
                by_category[cat].append(t)

        return {
            "send_types": types,
            "by_category": by_category,
            "total": len(types),
            "page_type_filter": page_type,
            "fields_returned": 9,
            "_optimization_note": "Lightweight view (9 fields vs 53). Use get_send_types for full details."
        }

    except Exception as e:
        logger.error(f"get_send_types_constraints error: {e}")
        return {"error": str(e), "send_types": []}


@mcp.tool()
def get_send_types(page_type: str = None) -> dict:
    """Returns the send type taxonomy with constraints.

    MCP Name: mcp__eros-db__get_send_types

    Args:
        page_type: Optional filter ('paid' or 'free')

    Returns:
        List of send types with constraints
    """
    logger.info(f"get_send_types: page_type={page_type}")
    try:
        query = "SELECT * FROM send_types WHERE is_active = 1"
        params = []

        if page_type == 'free':
            query += " AND page_type_restriction IN ('both', 'free')"
        elif page_type == 'paid':
            query += " AND page_type_restriction IN ('both', 'paid')"

        query += " ORDER BY category, sort_order"

        types = db_query(query, tuple(params))

        # Group by category
        by_category = {
            "revenue": [],
            "engagement": [],
            "retention": []
        }
        for t in types:
            cat = t.get('category', 'engagement').lower()
            if cat in by_category:
                by_category[cat].append(t)

        return {
            "send_types": types,
            "by_category": by_category,
            "total": len(types),
            "page_type_filter": page_type
        }

    except Exception as e:
        logger.error(f"get_send_types error: {e}")
        return {"error": str(e), "send_types": []}


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting EROS MCP Server")
    logger.info(f"  Server Name: eros-db")
    logger.info(f"  Database: {DB_PATH}")
    logger.info(f"  DB Exists: {os.path.exists(DB_PATH)}")
    logger.info("=" * 60)

    if not os.path.exists(DB_PATH):
        logger.error(f"DATABASE NOT FOUND: {DB_PATH}")
        sys.exit(1)

    mcp.run()
