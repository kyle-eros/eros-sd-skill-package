"""
Dry-run trigger detection for all active creators.
Outputs what WOULD be detected without writing to DB.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_server"))
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from volume_utils import TRIGGER_THRESHOLDS, TRIGGER_DEFAULT_TTL_DAYS, CONFIDENCE_THRESHOLDS

import sqlite3

DB_PATH = Path(__file__).parent.parent / "data" / "eros_sd_main.db"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "trigger_backfill_dryrun.json"


def get_confidence(send_count: int) -> str:
    if send_count > CONFIDENCE_THRESHOLDS["high"]:
        return "high"
    elif send_count >= CONFIDENCE_THRESHOLDS["moderate"]:
        return "moderate"
    return "low"


def detect_triggers_for_content_type(ct: dict) -> list:
    """Detect triggers for a single content type."""
    triggers = []

    # Map to actual column names in top_content_types table
    name = ct.get("content_type", ct.get("type_name", ""))
    conv = (ct.get("avg_purchase_rate", 0) or 0) * 100  # Convert to percentage
    uses = ct.get("send_count", ct.get("sends_last_30d", 10)) or 10
    wow = ct.get("wow_rps_change", 0) or 0
    orc = ct.get("open_rate_7d_change", 0) or 0
    dec = ct.get("declining_rps_days", 0) or 0

    conf = get_confidence(uses)
    expires = (datetime.now() + timedelta(days=TRIGGER_DEFAULT_TTL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    th = TRIGGER_THRESHOLDS

    if conv >= th["HIGH_PERFORMER"]["min_conversion"]:
        triggers.append({
            "content_type": name,
            "trigger_type": "HIGH_PERFORMER",
            "adjustment_multiplier": th["HIGH_PERFORMER"]["multiplier"],
            "confidence": conf,
            "reason": f"Conversion {conv:.1f}%",
            "expires_at": expires
        })
    elif conv >= th["EMERGING_WINNER"]["min_conversion"] and uses < th["EMERGING_WINNER"]["max_uses_30d"]:
        triggers.append({
            "content_type": name,
            "trigger_type": "EMERGING_WINNER",
            "adjustment_multiplier": th["EMERGING_WINNER"]["multiplier"],
            "confidence": conf,
            "reason": f"Conversion {conv:.1f}%, {uses} uses/30d",
            "expires_at": expires
        })
    elif wow >= th["TRENDING_UP"]["min_wow_revenue_change"]:
        triggers.append({
            "content_type": name,
            "trigger_type": "TRENDING_UP",
            "adjustment_multiplier": th["TRENDING_UP"]["multiplier"],
            "confidence": conf,
            "reason": f"WoW revenue +{wow:.0f}%",
            "expires_at": expires
        })
    elif dec >= th["SATURATING"]["min_decline_days"]:
        triggers.append({
            "content_type": name,
            "trigger_type": "SATURATING",
            "adjustment_multiplier": th["SATURATING"]["multiplier"],
            "confidence": "moderate",
            "reason": f"Declining {dec} days",
            "expires_at": expires
        })
    elif orc <= th["AUDIENCE_FATIGUE"]["max_open_rate_change"]:
        triggers.append({
            "content_type": name,
            "trigger_type": "AUDIENCE_FATIGUE",
            "adjustment_multiplier": th["AUDIENCE_FATIGUE"]["multiplier"],
            "confidence": "moderate",
            "reason": f"Open rate {orc:.0f}%/7d",
            "expires_at": expires
        })

    return triggers


def main():
    print("=" * 60)
    print("TRIGGER BACKFILL DRY-RUN")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get active creators
    creators = conn.execute("""
        SELECT c.creator_id, c.page_name, c.current_fan_count,
               (SELECT volume_level FROM volume_assignments
                WHERE creator_id = c.creator_id AND is_active = 1
                ORDER BY assigned_at DESC LIMIT 1) as tier
        FROM creators c
        WHERE c.is_active = 1
        ORDER BY c.current_fan_count DESC
    """).fetchall()

    print(f"\nActive creators: {len(creators)}")

    results = {
        "run_at": datetime.now().isoformat(),
        "active_creator_count": len(creators),
        "creators": [],
        "summary": defaultdict(int),
        "total_triggers": 0
    }

    for creator in creators:
        cid = creator["creator_id"]

        # Get content type rankings (using actual column names)
        rankings = conn.execute("""
            SELECT content_type, avg_purchase_rate, send_count
            FROM top_content_types
            WHERE creator_id = ?
            AND analysis_date = (
                SELECT MAX(analysis_date) FROM top_content_types WHERE creator_id = ?
            )
        """, (cid, cid)).fetchall()

        detected = []
        for r in rankings:
            ct_data = dict(r)
            detected.extend(detect_triggers_for_content_type(ct_data))

        creator_result = {
            "creator_id": cid,
            "page_name": creator["page_name"],
            "fan_count": creator["current_fan_count"],
            "tier": creator["tier"],
            "triggers_detected": len(detected),
            "triggers": detected
        }
        results["creators"].append(creator_result)
        results["total_triggers"] += len(detected)

        for t in detected:
            results["summary"][t["trigger_type"]] += 1

        # Print progress
        if detected:
            print(f"\n{creator['page_name']} ({creator['tier'] or 'MINIMAL'}, {creator['current_fan_count'] or 0:,} fans):")
            for t in detected:
                print(f"  -> {t['trigger_type']} on {t['content_type']}: {t['adjustment_multiplier']}x")
        else:
            print(f"\n{creator['page_name']}: No triggers detected")

    conn.close()

    # Save results
    with open(OUTPUT_PATH, "w") as f:
        json.dump(dict(results), f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Active creators: {len(creators)}")
    print(f"Total triggers detected: {results['total_triggers']}")
    print("\nBy trigger type:")
    for tt, count in sorted(results["summary"].items()):
        print(f"  {tt}: {count}")
    print(f"\nResults saved to: {OUTPUT_PATH}")

    return results


if __name__ == "__main__":
    main()
