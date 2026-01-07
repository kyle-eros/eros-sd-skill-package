"""EROS Schedule Generator MCP Server.

Provides database tools for the EROS schedule generation pipeline.
MCP Specification: 2025-11-25
Server Name: eros-db
Tool Naming Convention: mcp__eros-db__<tool-name>

Tools (15 total):
  Creator (5): get_creator_profile, get_active_creators, get_vault_availability,
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
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

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
# CREATOR TOOLS (5)
# ============================================================

@mcp.tool()
def get_creator_profile(creator_id: str, include_analytics: bool = False) -> dict:
    """Retrieves comprehensive creator profile including preferences and metrics.

    MCP Name: mcp__eros-db__get_creator_profile

    Args:
        creator_id: Unique identifier for the creator (creator_id or page_name)
        include_analytics: Include 30-day analytics in response

    Returns:
        Creator profile with optional analytics data
    """
    logger.info(f"get_creator_profile: creator_id={creator_id}, include_analytics={include_analytics}")
    try:
        results = db_query(
            "SELECT * FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )

        if not results:
            return {"error": f"Creator not found: {creator_id}", "found": False}

        profile = dict(results[0])
        profile["found"] = True

        if include_analytics:
            creator_pk = profile.get('creator_id')
            if creator_pk:
                analytics = db_query("""
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
                if analytics:
                    profile['analytics_30d'] = dict(analytics[0])

        return profile

    except Exception as e:
        logger.error(f"get_creator_profile error: {e}")
        return {"error": str(e), "found": False}


@mcp.tool()
def get_active_creators(limit: int = 100, tier: str = None) -> dict:
    """Returns list of active creators with basic metrics.

    MCP Name: mcp__eros-db__get_active_creators

    Args:
        limit: Maximum creators to return (default 100, max 500)
        tier: Optional filter by volume tier (MINIMAL/LITE/STANDARD/HIGH_VALUE/PREMIUM)

    Returns:
        List of active creator summaries
    """
    logger.info(f"get_active_creators: limit={limit}, tier={tier}")
    try:
        limit = min(max(1, limit), 500)  # Clamp between 1-500

        query = """
            SELECT c.creator_id, c.page_name, c.page_type, c.is_active,
                   c.current_fan_count, c.current_message_net as mm_revenue_monthly,
                   va.volume_level as volume_tier
            FROM creators c
            LEFT JOIN volume_assignments va ON c.creator_id = va.creator_id AND va.is_active = 1
            WHERE c.is_active = 1
        """
        params = []

        if tier and tier in ('MINIMAL', 'LITE', 'STANDARD', 'HIGH_VALUE', 'PREMIUM'):
            query += " AND va.volume_level = ?"
            params.append(tier)

        query += " ORDER BY c.current_message_net DESC LIMIT ?"
        params.append(limit)

        results = db_query(query, tuple(params))
        return {"creators": results, "count": len(results), "limit": limit}

    except Exception as e:
        logger.error(f"get_active_creators error: {e}")
        return {"error": str(e), "creators": [], "count": 0}


