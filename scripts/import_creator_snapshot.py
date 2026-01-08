#!/usr/bin/env python3
"""
EROS Creator Snapshot Import Script
Imports fresh metrics from Infloww CSV into the creators table.

Usage:
    python import_creator_snapshot.py           # Execute import
    python import_creator_snapshot.py --dry-run # Preview changes without committing
"""

import sqlite3
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

# Configuration
DB_PATH = Path("/Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db")
CSV_PATH = Path("/Users/kylemerriman/Developer/eros-sd-skill-package/creator_snapshot - creators.csv")

# Explicit mappings for known problem cases (CSV name -> DB page_name)
# These override standard normalization for typos/variations
EXPLICIT_MAPPINGS = {
    "Oliva Hansley PAID": "olivia_hansley_paid",  # Typo in CSV (missing 'i')
}

# Column mappings: CSV column name -> Database column name
COLUMN_MAPPINGS = {
    "Active fans": "current_active_fans",
    "Following": "current_following",
    "New fans": "current_new_fans",
    "Fans with renew on": "current_fans_renew_on",
    "Renew on %": "current_renew_on_pct",
    "Change in expired fan count": "current_expired_fan_change",
    "Total earnings Net": "current_total_earnings",
    "Subscription Net": "current_subscription_net",
    "Tips Net": "current_tips_net",
    "Message Net": "current_message_net",
    "Posts Net": "current_posts_net",
    "Streams Net": "current_streams_net",
    "Refund Net": "current_refund_net",
    "Contribution %": "current_contribution_pct",
    "OF ranking": "current_of_ranking",
    "Avg spend per spender Net": "current_avg_spend_per_spender",
    "Avg spend per transaction Net": "current_avg_spend_per_txn",
    "Avg earnings per fan Net": "current_avg_earnings_per_fan",
    "Avg subscription length": "current_avg_subscription_length",
}


def normalize_creator_name(name: str) -> str:
    """Normalize creator name to match database page_name format."""
    if not name:
        return ""
    # Lowercase
    normalized = name.lower().strip()
    # Replace spaces with underscores
    normalized = normalized.replace(" ", "_")
    # Remove special characters except underscores
    normalized = re.sub(r'[^a-z0-9_]', '', normalized)
    return normalized


def fuzzy_match(name: str, candidates: list, threshold: float = 0.7) -> str | None:
    """Find best fuzzy match from candidates."""
    best_match = None
    best_score = 0
    for candidate in candidates:
        score = SequenceMatcher(None, name, candidate).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    return best_match


def parse_numeric(value: str) -> float | None:
    """Parse numeric value, handling currency symbols, commas, and percentages."""
    if not value or str(value).strip() == "" or value == "-":
        return None
    # Remove currency symbols, commas, whitespace
    cleaned = re.sub(r'[$,\s]', '', str(value))
    # Handle percentage
    if '%' in cleaned:
        cleaned = cleaned.replace('%', '')
        try:
            return float(cleaned)  # Keep as percentage value (not divided)
        except ValueError:
            return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date_range(date_time_str: str) -> tuple[str | None, str | None]:
    """Parse date range from 'YYYY-MM-DD - YYYY-MM-DD' format."""
    if not date_time_str:
        return None, None
    parts = date_time_str.split(" - ")
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return None, None


