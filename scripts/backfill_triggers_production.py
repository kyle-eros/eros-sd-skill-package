"""
Production backfill - saves detected triggers to database.
Uses save_volume_triggers MCP tool for validation.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_server"))

from main import save_volume_triggers

DRY_RUN_PATH = Path(__file__).parent.parent / "data" / "trigger_backfill_dryrun.json"


def main():
    print("=" * 60)
    print("TRIGGER BACKFILL - PRODUCTION")
    print("=" * 60)

    # Load dry-run results
    with open(DRY_RUN_PATH) as f:
        dry_run = json.load(f)

    print(f"\nBackfilling {dry_run['total_triggers']} triggers for {dry_run['active_creator_count']} creators")

    success_count = 0
    error_count = 0
    total_saved = 0

    for creator in dry_run["creators"]:
        if not creator["triggers"]:
            continue

        result = save_volume_triggers(
            creator_id=creator["creator_id"],
            triggers=creator["triggers"]
        )

        if result.get("success"):
            saved = result.get("triggers_saved", 0)
            total_saved += saved
            success_count += 1
            print(f"  OK {creator['page_name']}: {saved} triggers saved")
        else:
            error_count += 1
            print(f"  X {creator['page_name']}: {result.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)
    print(f"Creators processed: {success_count + error_count}")
    print(f"Successful: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Total triggers saved: {total_saved}")

    return error_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