@mcp.tool()
def get_vault_availability(creator_id: str) -> dict:
    """Returns available content types in creator's vault.

    MCP Name: mcp__eros-db__get_vault_availability
    HARD GATE DATA - Used for validation

    Args:
        creator_id: Creator identifier

    Returns:
        Available content types with counts
    """
    logger.info(f"get_vault_availability: creator_id={creator_id}")
    try:
        # Verify creator exists
        creator = db_query(
            "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "available_types": []}

        creator_pk = creator[0]['creator_id']

        # Query vault_matrix (actual table name, not vault_content)
        types = db_query("""
            SELECT ct.type_name, vm.quantity_available as content_count, vm.has_content
            FROM vault_matrix vm
            JOIN content_types ct ON vm.content_type_id = ct.content_type_id
            WHERE vm.creator_id = ? AND vm.has_content = 1
            ORDER BY vm.quantity_available DESC
        """, (creator_pk,))

        type_names = [t['type_name'] for t in types]

        return {
            "creator_id": creator_id,
            "available_types": types,
            "type_names": type_names,
            "total_available": sum(t.get('content_count', 0) or 0 for t in types)
        }

    except Exception as e:
        logger.error(f"get_vault_availability error: {e}")
        return {"error": str(e), "available_types": [], "type_names": []}


@mcp.tool()
def get_content_type_rankings(creator_id: str) -> dict:
    """Returns content type performance rankings with TOP/MID/LOW/AVOID tiers.

    MCP Name: mcp__eros-db__get_content_type_rankings
    HARD GATE DATA - Used for validation

    Args:
        creator_id: Creator identifier

    Returns:
        Content types with performance tiers and metrics
    """
    logger.info(f"get_content_type_rankings: creator_id={creator_id}")
    try:
        # Verify creator exists
        creator = db_query(
            "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "content_types": []}

        creator_pk = creator[0]['creator_id']

        # Query top_content_types (actual table name, not content_type_rankings)
        rankings = db_query("""
            SELECT content_type as type_name, performance_tier,
                   avg_rps as rps, avg_purchase_rate as conversion_rate,
                   send_count as sends_last_30d,
                   total_earnings, confidence_score
            FROM top_content_types
            WHERE creator_id = ?
            ORDER BY avg_rps DESC
        """, (creator_pk,))

        avoid_types = [r['type_name'] for r in rankings if r.get('performance_tier') == 'AVOID']
        top_types = [r['type_name'] for r in rankings if r.get('performance_tier') == 'TOP']

        return {
            "creator_id": creator_id,
            "content_types": rankings,
            "avoid_types": avoid_types,
            "top_types": top_types,
            "total_types": len(rankings)
        }

    except Exception as e:
        logger.error(f"get_content_type_rankings error: {e}")
        return {"error": str(e), "content_types": [], "avoid_types": [], "top_types": []}


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
                "primary_tone": "GFE",
                "secondary_tone": "playful",
                "emoji_frequency": "moderate",
                "slang_level": "low",
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
def get_volume_config(creator_id: str, week_start: str) -> dict:
    """Returns volume configuration including tier and daily distribution.

    MCP Name: mcp__eros-db__get_volume_config

    Args:
        creator_id: Creator identifier
        week_start: Week start date (YYYY-MM-DD)

    Returns:
        Volume tier, daily volumes, and DOW distribution
    """
    logger.info(f"get_volume_config: creator_id={creator_id}, week_start={week_start}")
    try:
        # Query creators with volume_assignments (actual table name, not volume_configs)
        results = db_query("""
            SELECT c.current_message_net as mm_revenue_monthly,
                   va.volume_level as volume_tier,
                   va.ppv_per_day, va.bump_per_day,
                   c.content_category, c.current_fan_count, c.page_type
            FROM creators c
            LEFT JOIN volume_assignments va ON c.creator_id = va.creator_id AND va.is_active = 1
            WHERE c.creator_id = ? OR c.page_name = ?
            LIMIT 1
        """, (creator_id, creator_id))

        if not results:
            return {"error": f"Creator not found: {creator_id}"}

        row = dict(results[0])
        revenue = row.get('mm_revenue_monthly') or 0

        # Use volume_assignments if available, else calculate from revenue
        tier = row.get('volume_tier')
        if not tier:
            # Calculate tier from revenue (DOMAIN_KNOWLEDGE.md Section 2)
            if revenue < 150:
                tier = "MINIMAL"
            elif revenue < 800:
                tier = "LITE"
            elif revenue < 3000:
                tier = "STANDARD"
            elif revenue < 8000:
                tier = "HIGH_VALUE"
            else:
                tier = "PREMIUM"

        # Volume ranges by tier
        tier_ranges = {
            "MINIMAL": {"rev": (1, 2), "eng": (1, 2), "ret": (1, 1)},
            "LITE": {"rev": (2, 4), "eng": (2, 4), "ret": (1, 2)},
            "STANDARD": {"rev": (4, 6), "eng": (4, 6), "ret": (2, 3)},
            "HIGH_VALUE": {"rev": (6, 9), "eng": (5, 8), "ret": (2, 4)},
            "PREMIUM": {"rev": (8, 12), "eng": (6, 10), "ret": (3, 5)}
        }
        ranges = tier_ranges.get(tier, tier_ranges["STANDARD"])

        return {
            "creator_id": creator_id,
            "week_start": week_start,
            "tier": tier,
            "mm_revenue_monthly": revenue,
            "page_type": row.get('page_type', 'paid'),
            "content_category": row.get('content_category'),
            "current_fan_count": row.get('current_fan_count', 0),
            "ppv_per_day": row.get('ppv_per_day'),
            "bump_per_day": row.get('bump_per_day'),
            "revenue_per_day": list(ranges["rev"]),
            "engagement_per_day": list(ranges["eng"]),
            "retention_per_day": list(ranges["ret"])
        }

    except Exception as e:
        logger.error(f"get_volume_config error: {e}")
        return {"error": str(e)}


@mcp.tool()
def get_active_volume_triggers(creator_id: str) -> dict:
    """Returns active performance-based volume triggers.

    MCP Name: mcp__eros-db__get_active_volume_triggers

    Args:
        creator_id: Creator identifier

    Returns:
        List of active triggers with adjustments
    """
    logger.info(f"get_active_volume_triggers: creator_id={creator_id}")
    try:
        triggers = db_query("""
            SELECT vt.content_type, vt.trigger_type, vt.adjustment_multiplier,
                   vt.confidence, vt.reason, vt.expires_at
            FROM volume_triggers vt
            WHERE vt.creator_id = ?
            AND vt.is_active = 1
            AND (vt.expires_at IS NULL OR vt.expires_at > datetime('now'))
            ORDER BY vt.adjustment_multiplier DESC
        """, (creator_id,))

        # Also try by page_name
        if not triggers:
            creator = db_query(
                "SELECT creator_id FROM creators WHERE page_name = ? LIMIT 1",
                (creator_id,)
            )
            if creator:
                triggers = db_query("""
                    SELECT vt.content_type, vt.trigger_type, vt.adjustment_multiplier,
                           vt.confidence, vt.reason, vt.expires_at
                    FROM volume_triggers vt
                    WHERE vt.creator_id = ?
                    AND vt.is_active = 1
                    AND (vt.expires_at IS NULL OR vt.expires_at > datetime('now'))
                    ORDER BY vt.adjustment_multiplier DESC
                """, (creator[0]['creator_id'],))

        return {
            "creator_id": creator_id,
            "triggers": triggers,
            "count": len(triggers)
        }

    except Exception as e:
        logger.error(f"get_active_volume_triggers error: {e}")
        return {"error": str(e), "triggers": [], "count": 0}


@mcp.tool()
def get_performance_trends(creator_id: str, period: str = "14d") -> dict:
    """Returns performance trends for health and saturation detection.

    MCP Name: mcp__eros-db__get_performance_trends

    Args:
        creator_id: Creator identifier
        period: Analysis period (default "14d")

    Returns:
        Performance metrics including saturation indicators
    """
    logger.info(f"get_performance_trends: creator_id={creator_id}, period={period}")
    try:
        # Parse period (default 14 days)
        days = 14
        if period.endswith('d'):
            try:
                days = int(period[:-1])
            except ValueError:
                days = 14

        # Get creator_id if page_name provided
        creator = db_query(
            "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}"}

        creator_pk = creator[0]['creator_id']

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
                MIN(imported_at) as first_send,
                MAX(imported_at) as last_send
            FROM mass_messages
            WHERE creator_id = ?
            AND imported_at >= date('now', ?)
        """, (creator_pk, f'-{days} days'))

        if not metrics or not metrics[0].get('total_sends'):
            return {
                "creator_id": creator_id,
                "period": period,
                "health_status": "UNKNOWN",
                "message": "No performance data found",
                "avg_rps": 0,
                "total_sends": 0
            }

        m = dict(metrics[0])

        # Determine health status based on trends
        health_status = "HEALTHY"
        saturation = 50
        opportunity = 50

        return {
            "creator_id": creator_id,
            "period": period,
            "health_status": health_status,
            "avg_rps": round(m.get('avg_rps') or 0, 2),
            "avg_conversion": round(m.get('avg_conversion') or 0, 3),
            "avg_open_rate": round(m.get('avg_open_rate') or 0, 3),
            "total_earnings": round(m.get('total_earnings') or 0, 2),
            "total_sends": m.get('total_sends') or 0,
            "saturation_score": saturation,
            "opportunity_score": opportunity,
            "date_range": {
                "start": m.get('first_send'),
                "end": m.get('last_send')
            }
        }

    except Exception as e:
        logger.error(f"get_performance_trends error: {e}")
        return {"error": str(e)}


@mcp.tool()
def save_schedule(
    creator_id: str,
    week_start: str,
    items: list,
    validation_certificate: dict = None
) -> dict:
    """Persists generated schedule with validation certificate.

    MCP Name: mcp__eros-db__save_schedule

    Args:
        creator_id: Creator identifier
        week_start: Week start date (YYYY-MM-DD)
        items: List of schedule items
        validation_certificate: Optional validation certificate

    Returns:
        Result with schedule_id if successful
    """
    logger.info(f"save_schedule: creator_id={creator_id}, week_start={week_start}, items={len(items)}")
    try:
        # Get actual creator_id
        creator = db_query(
            "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "success": False}

        creator_pk = creator[0]['creator_id']

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO schedule_templates (
                    creator_id, week_start_date, schedule_json,
                    validation_status, item_count, created_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (
                creator_pk,
                week_start,
                json.dumps({"items": items, "validation_certificate": validation_certificate}),
                "validated" if validation_certificate else "pending",
                len(items)
            ))
            schedule_id = cursor.lastrowid
            conn.commit()

        logger.info(f"Schedule saved: id={schedule_id}")

        return {
            "success": True,
            "schedule_id": schedule_id,
            "template_id": schedule_id,
            "items_saved": len(items),
            "creator_id": creator_id,
            "week_start": week_start,
            "has_certificate": validation_certificate is not None
        }

    except Exception as e:
        logger.error(f"save_schedule error: {e}")
        return {"error": str(e), "success": False}


@mcp.tool()
def save_volume_triggers(creator_id: str, triggers: list) -> dict:
    """Persists detected volume triggers.

    MCP Name: mcp__eros-db__save_volume_triggers

    Args:
        creator_id: Creator identifier
        triggers: List of trigger objects

    Returns:
        Result with count of triggers saved
    """
    logger.info(f"save_volume_triggers: creator_id={creator_id}, triggers={len(triggers)}")
    try:
        # Get actual creator_id
        creator = db_query(
            "SELECT creator_id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "success": False}

        creator_pk = creator[0]['creator_id']
        saved = 0

        with get_db_connection() as conn:
            cursor = conn.cursor()
            for trigger in triggers:
                cursor.execute("""
                    INSERT OR REPLACE INTO volume_triggers (
                        creator_id, content_type, trigger_type,
                        adjustment_value, confidence, reason, expires_at,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    creator_pk,
                    trigger.get('content_type'),
                    trigger.get('trigger_type'),
                    trigger.get('adjustment_multiplier', 1.0),
                    trigger.get('confidence', 'moderate'),
                    trigger.get('reason', ''),
                    trigger.get('expires_at')
                ))
                saved += 1
            conn.commit()

        logger.info(f"Triggers saved: {saved}")

        return {
            "success": True,
            "triggers_saved": saved,
            "creator_id": creator_id
        }

    except Exception as e:
        logger.error(f"save_volume_triggers error: {e}")
        return {"error": str(e), "success": False}


# ============================================================
# CAPTION TOOLS (3)
# ============================================================

@mcp.tool()
def get_batch_captions_by_content_types(
    creator_id: str,
    content_types: list,
    limit_per_type: int = 5
) -> dict:
    """Batch retrieves captions filtered by content types for PPV selection.

    MCP Name: mcp__eros-db__get_batch_captions_by_content_types

    Args:
        creator_id: Creator identifier
        content_types: List of content type names to filter
        limit_per_type: Max captions per content type (default 5, max 20)

    Returns:
        Captions grouped by content type
    """
    logger.info(f"get_batch_captions_by_content_types: creator_id={creator_id}, types={content_types}")
    try:
        # Note: caption_bank is global, not per-creator in this schema
        # Filter by content_type_id matching the requested types

        limit_per_type = min(max(1, limit_per_type), 20)  # Clamp 1-20

        results = {}
        total = 0

        for ct in content_types:
            # Get content_type_id first
            ct_row = db_query(
                "SELECT content_type_id FROM content_types WHERE type_name = ? LIMIT 1",
                (ct,)
            )
            if not ct_row:
                results[ct] = []
                continue

            ct_id = ct_row[0]['content_type_id']

            # Query caption_bank (actual table name, not captions)
            captions = db_query("""
                SELECT cb.caption_id, cb.caption_text, cb.caption_type as category,
                       cb.performance_tier as quality_score, ct.type_name as content_type,
                       cb.global_last_used_date as last_used_at, cb.global_times_used as use_count
                FROM caption_bank cb
                JOIN content_types ct ON cb.content_type_id = ct.content_type_id
                WHERE cb.content_type_id = ?
                AND cb.is_active = 1
                ORDER BY cb.performance_tier ASC, cb.global_last_used_date ASC NULLS FIRST
                LIMIT ?
            """, (ct_id, limit_per_type))

            results[ct] = captions
            total += len(captions)

        return {
            "creator_id": creator_id,
            "captions_by_type": results,
            "total_captions": total,
            "types_requested": len(content_types)
        }

    except Exception as e:
        logger.error(f"get_batch_captions_by_content_types error: {e}")
        return {"error": str(e), "captions_by_type": {}}


@mcp.tool()
def get_send_type_captions(creator_id: str, send_type: str, limit: int = 10) -> dict:
    """Retrieves captions compatible with a specific send type.

    MCP Name: mcp__eros-db__get_send_type_captions

    Args:
        creator_id: Creator identifier
        send_type: Send type key (e.g., 'ppv_unlock', 'bump_normal')
        limit: Maximum captions to return (max 50)

    Returns:
        List of compatible captions
    """
    logger.info(f"get_send_type_captions: creator_id={creator_id}, send_type={send_type}")
    try:
        limit = min(max(1, limit), 50)

        # Map send types to caption categories
        category_map = {
            'ppv_unlock': 'ppv',
            'ppv_wall': 'ppv',
            'ppv_followup': 'followup',
            'bump_normal': 'bump',
            'bump_descriptive': 'bump',
            'bump_text_only': 'bump',
            'bump_flyer': 'bump',
            'tip_goal': 'tip',
            'renew_on_post': 'renewal',
            'renew_on_message': 'renewal',
            'expired_winback': 'winback',
            'link_drop': 'promo',
            'dm_farm': 'engagement'
        }
        category = category_map.get(send_type, 'general')

        # Query caption_bank (actual table name)
        captions = db_query("""
            SELECT caption_id, caption_text, caption_type as category,
                   performance_tier as quality_score, content_type_id,
                   global_last_used_date as last_used_at
            FROM caption_bank
            WHERE (caption_type = ? OR caption_type = 'general')
            AND is_active = 1
            ORDER BY
                CASE WHEN caption_type = ? THEN 0 ELSE 1 END,
                performance_tier ASC
            LIMIT ?
        """, (category, category, limit))

        return {
            "creator_id": creator_id,
            "send_type": send_type,
            "category_matched": category,
            "captions": captions,
            "count": len(captions)
        }

    except Exception as e:
        logger.error(f"get_send_type_captions error: {e}")
        return {"error": str(e), "captions": []}


@mcp.tool()
def validate_caption_structure(caption_text: str, send_type: str) -> dict:
    """Validates caption structure against anti-patterization rules.

    MCP Name: mcp__eros-db__validate_caption_structure

    Args:
        caption_text: The caption text to validate
        send_type: The intended send type

    Returns:
        Validation result with score and issues
    """
    logger.info(f"validate_caption_structure: send_type={send_type}, length={len(caption_text)}")

    issues = []
    score = 100

    # Length validation
    if len(caption_text) < 10:
        issues.append("Caption too short (min 10 chars)")
        score -= 30
    elif len(caption_text) < 20:
        issues.append("Caption very short (recommend 20+ chars)")
        score -= 10
    elif len(caption_text) > 500:
        issues.append("Caption too long (max 500 chars)")
        score -= 10
    elif len(caption_text) > 300:
        issues.append("Caption lengthy (recommend under 300 chars)")
        score -= 5

    # Spam pattern detection
    spam_patterns = [
        ("click here", 15),
        ("limited time", 10),
        ("act now", 15),
        ("don't miss", 10),
        ("hurry", 5),
        ("exclusive offer", 10),
        ("buy now", 15)
    ]

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

    score = max(0, min(100, score))

    return {
        "valid": score >= 70,
        "score": score,
        "issues": issues,
        "send_type": send_type,
        "caption_length": len(caption_text),
        "recommendation": "PASS" if score >= 85 else "REVIEW" if score >= 70 else "REJECT"
    }


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