def main(dry_run: bool = False):
    """Main import function."""
    print("=" * 70)
    print("EROS Creator Snapshot Import")
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE EXECUTION'}")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    # Verify files exist
    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH}")
        return 1
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}")
        return 1

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get existing page_names
    cursor.execute("SELECT page_name, display_name FROM creators WHERE is_active = 1")
    db_creators = {row['page_name']: row['display_name'] for row in cursor.fetchall()}
    print(f"\nFound {len(db_creators)} active creators in database")

    # Read CSV
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)
    print(f"Found {len(csv_rows)} rows in CSV")

    # Track results
    updated = 0
    not_found = []
    errors = []
    before_after = []  # Track changes for reporting

    snapshot_date = datetime.now().isoformat()

    print("\n" + "-" * 70)
    print("PROCESSING CREATORS")
    print("-" * 70)

    for row in csv_rows:
        csv_creator = row.get('Creator', '').strip()
        if not csv_creator:
            continue

        # Try explicit mapping first
        if csv_creator in EXPLICIT_MAPPINGS:
            page_name = EXPLICIT_MAPPINGS[csv_creator]
            match_type = "EXPLICIT"
        else:
            # Standard normalization
            normalized = normalize_creator_name(csv_creator)

            # Direct match
            if normalized in db_creators:
                page_name = normalized
                match_type = "DIRECT"
            else:
                # Fuzzy match
                page_name = fuzzy_match(normalized, list(db_creators.keys()))
                match_type = "FUZZY" if page_name else None

        if not page_name or page_name not in db_creators:
            not_found.append(csv_creator)
            print(f"  [NOT FOUND] {csv_creator}")
            continue

        # Get before values for comparison
        cursor.execute("""
            SELECT current_message_net, current_total_earnings, current_active_fans,
                   metrics_snapshot_date
            FROM creators WHERE page_name = ?
        """, (page_name,))
        before = cursor.fetchone()

        # Build UPDATE query
        try:
            # Parse the date/time field for period info
            date_time = row.get('Date/Time', '')
            period_start, period_end = parse_date_range(date_time)

            update_fields = []
            update_values = []

            for csv_col, db_col in COLUMN_MAPPINGS.items():
                value = row.get(csv_col)
                if value is not None:
                    # Special handling for text fields
                    if db_col in ['current_of_ranking', 'current_avg_subscription_length']:
                        parsed = str(value).strip() if value and str(value).strip() not in ['', '-'] else None
                    else:
                        parsed = parse_numeric(value)
                    update_fields.append(f"{db_col} = ?")
                    update_values.append(parsed)

            # Add metadata fields
            update_fields.extend([
                "metrics_snapshot_date = ?",
                "updated_at = ?",
                "current_fan_count = ?",  # Set fan_count same as active_fans
                "metrics_period_start = ?",
                "metrics_period_end = ?"
            ])
            update_values.extend([
                snapshot_date,
                snapshot_date,
                parse_numeric(row.get('Active fans', '0')),
                period_start,
                period_end
            ])

            if dry_run:
                # Just report what would happen
                new_message_net = parse_numeric(row.get('Message Net', '0'))
                new_total = parse_numeric(row.get('Total earnings Net', '0'))
                print(f"  [{match_type}] {page_name} <- {csv_creator}")
                print(f"           message_net: ${before['current_message_net'] or 0:,.2f} -> ${new_message_net or 0:,.2f}")
                updated += 1
            else:
                # Execute update
                query = f"UPDATE creators SET {', '.join(update_fields)} WHERE page_name = ?"
                update_values.append(page_name)

                cursor.execute(query, update_values)

                if cursor.rowcount > 0:
                    updated += 1
                    new_message_net = parse_numeric(row.get('Message Net', '0'))
                    before_after.append({
                        'page_name': page_name,
                        'csv_name': csv_creator,
                        'match_type': match_type,
                        'old_message_net': before['current_message_net'],
                        'new_message_net': new_message_net,
                        'old_total': before['current_total_earnings'],
                        'new_total': parse_numeric(row.get('Total earnings Net', '0')),
                    })
                    print(f"  [{match_type}] Updated: {page_name} <- {csv_creator}")
                else:
                    errors.append(f"No rows affected for {page_name}")

        except Exception as e:
            errors.append(f"Error updating {csv_creator}: {e}")
            print(f"  [ERROR] {csv_creator}: {e}")

    if not dry_run:
        # Commit changes
        conn.commit()

    # Summary
    print("\n" + "=" * 70)
    print("IMPORT SUMMARY")
    print("=" * 70)
    print(f"{'Would update' if dry_run else 'Successfully updated'}: {updated}")
    print(f"Not found in database: {len(not_found)}")
    if not_found:
        for name in not_found:
            print(f"  - {name}")
    print(f"Errors: {len(errors)}")
    if errors:
        for err in errors:
            print(f"  - {err}")

    # Show key changes
    if before_after and not dry_run:
        print("\n" + "-" * 70)
        print("KEY CHANGES (Message Net)")
        print("-" * 70)
        print(f"{'Creator':<30} {'Old':>15} {'New':>15} {'Delta':>15}")
        print("-" * 70)
        for change in sorted(before_after, key=lambda x: abs((x['new_message_net'] or 0) - (x['old_message_net'] or 0)), reverse=True)[:15]:
            old = change['old_message_net'] or 0
            new = change['new_message_net'] or 0
            delta = new - old
            delta_str = f"+${delta:,.2f}" if delta >= 0 else f"-${abs(delta):,.2f}"
            print(f"{change['page_name']:<30} ${old:>13,.2f} ${new:>13,.2f} {delta_str:>15}")

    # Verify key creator
    print("\n" + "=" * 70)
    print("VERIFICATION: maya_hill")
    print("=" * 70)
    cursor.execute("""
        SELECT page_name, current_message_net, current_fan_count,
               metrics_snapshot_date, current_total_earnings,
               metrics_period_start, metrics_period_end
        FROM creators WHERE page_name = 'maya_hill'
    """)
    result = cursor.fetchone()
    if result:
        print(f"  page_name:            {result['page_name']}")
        print(f"  current_message_net:  ${result['current_message_net']:,.2f}" if result['current_message_net'] else "  current_message_net:  NULL")
        print(f"  current_fan_count:    {result['current_fan_count']}")
        print(f"  current_total_earnings: ${result['current_total_earnings']:,.2f}" if result['current_total_earnings'] else "  current_total_earnings: NULL")
        print(f"  metrics_snapshot_date: {result['metrics_snapshot_date']}")
        print(f"  metrics_period:       {result['metrics_period_start']} to {result['metrics_period_end']}")

    conn.close()
    print(f"\n{'DRY RUN ' if dry_run else ''}Completed: {datetime.now().isoformat()}")
    return 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry_run))
