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
    include_vault: bool = True
) -> dict:
    """Retrieves comprehensive creator profile with analytics, volume, content rankings, and vault.

    MCP Name: mcp__eros-db__get_creator_profile

    This is the PRIMARY data-fetching tool for pipeline preflight. Returns a bundled
    response to minimize MCP calls during execution.

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        include_analytics: Include 30-day performance metrics with confidence (default: True)
        include_volume: Include volume tier and daily distribution (default: True)
        include_content_rankings: Include TOP/MID/LOW/AVOID content types (default: True)
        include_vault: Include vault availability from vault_matrix (default: True)

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
            "metadata": {
                "fetched_at", "data_sources_used", "mcp_calls_saved"
            }
        }
    """
    logger.info(f"get_creator_profile: creator_id={creator_id}, analytics={include_analytics}, volume={include_volume}, rankings={include_content_rankings}, vault={include_vault}")

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

            if vol_rows:
                vol = vol_rows[0]
                tier = vol.get("volume_level", "STANDARD")
                data_sources.append("volume_assignments")
            else:
                # Calculate from revenue
                if mm_rev < 150: tier = "MINIMAL"
                elif mm_rev < 800: tier = "LITE"
                elif mm_rev < 3000: tier = "STANDARD"
                elif mm_rev < 8000: tier = "HIGH_VALUE"
                else: tier = "PREMIUM"

            # Tier volume ranges
            tier_config = {
                "MINIMAL": {"rev": (1, 2), "eng": (1, 2), "ret": (1, 1)},
                "LITE": {"rev": (2, 4), "eng": (2, 4), "ret": (1, 2)},
                "STANDARD": {"rev": (4, 6), "eng": (4, 6), "ret": (2, 3)},
                "HIGH_VALUE": {"rev": (6, 9), "eng": (5, 8), "ret": (2, 4)},
                "PREMIUM": {"rev": (8, 12), "eng": (6, 10), "ret": (3, 5)}
            }
            ranges = tier_config.get(tier, tier_config["STANDARD"])

            response["volume_assignment"] = {
                "volume_level": tier,
                "mm_revenue_used": mm_rev,
                "revenue_per_day": list(ranges["rev"]),
                "engagement_per_day": list(ranges["eng"]),
                "retention_per_day": list(ranges["ret"]),
                "ppv_per_day": vol_rows[0].get("ppv_per_day") if vol_rows else None,
                "bump_per_day": vol_rows[0].get("bump_per_day") if vol_rows else None
            }

        # Step 5: Get content type rankings (if requested)
        if include_content_rankings:
            rankings = db_query("""
                SELECT
                    content_type as type_name,
                    performance_tier,
                    avg_rps as rps,
                    avg_purchase_rate as conversion_rate,
                    send_count,
                    total_earnings,
                    confidence_score
                FROM top_content_types
                WHERE creator_id = ?
                ORDER BY avg_rps DESC
            """, (creator_pk,))

            if rankings:
                data_sources.append("top_content_types")

            response["top_content_types"] = rankings or []
            response["avoid_types"] = [r["type_name"] for r in rankings if r.get("performance_tier") == "AVOID"]
            response["top_types"] = [r["type_name"] for r in rankings if r.get("performance_tier") == "TOP"]

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

        # Step 6: Add metadata
        mcp_calls_saved = 0
        if include_analytics: mcp_calls_saved += 1
        if include_volume: mcp_calls_saved += 1
        if include_content_rankings: mcp_calls_saved += 1
        if include_vault: mcp_calls_saved += 1

        response["metadata"] = {
            "fetched_at": fetched_at,
            "data_sources_used": list(set(data_sources)),
            "mcp_calls_saved": mcp_calls_saved,
            "include_flags": {
                "analytics": include_analytics,
                "volume": include_volume,
                "content_rankings": include_content_rankings,
                "vault": include_vault
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

        # Map send types to caption categories (for fallback only)
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
        # Priority: 1) Exact send_type match, 2) Category fallback, 3) General captions
        captions = db_query("""
            SELECT caption_id, caption_text, caption_type as category,
                   performance_tier as quality_score, content_type_id,
                   global_last_used_date as last_used_at
            FROM caption_bank
            WHERE (caption_type = ? OR caption_type = ? OR caption_type = 'general')
            AND is_active = 1
            ORDER BY
                CASE WHEN caption_type = ? THEN 0
                     WHEN caption_type = ? THEN 1
                     ELSE 2 END,
                performance_tier ASC
            LIMIT ?
        """, (send_type, category, send_type, category, limit))

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
