# EROS Skill Package MCP Infrastructure Perfection Prompt

**Target**: EROS Schedule Generator Skill Package  
**Database**: `eros_sd_main.db` (SQLite3)  
**Old Project Location**: `/Users/kylemerriman/Developer/Archived-EROS-SD-MAIN-PROJECT`  
**Claude Code Version**: v2.0.76+  
**MCP Specification**: 2025-11-25  
**Prompt Version**: 3.0.0 (FINAL)

---

## ⚠️ PRE-EXECUTION CHECKLIST (REQUIRED)

**STOP! Before executing ANY phase, complete ALL items below:**

### 1. Verify Working Directory
```bash
pwd
# MUST show your eros-sd-skill-package directory
# If not, cd to the correct location first
```

### 2. Confirm Database Location
```bash
find /Users/kylemerriman -name "eros_sd_main.db" -type f 2>/dev/null
```
**Q1**: Full database path: ____________________

### 3. Verify Database Schema
```bash
# Replace [path-to-db] with answer from Q1
sqlite3 [path-to-db] ".tables"
```
**Q2**: Mark which tables exist:
- [ ] `creators`
- [ ] `captions`  
- [ ] `content_types`
- [ ] `send_types`
- [ ] `schedule_templates` (or similar: ____________)
- [ ] `vault_content` (or similar: ____________)
- [ ] `content_type_rankings` (or similar: ____________)
- [ ] `volume_triggers` (or similar: ____________)
- [ ] `personas` (or similar: ____________)
- [ ] `mass_messages` (or similar: ____________)
- [ ] `volume_configs` (or similar: ____________)

**Q3**: What is the creator identifier column in `creators` table?
```bash
sqlite3 [path-to-db] "PRAGMA table_info(creators);" | head -20
```
- [ ] `creator_id`
- [ ] `page_name`
- [ ] `id` (numeric primary key)
- [ ] Other: ____________

### 4. Verify Python Environment
```bash
python --version  # Requires 3.10+
pip show mcp 2>/dev/null || echo "MCP NOT INSTALLED"
```
**Q4**: Python version: ______ | MCP installed: [ ] Yes [ ] No

### 5. Record Table Name Mappings
Based on Q2, fill in actual table names for any non-standard naming:

| Expected Name | Actual Name (if different) |
|---------------|---------------------------|
| `creators` | |
| `captions` | |
| `content_types` | |
| `send_types` | |
| `schedule_templates` | |
| `vault_content` | |
| `content_type_rankings` | |
| `volume_triggers` | |
| `personas` | |
| `mass_messages` | |
| `volume_configs` | |

---

## ⛔ PRE-EXECUTION GATE

**DO NOT PROCEED unless ALL of the following are true:**
- [ ] Q1-Q4 answered completely
- [ ] Database path confirmed and accessible
- [ ] Python 3.10+ confirmed
- [ ] Table name mappings recorded

**Missing any item? STOP and resolve before continuing.**

---

## EXECUTION INSTRUCTIONS

### Sequential Execution Pattern
Execute each phase **SEQUENTIALLY** using the specified subagent via the Task tool:

```
Task: [phase description]
Subagent: [specified-subagent]
Prompt: [include FULL prompt text from that phase]
```

### Phase Completion Requirements
**DO NOT proceed to the next phase until:**
1. ✓ Current phase outputs explicit "PHASE N COMPLETE" message
2. ✓ All listed output files/directories verified to exist
3. ✓ No errors during execution

### Failure Recovery Protocol
If ANY phase fails:
1. **READ** the error message carefully
2. **FIX** within the same phase (re-run subagent with corrections)
3. **VERIFY** fix resolved the issue
4. If unfixable after 2 attempts: **STOP** and document the error
5. **NEVER** proceed to subsequent phases with unresolved errors

---

## PHASE 0: DISCOVERY & AUDIT
**Executor**: `sre-engineer` (sonnet)  
**Estimated Time**: 3-5 minutes  
**Dependencies**: Pre-execution checklist complete  
**Outputs**: `./mcp-audit-report.md`

### Task Description
Perform comprehensive discovery of ALL MCP-related configurations across both the new skill package AND the archived old project.

### Detailed Instructions

```markdown
You are performing a critical infrastructure audit for the EROS Schedule Generator MCP migration.

## STEP 0.1: Scan Current Skill Package Root
Find and list ALL files that might contain MCP configurations:

```bash
echo "=== Current Skill Package MCP Scan ==="
echo "Working directory: $(pwd)"
for file in .mcp.json plugin.json .claude/settings.json .claude/settings.local.json CLAUDE.md CLAUDE.local.md; do
    if [ -f "$file" ]; then
        echo "FOUND: $file"
        echo "  Size: $(ls -lh "$file" | awk '{print $5}')"
        echo "  Contains MCP: $(grep -l 'mcp\|mcpServers' "$file" 2>/dev/null && echo 'YES' || echo 'NO')"
    else
        echo "NOT FOUND: $file"
    fi
done
```

## STEP 0.2: Check User-Level Configs
```bash
echo "=== User-Level MCP Configs ==="
if [ -f ~/.claude.json ]; then
    echo "~/.claude.json exists"
    echo "  Size: $(ls -lh ~/.claude.json | awk '{print $5}')"
    echo "  EROS entries: $(grep -c "eros" ~/.claude.json 2>/dev/null || echo '0')"
    grep -B2 -A5 "eros" ~/.claude.json 2>/dev/null || echo "  No eros entries found"
else
    echo "~/.claude.json not found - clean"
fi
```

## STEP 0.3: Scan Archived Old Project
```bash
echo "=== Archived Project Scan ==="
OLD_PROJECT="/Users/kylemerriman/Developer/Archived-EROS-SD-MAIN-PROJECT"
if [ -d "$OLD_PROJECT" ]; then
    echo "Old project found at: $OLD_PROJECT"
    echo ""
    echo "MCP config files:"
    find "$OLD_PROJECT" -name ".mcp.json" -o -name "plugin.json" 2>/dev/null | while read f; do
        echo "  $f"
    done
    echo ""
    echo "MCP server implementations:"
    find "$OLD_PROJECT" -name "index.ts" -o -name "index.js" -o -name "server.py" 2>/dev/null | while read f; do
        echo "  $f"
    done
    echo ""
    echo "Database references:"
    grep -r "eros_sd_main.db" "$OLD_PROJECT" --include="*.json" --include="*.py" --include="*.ts" -l 2>/dev/null | while read f; do
        echo "  $f"
    done
else
    echo "WARNING: Old project directory not found at $OLD_PROJECT"
fi
```

## STEP 0.4: Locate All Database Files
```bash
echo "=== Database Location Search ==="
DB_COUNT=0
find /Users/kylemerriman -name "eros_sd_main.db" -type f 2>/dev/null | while read db; do
    DB_COUNT=$((DB_COUNT + 1))
    echo "Database $DB_COUNT: $db"
    echo "  Size: $(ls -lh "$db" | awk '{print $5}')"
    echo "  Modified: $(stat -f '%Sm' "$db" 2>/dev/null || stat -c '%y' "$db" 2>/dev/null)"
    echo "  Tables: $(sqlite3 "$db" ".tables" 2>/dev/null | wc -w | tr -d ' ')"
done

if [ $DB_COUNT -eq 0 ]; then
    echo "ERROR: No database files found!"
fi
```

## STEP 0.5: Generate Audit Report
Create `./mcp-audit-report.md`:

```bash
cat > ./mcp-audit-report.md << 'REPORT'
# MCP Infrastructure Audit Report

**Generated**: $(date -Iseconds)
**Skill Package**: $(pwd)
**Audited By**: Phase 0 - sre-engineer

## Summary

| Item | Status |
|------|--------|
| MCP configs in project | [count] |
| MCP configs in old project | [count] |
| User-level EROS configs | [yes/no] |
| Database files found | [count] |

## Current Skill Package

| File | Exists | Contains MCP | Notes |
|------|--------|--------------|-------|
| .mcp.json | | | |
| plugin.json | | | |
| .claude/settings.json | | | |
| .claude/settings.local.json | | | |

## Archived Project

**Location**: /Users/kylemerriman/Developer/Archived-EROS-SD-MAIN-PROJECT

### MCP Config Files Found
[list]

### MCP Server Implementations Found
[list]

## Database

| Property | Value |
|----------|-------|
| Primary Location | [path] |
| Size | [size] |
| Last Modified | [date] |
| Table Count | [count] |

## Recommended Actions

1. [ ] Archive old MCP configs before proceeding
2. [ ] Copy database to ./data/ directory
3. [ ] Remove conflicting user-level configs

## Potential Conflicts

[List any duplicate or conflicting configurations that could cause issues]

---
*End of Audit Report*
REPORT

echo "Audit report created: ./mcp-audit-report.md"
```

## OUTPUT REQUIREMENTS
- [ ] Audit report created at `./mcp-audit-report.md`
- [ ] All MCP config locations documented
- [ ] Database location(s) identified
- [ ] No errors during scan

## COMPLETION CONFIRMATION
State: "PHASE 0 COMPLETE: Audit report generated at ./mcp-audit-report.md. Found [N] MCP configs, [N] database files. Primary database at [PATH]."
```

---

## PHASE 1: ARCHIVE & CLEANUP
**Executor**: `platform-engineer` (sonnet)  
**Estimated Time**: 2-3 minutes  
**Dependencies**: Phase 0 complete, `./mcp-audit-report.md` exists  
**Outputs**: `./archived/old-mcp-configs-[timestamp]/`, backup documentation

### Task Description
Archive all old MCP configurations to prevent conflicts, then verify clean state.

### Detailed Instructions

```markdown
You are performing critical cleanup to prevent MCP configuration conflicts.

**REQUIRED INPUT**: Read `./mcp-audit-report.md` first to understand what needs cleanup.

## STEP 1.1: Create Timestamped Archive Directory
```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="./archived/old-mcp-configs-${TIMESTAMP}"
mkdir -p "$ARCHIVE_DIR"
echo "Archive directory created: $ARCHIVE_DIR"
```

## STEP 1.2: Archive Old Project MCP Files
```bash
OLD_PROJECT="/Users/kylemerriman/Developer/Archived-EROS-SD-MAIN-PROJECT"

mkdir -p "$ARCHIVE_DIR/old-project"

# Copy any MCP-related files from old project
if [ -d "$OLD_PROJECT" ]; then
    find "$OLD_PROJECT" -name ".mcp.json" -exec cp {} "$ARCHIVE_DIR/old-project/" \; 2>/dev/null
    find "$OLD_PROJECT" -name "plugin.json" -exec cp {} "$ARCHIVE_DIR/old-project/" \; 2>/dev/null
    echo "Archived old project MCP files"
else
    echo "Note: Old project directory not found - skipping"
fi

# Create manifest of archived files
echo "# MCP Archive Manifest" > "$ARCHIVE_DIR/manifest.txt"
echo "Created: $(date -Iseconds)" >> "$ARCHIVE_DIR/manifest.txt"
echo "" >> "$ARCHIVE_DIR/manifest.txt"
echo "## Files:" >> "$ARCHIVE_DIR/manifest.txt"
find "$ARCHIVE_DIR" -type f -name "*.json" >> "$ARCHIVE_DIR/manifest.txt"
```

## STEP 1.3: Handle User-Level EROS Configs
```bash
# Backup user config (DO NOT DELETE - just backup for safety)
if [ -f ~/.claude.json ]; then
    cp ~/.claude.json "$ARCHIVE_DIR/user-claude.json.backup"
    echo "Backed up ~/.claude.json"
    
    # Document any EROS entries
    if grep -q "eros" ~/.claude.json; then
        echo ""
        echo "WARNING: Found eros entries in ~/.claude.json"
        grep -B2 -A10 "eros" ~/.claude.json > "$ARCHIVE_DIR/user-config-eros-entries.txt"
        echo "Documented EROS entries in archive"
        echo "NOTE: Manual cleanup may be required after successful setup"
    fi
else
    echo "No ~/.claude.json found - clean"
fi
```

## STEP 1.4: Remove Any Existing .mcp.json in Current Project
```bash
if [ -f .mcp.json ]; then
    cp .mcp.json "$ARCHIVE_DIR/current-project-mcp.json"
    rm .mcp.json
    echo "Archived and removed existing .mcp.json"
else
    echo "No existing .mcp.json to remove - clean"
fi

# Also check for plugin.json (shouldn't exist but verify)
if [ -f plugin.json ]; then
    cp plugin.json "$ARCHIVE_DIR/current-project-plugin.json"
    rm plugin.json
    echo "Archived and removed existing plugin.json"
fi
```

## STEP 1.5: Create Cleanup Documentation
```bash
cat > "$ARCHIVE_DIR/README.md" << 'README'
# MCP Configuration Cleanup Archive

**Date**: [TIMESTAMP]
**Purpose**: Migration to new EROS MCP infrastructure

## Files Archived

| Source | Archive Location |
|--------|-----------------|
| [list sources] | [list destinations] |

## Changes Made

1. Archived old project MCP configs
2. Backed up user-level configs
3. Removed current project .mcp.json (if existed)

## How to Restore

If rollback needed:

1. Copy files back from this archive:
   ```bash
   cp ./archived/old-mcp-configs-[TIMESTAMP]/current-project-mcp.json ./.mcp.json
   ```

2. Restore user config:
   ```bash
   cp ./archived/old-mcp-configs-[TIMESTAMP]/user-claude.json.backup ~/.claude.json
   ```

---
*Archive created during EROS MCP setup Phase 1*
README

sed -i '' "s/\[TIMESTAMP\]/$TIMESTAMP/g" "$ARCHIVE_DIR/README.md" 2>/dev/null || \
sed -i "s/\[TIMESTAMP\]/$TIMESTAMP/g" "$ARCHIVE_DIR/README.md"

echo "Created archive README"
```

## STEP 1.6: Verify Clean Slate
```bash
echo ""
echo "=== Clean Slate Verification ==="
CLEAN=true

if [ -f .mcp.json ]; then
    echo "✗ ERROR: .mcp.json still exists!"
    CLEAN=false
else
    echo "✓ No .mcp.json in project root"
fi

if [ -f plugin.json ]; then
    echo "! Warning: plugin.json exists (may be intentional)"
else
    echo "✓ No plugin.json in project root"
fi

if [ -d "$ARCHIVE_DIR" ]; then
    echo "✓ Archive directory created"
else
    echo "✗ ERROR: Archive directory not created!"
    CLEAN=false
fi

if [ "$CLEAN" = true ]; then
    echo ""
    echo "Clean slate verification: PASSED"
else
    echo ""
    echo "Clean slate verification: FAILED - review errors above"
fi
```

## OUTPUT REQUIREMENTS
- [ ] Archive directory created: `./archived/old-mcp-configs-[timestamp]/`
- [ ] Old project configs copied to archive
- [ ] User config backed up (if existed)
- [ ] Current project .mcp.json removed (if existed)
- [ ] README created in archive
- [ ] Clean slate verification passed

## COMPLETION CONFIRMATION
State: "PHASE 1 COMPLETE: Archived [N] files to ./archived/old-mcp-configs-[timestamp]/. Clean slate verified. Ready for database setup."
```

---

## PHASE 2: DATABASE POSITIONING
**Executor**: `database-administrator` (inherit)  
**Estimated Time**: 5-10 minutes  
**Dependencies**: Phase 1 complete, database location known from pre-execution checklist  
**Outputs**: `./data/eros_sd_main.db`, `./data/db-config.json`, schema documentation

### Task Description
Position the SQLite database within the skill package and validate its schema.

### Detailed Instructions

```markdown
You are setting up the database infrastructure for the EROS MCP server.

**REQUIRED INPUTS FROM PRE-EXECUTION CHECKLIST**:
- Database source path (Q1): [USER_MUST_PROVIDE]
- Table name mappings (Q5): [USER_MUST_PROVIDE]

## STEP 2.1: Create Data Directory
```bash
mkdir -p ./data
chmod 755 ./data
echo "Created ./data directory"
ls -la ./data
```

## STEP 2.2: Update .gitignore for Database Files
```bash
# Check if .gitignore exists and add database entries
if [ -f .gitignore ]; then
    # Check if already has database entries
    if grep -q "data/\*.db" .gitignore; then
        echo ".gitignore already has database entries"
    else
        echo "" >> .gitignore
        echo "# Database files (EROS MCP)" >> .gitignore
        echo "data/*.db" >> .gitignore
        echo "data/*.db-journal" >> .gitignore
        echo "data/*.db-wal" >> .gitignore
        echo "data/*.db-shm" >> .gitignore
        echo "Updated .gitignore"
    fi
else
    cat > .gitignore << 'GITIGNORE'
# Database files (EROS MCP)
data/*.db
data/*.db-journal
data/*.db-wal
data/*.db-shm
GITIGNORE
    echo "Created .gitignore with database entries"
fi
```

## STEP 2.3: Copy Database with Verification
```bash
# REPLACE THIS PATH with actual database path from Q1
DB_SOURCE="[REPLACE_WITH_Q1_ANSWER]"

echo "Source database: $DB_SOURCE"

if [ -f "$DB_SOURCE" ]; then
    # Copy database
    cp "$DB_SOURCE" ./data/eros_sd_main.db
    
    # Verify copy succeeded
    if [ -f ./data/eros_sd_main.db ]; then
        SOURCE_SIZE=$(ls -l "$DB_SOURCE" | awk '{print $5}')
        DEST_SIZE=$(ls -l ./data/eros_sd_main.db | awk '{print $5}')
        
        if [ "$SOURCE_SIZE" = "$DEST_SIZE" ]; then
            echo "✓ Database copied successfully"
            echo "  Source size: $SOURCE_SIZE bytes"
            echo "  Dest size: $DEST_SIZE bytes"
        else
            echo "✗ ERROR: Size mismatch after copy!"
            echo "  Source: $SOURCE_SIZE, Dest: $DEST_SIZE"
            exit 1
        fi
    else
        echo "✗ ERROR: Database file not created!"
        exit 1
    fi
else
    echo "✗ ERROR: Source database not found at: $DB_SOURCE"
    echo "Please verify the path from pre-execution checklist Q1"
    exit 1
fi
```

## STEP 2.4: Verify Database Integrity
```bash
echo ""
echo "=== Database Integrity Check ==="

INTEGRITY=$(sqlite3 ./data/eros_sd_main.db "PRAGMA integrity_check;")
if [ "$INTEGRITY" = "ok" ]; then
    echo "✓ Database integrity: OK"
else
    echo "✗ Database integrity: FAILED"
    echo "  Result: $INTEGRITY"
    exit 1
fi

# Quick access check
TABLE_COUNT=$(sqlite3 ./data/eros_sd_main.db ".tables" | wc -w | tr -d ' ')
echo "✓ Database accessible: $TABLE_COUNT tables found"
```

## STEP 2.5: Document Complete Schema
```bash
echo ""
echo "=== Documenting Schema ==="

# List all tables
sqlite3 ./data/eros_sd_main.db ".tables" > ./data/schema-tables.txt
echo "Tables found:"
cat ./data/schema-tables.txt

# Full schema
sqlite3 ./data/eros_sd_main.db ".schema" > ./data/schema-full.sql
echo ""
echo "Full schema saved to ./data/schema-full.sql"

# Record counts for key tables
echo ""
echo "=== Table Record Counts ==="
sqlite3 ./data/eros_sd_main.db << 'EOF'
.mode column
.headers on
SELECT 'creators' as "Table", COUNT(*) as "Records" FROM creators
UNION ALL SELECT 'captions', COUNT(*) FROM captions
UNION ALL SELECT 'content_types', COUNT(*) FROM content_types
UNION ALL SELECT 'send_types', COUNT(*) FROM send_types;
EOF
```

## STEP 2.6: Discover Actual Column Names
```bash
echo ""
echo "=== Column Name Discovery ==="

echo "creators table columns:"
sqlite3 ./data/eros_sd_main.db "PRAGMA table_info(creators);" | cut -d'|' -f2

echo ""
echo "Key identifier column check:"
sqlite3 ./data/eros_sd_main.db "SELECT name FROM pragma_table_info('creators') WHERE name IN ('creator_id', 'page_name', 'id');"
```

## STEP 2.7: Create Database Config File
```bash
cat > ./data/db-config.json << 'CONFIG'
{
  "database_path": "./data/eros_sd_main.db",
  "database_type": "sqlite3",
  "connection_settings": {
    "journal_mode": "WAL",
    "synchronous": "NORMAL",
    "foreign_keys": true,
    "busy_timeout": 5000
  },
  "table_mappings": {
    "_comment": "Map expected names to actual table names if different",
    "creators": "creators",
    "captions": "captions",
    "content_types": "content_types",
    "send_types": "send_types",
    "schedule_templates": "schedule_templates",
    "vault_content": "vault_content",
    "content_type_rankings": "content_type_rankings",
    "volume_triggers": "volume_triggers",
    "personas": "personas",
    "mass_messages": "mass_messages",
    "volume_configs": "volume_configs"
  },
  "migration": {
    "source_path": "[SOURCE_PATH]",
    "migration_date": "$(date -Iseconds)",
    "migrated_by": "EROS MCP Setup Phase 2"
  }
}
CONFIG

echo "Created ./data/db-config.json"
```

## STEP 2.8: Set Appropriate Permissions
```bash
chmod 644 ./data/eros_sd_main.db
chmod 644 ./data/db-config.json
chmod 644 ./data/schema-*.txt 2>/dev/null
chmod 644 ./data/schema-*.sql 2>/dev/null
echo "Permissions set"
ls -la ./data/
```

## OUTPUT REQUIREMENTS
- [ ] `./data/` directory created
- [ ] Database copied to `./data/eros_sd_main.db`
- [ ] Size matches source
- [ ] Integrity check passed
- [ ] Schema documented (`schema-tables.txt`, `schema-full.sql`)
- [ ] `./data/db-config.json` created
- [ ] .gitignore updated
- [ ] Permissions set correctly

## COMPLETION CONFIRMATION
State: "PHASE 2 COMPLETE: Database positioned at ./data/eros_sd_main.db ([SIZE]). Schema: [N] tables. Integrity check: PASSED."
```

---

## PHASE 3: MCP SERVER IMPLEMENTATION
**Executor**: `mcp-developer` (sonnet)  
**Estimated Time**: 15-20 minutes  
**Dependencies**: Phase 2 complete, database positioned, schema documented  
**Outputs**: `.mcp.json`, `./mcp_server/main.py`

### Task Description
Create the complete MCP server configuration and Python implementation with all 14 tools.

### Detailed Instructions

```markdown
You are creating the MCP server for the EROS Schedule Generator.

**CRITICAL REFERENCES**:
- MCP Specification: 2025-11-25
- Database schema: Read `./data/schema-full.sql` first
- Table names: From `./data/db-config.json` table_mappings

**IMPORTANT**: All 14 tools MUST be in a single file (main.py) to avoid circular import issues.

## STEP 3.1: Create .mcp.json Configuration
Create `.mcp.json` at project root:

```json
{
  "mcpServers": {
    "eros-db": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server.main"],
      "env": {
        "EROS_DB_PATH": "./data/eros_sd_main.db",
        "LOG_LEVEL": "info",
        "PYTHONPATH": "."
      },
      "timeout": 30000
    }
  }
}
```

**Note**: Using relative path `./data/eros_sd_main.db` which works from project root.

## STEP 3.2: Create Directory Structure
```bash
mkdir -p ./mcp_server
touch ./mcp_server/__init__.py
echo "Created ./mcp_server directory"
```

## STEP 3.3: Install MCP SDK (if needed)
```bash
pip install mcp --upgrade
pip show mcp | grep -E "Name|Version"
```

## STEP 3.4: Create Main Server Implementation
Create `./mcp_server/main.py` with ALL 14 tools in a single file:

```python
"""EROS Schedule Generator MCP Server.

Provides database tools for the EROS schedule generation pipeline.
MCP Specification: 2025-11-25
Server Name: eros-db
Tool Naming Convention: mcp__eros-db__<tool-name>

Tools (14 total):
  Creator (5): get_creator_profile, get_active_creators, get_vault_availability,
               get_content_type_rankings, get_persona_profile
  Schedule (5): get_volume_config, get_active_volume_triggers, get_performance_trends,
                save_schedule, save_volume_triggers
  Caption (3): get_batch_captions_by_content_types, get_send_type_captions,
               validate_caption_structure
  Config (1): get_send_types
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
            creator_pk = profile.get('id')
            if creator_pk:
                analytics = db_query("""
                    SELECT 
                        AVG(rps) as avg_rps,
                        AVG(conversion_rate) as avg_conversion,
                        AVG(open_rate) as avg_open_rate,
                        SUM(total_earnings) as total_earnings,
                        COUNT(*) as total_sends
                    FROM mass_messages 
                    WHERE creator_id = ?
                    AND sent_date >= date('now', '-30 days')
                """, (creator_pk,))
                if analytics:
                    profile['analytics_30d'] = dict(analytics[0])
        
        return profile
        
    except Exception as e:
        logger.error(f"get_creator_profile error: {e}")
        return {"error": str(e), "found": False}


@mcp.tool()
def get_active_creators(limit: int = 100, tier: str = None) -> list:
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
            SELECT creator_id, page_name, page_type, is_active,
                   current_fan_count, mm_revenue_monthly, volume_tier
            FROM creators 
            WHERE is_active = 1
        """
        params = []
        
        if tier and tier in ('MINIMAL', 'LITE', 'STANDARD', 'HIGH_VALUE', 'PREMIUM'):
            query += " AND volume_tier = ?"
            params.append(tier)
            
        query += " ORDER BY mm_revenue_monthly DESC LIMIT ?"
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
        creator = db_query(
            "SELECT id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "available_types": []}
        
        creator_pk = creator[0]['id']
        
        types = db_query("""
            SELECT ct.type_name, COUNT(v.id) as content_count
            FROM vault_content v
            JOIN content_types ct ON v.content_type_id = ct.id
            WHERE v.creator_id = ? AND v.is_available = 1
            GROUP BY ct.type_name
            ORDER BY content_count DESC
        """, (creator_pk,))
        
        type_names = [t['type_name'] for t in types]
        
        return {
            "creator_id": creator_id,
            "available_types": types,
            "type_names": type_names,
            "total_available": sum(t.get('content_count', 0) for t in types)
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
        creator = db_query(
            "SELECT id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "content_types": []}
        
        creator_pk = creator[0]['id']
        
        rankings = db_query("""
            SELECT ct.type_name, ctr.performance_tier,
                   ctr.rps, ctr.conversion_rate, ctr.sends_last_30d,
                   ctr.wow_rps_change, ctr.open_rate_7d_change
            FROM content_type_rankings ctr
            JOIN content_types ct ON ctr.content_type_id = ct.id
            WHERE ctr.creator_id = ?
            ORDER BY ctr.rps DESC
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
        results = db_query("""
            SELECT p.* FROM personas p
            JOIN creators c ON p.creator_id = c.id
            WHERE c.creator_id = ? OR c.page_name = ?
            LIMIT 1
        """, (creator_id, creator_id))
        
        if not results:
            # Return sensible defaults if no persona configured
            return {
                "creator_id": creator_id,
                "primary_tone": "GFE",
                "secondary_tone": "playful",
                "archetype": "girl_next_door",
                "voice_settings": {},
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
        results = db_query("""
            SELECT c.mm_revenue_monthly, c.volume_tier, c.content_category,
                   c.current_fan_count, c.page_type,
                   vc.fused_saturation, vc.fused_opportunity
            FROM creators c
            LEFT JOIN volume_configs vc ON c.id = vc.creator_id
            WHERE c.creator_id = ? OR c.page_name = ?
            LIMIT 1
        """, (creator_id, creator_id))
        
        if not results:
            return {"error": f"Creator not found: {creator_id}"}
        
        row = dict(results[0])
        revenue = row.get('mm_revenue_monthly') or 0
        
        # Calculate tier from revenue (DOMAIN_KNOWLEDGE.md Section 2)
        if revenue < 150:
            tier, rev, eng, ret = "MINIMAL", (1, 2), (1, 2), (1, 1)
        elif revenue < 800:
            tier, rev, eng, ret = "LITE", (2, 4), (2, 4), (1, 2)
        elif revenue < 3000:
            tier, rev, eng, ret = "STANDARD", (4, 6), (4, 6), (2, 3)
        elif revenue < 8000:
            tier, rev, eng, ret = "HIGH_VALUE", (6, 9), (5, 8), (2, 4)
        else:
            tier, rev, eng, ret = "PREMIUM", (8, 12), (6, 10), (3, 5)
        
        return {
            "creator_id": creator_id,
            "week_start": week_start,
            "tier": tier,
            "mm_revenue_monthly": revenue,
            "page_type": row.get('page_type', 'paid'),
            "content_category": row.get('content_category'),
            "current_fan_count": row.get('current_fan_count', 0),
            "revenue_per_day": list(rev),
            "engagement_per_day": list(eng),
            "retention_per_day": list(ret),
            "fused_saturation": row.get('fused_saturation') or 50,
            "fused_opportunity": row.get('fused_opportunity') or 50
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
            JOIN creators c ON vt.creator_id = c.id
            WHERE (c.creator_id = ? OR c.page_name = ?)
            AND vt.expires_at > datetime('now')
            ORDER BY vt.adjustment_multiplier DESC
        """, (creator_id, creator_id))
        
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
        
        metrics = db_query("""
            SELECT 
                AVG(rps) as avg_rps,
                AVG(conversion_rate) as avg_conversion,
                AVG(open_rate) as avg_open_rate,
                SUM(total_earnings) as total_earnings,
                COUNT(*) as total_sends,
                MIN(sent_date) as first_send,
                MAX(sent_date) as last_send
            FROM mass_messages mm
            JOIN creators c ON mm.creator_id = c.id
            WHERE (c.creator_id = ? OR c.page_name = ?)
            AND mm.sent_date >= date('now', ?)
        """, (creator_id, creator_id, f'-{days} days'))
        
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
        # (simplified - full implementation would compare week-over-week)
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
        creator = db_query(
            "SELECT id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "success": False}
        
        creator_pk = creator[0]['id']
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO schedule_templates (
                    creator_id, week_start, items_json,
                    validation_certificate, item_count, created_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (
                creator_pk,
                week_start,
                json.dumps(items),
                json.dumps(validation_certificate) if validation_certificate else None,
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
        creator = db_query(
            "SELECT id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "success": False}
        
        creator_pk = creator[0]['id']
        saved = 0
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for trigger in triggers:
                cursor.execute("""
                    INSERT OR REPLACE INTO volume_triggers (
                        creator_id, content_type, trigger_type,
                        adjustment_multiplier, confidence, reason, expires_at,
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
        creator = db_query(
            "SELECT id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "captions_by_type": {}}
        
        creator_pk = creator[0]['id']
        limit_per_type = min(max(1, limit_per_type), 20)  # Clamp 1-20
        
        results = {}
        total = 0
        
        for ct in content_types:
            captions = db_query("""
                SELECT c.id as caption_id, c.caption_text, c.category, 
                       c.quality_score, ct.type_name as content_type,
                       c.last_used_at, c.use_count
                FROM captions c
                JOIN content_types ct ON c.content_type_id = ct.id
                WHERE c.creator_id = ? 
                AND ct.type_name = ? 
                AND c.is_active = 1
                ORDER BY c.quality_score DESC, c.last_used_at ASC NULLS FIRST
                LIMIT ?
            """, (creator_pk, ct, limit_per_type))
            
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
        creator = db_query(
            "SELECT id FROM creators WHERE creator_id = ? OR page_name = ? LIMIT 1",
            (creator_id, creator_id)
        )
        if not creator:
            return {"error": f"Creator not found: {creator_id}", "captions": []}
        
        creator_pk = creator[0]['id']
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
        
        captions = db_query("""
            SELECT id as caption_id, caption_text, category, 
                   quality_score, content_type_id, last_used_at
            FROM captions
            WHERE creator_id = ? 
            AND (category = ? OR category = 'general') 
            AND is_active = 1
            ORDER BY 
                CASE WHEN category = ? THEN 0 ELSE 1 END,
                quality_score DESC
            LIMIT ?
        """, (creator_pk, category, category, limit))
        
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
# CONFIG TOOLS (1)
# ============================================================

@mcp.tool()
def get_send_types(page_type: str = None) -> dict:
    """Returns the 22 send type taxonomy with constraints.
    
    MCP Name: mcp__eros-db__get_send_types
    
    Args:
        page_type: Optional filter ('paid' or 'free')
        
    Returns:
        List of send types with constraints
    """
    logger.info(f"get_send_types: page_type={page_type}")
    try:
        query = "SELECT * FROM send_types WHERE 1=1"
        params = []
        
        if page_type == 'free':
            query += " AND page_type IN ('both', 'free')"
        elif page_type == 'paid':
            query += " AND page_type IN ('both', 'paid')"
        
        query += " ORDER BY category, send_type_key"
        
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
```

## STEP 3.5: Create Package Init
```bash
cat > ./mcp_server/__init__.py << 'INIT'
"""EROS MCP Server Package.

Provides database access tools for the EROS Schedule Generator.
Server: eros-db
Tools: 14 total
"""
__version__ = "1.0.0"
__server_name__ = "eros-db"
INIT

echo "Created __init__.py"
```

## STEP 3.6: Verify Server Can Import
```bash
echo "=== Testing Server Import ==="
python -c "
import sys
sys.path.insert(0, '.')

try:
    from mcp_server.main import mcp, DB_PATH
    import os
    
    print(f'✓ Server Name: {mcp.name}')
    print(f'✓ DB Path: {DB_PATH}')
    print(f'✓ DB Exists: {os.path.exists(DB_PATH)}')
    print('')
    print('Import test: PASSED')
except Exception as e:
    print(f'✗ Import failed: {e}')
    sys.exit(1)
"
```

## OUTPUT REQUIREMENTS
- [ ] `.mcp.json` created at project root
- [ ] `./mcp_server/__init__.py` created
- [ ] `./mcp_server/main.py` created with all 14 tools
- [ ] Server imports successfully without errors
- [ ] Database path resolves correctly

## COMPLETION CONFIRMATION
State: "PHASE 3 COMPLETE: MCP server created with 14 tools. Server name: eros-db. Import test: PASSED."
```

---

## PHASE 4: SKILL.MD INTEGRATION
**Executor**: `llm-architect` (inherit)  
**Estimated Time**: 5-10 minutes  
**Dependencies**: Phase 3 complete  
**Outputs**: Updated `skills/eros-schedule-generator/SKILL.md`

### Task Description
Update SKILL.md with proper MCP tool namespacing and documentation.

### Detailed Instructions

```markdown
You are updating SKILL.md for MCP integration.

**MCP TOOL NAMING CONVENTION**: `mcp__eros-db__<tool-name>`

## STEP 4.1: Update SKILL.md Frontmatter
Update the frontmatter in `./skills/eros-schedule-generator/SKILL.md`:

```yaml
---
name: eros-schedule-generator
description: Generate optimized weekly schedules for OnlyFans creators. Invoke PROACTIVELY for schedule generation, PPV optimization, or content planning requests.
version: 5.2.0
allowed-tools: mcp__eros-db__get_creator_profile, mcp__eros-db__get_volume_config, mcp__eros-db__get_vault_availability, mcp__eros-db__get_content_type_rankings, mcp__eros-db__get_persona_profile, mcp__eros-db__get_active_volume_triggers, mcp__eros-db__get_performance_trends, mcp__eros-db__get_batch_captions_by_content_types, mcp__eros-db__get_send_type_captions, mcp__eros-db__save_schedule, mcp__eros-db__save_volume_triggers, mcp__eros-db__get_active_creators, mcp__eros-db__validate_caption_structure, mcp__eros-db__get_send_types
triggers:
  - generate schedule
  - weekly schedule
  - content plan
  - PPV optimization
  - schedule for [creator]
---
```

## STEP 4.2: Add MCP Server Documentation Section
Add this section after the Activation Protocol:

```markdown
---

## MCP Server: eros-db

This skill uses the `eros-db` MCP server for database access.

**Tool Naming**: All tools use format `mcp__eros-db__<tool-name>`

### Verify MCP Connection
Before using tools:
1. Run `/mcp status` 
2. Confirm `eros-db` shows as "connected"
3. If not connected, restart Claude Code session

### Available Tools (14 total)

| Tool | Category | Description | GATE |
|------|----------|-------------|------|
| `mcp__eros-db__get_creator_profile` | Creator | Profile with analytics | |
| `mcp__eros-db__get_active_creators` | Creator | List active creators | |
| `mcp__eros-db__get_vault_availability` | Creator | Content type availability | HARD |
| `mcp__eros-db__get_content_type_rankings` | Creator | Performance tiers | HARD |
| `mcp__eros-db__get_persona_profile` | Creator | Tone/archetype settings | |
| `mcp__eros-db__get_volume_config` | Schedule | Tier and daily volumes | |
| `mcp__eros-db__get_active_volume_triggers` | Schedule | Performance triggers | |
| `mcp__eros-db__get_performance_trends` | Schedule | Health/saturation metrics | |
| `mcp__eros-db__save_schedule` | Schedule | Persist with certificate | |
| `mcp__eros-db__save_volume_triggers` | Schedule | Persist triggers | |
| `mcp__eros-db__get_batch_captions_by_content_types` | Caption | Batch PPV retrieval | |
| `mcp__eros-db__get_send_type_captions` | Caption | Send-type specific | |
| `mcp__eros-db__validate_caption_structure` | Caption | Anti-patterization | |
| `mcp__eros-db__get_send_types` | Config | 22-type taxonomy | |

### Tool Usage by Phase

**Phase 1 - Preflight** (5 tools):
- `get_creator_profile` - Creator metadata
- `get_volume_config` - Volume tier configuration  
- `get_vault_availability` - HARD GATE data
- `get_content_type_rankings` - HARD GATE data
- `get_persona_profile` - Caption styling

**Phase 2 - Generate** (3 tools):
- `get_batch_captions_by_content_types` - PPV captions
- `get_send_type_captions` - Engagement captions
- `validate_caption_structure` - Quality check

**Phase 3 - Validate** (3 tools):
- `get_vault_availability` - Re-verify HARD GATE
- `get_content_type_rankings` - Re-verify HARD GATE
- `save_schedule` - Persist with certificate
```

## STEP 4.3: Update Existing Tool References
Search and replace old tool references throughout SKILL.md:
- `get_creator_profile` → `mcp__eros-db__get_creator_profile`
- etc.

## OUTPUT REQUIREMENTS
- [ ] Frontmatter updated with namespaced tools list
- [ ] Version bumped to 5.2.0
- [ ] MCP server documentation section added
- [ ] Existing tool references updated

## COMPLETION CONFIRMATION
State: "PHASE 4 COMPLETE: SKILL.md updated with MCP namespacing for all 14 tools. Version: 5.2.0"
```

---

## PHASE 5: SUBAGENT CONFIGURATION
**Executor**: `multi-agent-coordinator` (sonnet)  
**Estimated Time**: 5-10 minutes  
**Dependencies**: Phase 4 complete  
**Outputs**: Updated agent files in `./agents/` and `.claude/agents/`

### Task Description
Configure subagents for proper MCP tool inheritance.

### Detailed Instructions

```markdown
You are configuring subagents for MCP tool access.

**CRITICAL INHERITANCE RULE**: When the `tools` field is OMITTED from frontmatter, subagents inherit ALL MCP tools automatically.

## STEP 5.1: Update Generator Agent
Update `./agents/schedule-generator.md`:

```markdown
---
name: schedule-generator
description: Builds optimized weekly schedule items from CreatorContext. Executes Phase 2 of the EROS pipeline.
model: sonnet
skills: eros-schedule-generator
---

# Schedule Generator Agent

**Model**: Sonnet | **Phase**: 2 (Generate) | **Version**: 5.0.0

## MCP Tool Access

This agent inherits ALL MCP tools from the eros-db server.
(The `tools` field is intentionally omitted to enable full inheritance.)

### Primary Tools Used
- `mcp__eros-db__get_batch_captions_by_content_types` - Batch PPV caption retrieval
- `mcp__eros-db__get_send_type_captions` - Send-type specific captions
- `mcp__eros-db__validate_caption_structure` - Caption quality validation

[Rest of existing schedule-generator.md content...]
```

## STEP 5.2: Update Validator Agent
Update `./agents/schedule-validator.md`:

```markdown
---
name: schedule-validator
description: Independently verifies schedule against hard gates. Executes Phase 3 of the EROS pipeline.
model: opus
skills: eros-schedule-generator
---

# Schedule Validator Agent

**Model**: Opus | **Phase**: 3 (Validate) | **Version**: 5.0.0

## MCP Tool Access

This agent inherits ALL MCP tools from the eros-db server.
(The `tools` field is intentionally omitted to enable full inheritance.)

### Primary Tools Used
- `mcp__eros-db__get_vault_availability` - Re-verify vault compliance (HARD GATE)
- `mcp__eros-db__get_content_type_rankings` - Re-verify AVOID exclusion (HARD GATE)
- `mcp__eros-db__save_schedule` - Persist with ValidationCertificate

[Rest of existing schedule-validator.md content...]
```

## STEP 5.3: Ensure .claude/agents/ Directory and Copy
```bash
# Create directory if not exists
mkdir -p .claude/agents/

# Copy agent files
cp ./agents/schedule-generator.md .claude/agents/
cp ./agents/schedule-validator.md .claude/agents/

echo "Copied agents to .claude/agents/"
ls -la .claude/agents/
```

## OUTPUT REQUIREMENTS
- [ ] Generator agent updated (tools field omitted for inheritance)
- [ ] Validator agent updated (tools field omitted for inheritance)
- [ ] Both agents copied to `.claude/agents/`
- [ ] MCP tool documentation added to both

## COMPLETION CONFIRMATION
State: "PHASE 5 COMPLETE: 2 subagents configured for MCP tool inheritance at .claude/agents/"
```

---

## PHASE 6: PYTHON ADAPTER ALIGNMENT
**Executor**: `python-pro` (inherit)  
**Estimated Time**: 5-10 minutes  
**Dependencies**: Phase 5 complete  
**Outputs**: Updated `./python/adapters.py`, `./python/preflight.py`

### Task Description
Align Python adapter layer with MCP tool definitions.

### Detailed Instructions

```markdown
You are aligning the Python adapter with MCP tools.

## STEP 6.1: Update MCPClient Protocol in preflight.py
Ensure `./python/preflight.py` MCPClient Protocol includes ALL 14 methods:

```python
class MCPClient(Protocol):
    """Protocol for MCP client - matches eros-db server tools."""
    
    # Creator tools (5)
    async def get_creator_profile(self, creator_id: str) -> dict: ...
    async def get_active_creators(self, limit: int = 100, tier: str = None) -> list: ...
    async def get_vault_availability(self, creator_id: str) -> dict: ...
    async def get_content_type_rankings(self, creator_id: str) -> dict: ...
    async def get_persona_profile(self, creator_id: str) -> dict: ...
    
    # Schedule tools (5)
    async def get_volume_config(self, creator_id: str, week_start: str) -> dict: ...
    async def get_active_volume_triggers(self, creator_id: str) -> dict: ...
    async def get_performance_trends(self, creator_id: str, period: str) -> dict: ...
    async def save_schedule(self, creator_id: str, week_start: str, items: list, validation_certificate: dict = None) -> dict: ...
    async def save_volume_triggers(self, creator_id: str, triggers: list) -> dict: ...
    
    # Caption tools (3)
    async def get_batch_captions_by_content_types(self, creator_id: str, content_types: list, limit_per_type: int = 5) -> dict: ...
    async def get_send_type_captions(self, creator_id: str, send_type: str, limit: int = 10) -> list: ...
    async def validate_caption_structure(self, caption_text: str, send_type: str) -> dict: ...
    
    # Config tools (1)
    async def get_send_types(self, page_type: str = None) -> list: ...
```

## STEP 6.2: Update ProductionMCPClient in adapters.py
Add docstrings showing MCP tool name and ensure all 14 tools have wrappers:

```python
@with_retry()
async def get_creator_profile(self, creator_id: str, include_analytics: bool = False) -> dict:
    """MCP: mcp__eros-db__get_creator_profile"""
    return await self._call("get_creator_profile", creator_id=creator_id, include_analytics=include_analytics)

@with_retry()
async def get_active_creators(self, limit: int = 100, tier: str = None) -> dict:
    """MCP: mcp__eros-db__get_active_creators"""
    return await self._call("get_active_creators", limit=limit, tier=tier)

# ... add similar for all 14 tools ...

@with_retry()
async def get_send_types(self, page_type: str = None) -> dict:
    """MCP: mcp__eros-db__get_send_types"""
    return await self._call("get_send_types", page_type=page_type)
```

## STEP 6.3: Verify All Methods Present
```bash
echo "=== Checking Protocol and Adapter Methods ==="
grep -E "async def (get_|save_|validate_)" ./python/preflight.py | wc -l
grep -E "async def (get_|save_|validate_)" ./python/adapters.py | wc -l
echo "Expected: 14 methods in each file"
```

## OUTPUT REQUIREMENTS
- [ ] MCPClient Protocol updated with all 14 method signatures
- [ ] ProductionMCPClient has all 14 tool wrappers
- [ ] MCP naming documented in docstrings
- [ ] Method signatures match MCP tool parameters

## COMPLETION CONFIRMATION
State: "PHASE 6 COMPLETE: Python adapters aligned with 14 MCP tools."
```

---

## PHASE 7: VALIDATION & TESTING
**Executor**: `sre-engineer` (sonnet)  
**Estimated Time**: 10-15 minutes  
**Dependencies**: Phase 6 complete  
**Outputs**: `./mcp-validation-report.md`

### Task Description
Validate the complete MCP infrastructure with comprehensive tests.

### Detailed Instructions

```markdown
You are validating the complete MCP infrastructure.

## STEP 7.1: File Structure Verification
```bash
echo "=== File Structure Check ==="
MISSING=0

for f in .mcp.json ./data/eros_sd_main.db ./mcp_server/__init__.py ./mcp_server/main.py ./skills/eros-schedule-generator/SKILL.md .claude/agents/schedule-generator.md .claude/agents/schedule-validator.md; do
    if [ -f "$f" ]; then
        echo "✓ $f"
    else
        echo "✗ MISSING: $f"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
if [ $MISSING -eq 0 ]; then
    echo "Structure check: PASSED"
else
    echo "Structure check: FAILED ($MISSING files missing)"
fi
```

## STEP 7.2: MCP Server Import Test
```bash
echo ""
echo "=== MCP Server Import Test ==="
python << 'PYTEST'
import sys
sys.path.insert(0, '.')

try:
    from mcp_server.main import mcp, DB_PATH, get_db_connection
    import os
    
    print(f"Server name: {mcp.name}")
    print(f"DB path: {DB_PATH}")
    print(f"DB exists: {os.path.exists(DB_PATH)}")
    
    # Test connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM creators")
        count = cursor.fetchone()[0]
        print(f"Creators count: {count}")
    
    print("")
    print("Import test: PASSED")
    
except Exception as e:
    print(f"Import test: FAILED - {e}")
    sys.exit(1)
PYTEST
```

## STEP 7.3: Database Connectivity Test
```bash
echo ""
echo "=== Database Tool Test ==="
python << 'PYTEST'
import sys
sys.path.insert(0, '.')

from mcp_server.main import get_creator_profile, get_active_creators, get_send_types

# Test get_active_creators
result = get_active_creators(limit=5)
if "error" not in result:
    print(f"✓ get_active_creators: {result.get('count', 0)} creators")
else:
    print(f"✗ get_active_creators: {result['error']}")

# Test get_send_types
result = get_send_types()
if "error" not in result:
    print(f"✓ get_send_types: {result.get('total', 0)} types")
else:
    print(f"✗ get_send_types: {result['error']}")

# Test validate_caption_structure (doesn't need DB)
from mcp_server.main import validate_caption_structure
result = validate_caption_structure("Hey baby, check out my new content! 💕", "ppv_unlock")
print(f"✓ validate_caption_structure: score={result.get('score', 0)}")

print("")
print("Database tool test: PASSED")
PYTEST
```

## STEP 7.4: MCP Config Validation
```bash
echo ""
echo "=== MCP Config Validation ==="
python << 'PYTEST'
import json
import sys

try:
    with open('.mcp.json') as f:
        config = json.load(f)
    
    server = config.get('mcpServers', {}).get('eros-db', {})
    
    print(f"Server name: eros-db")
    print(f"Transport: {server.get('type', 'NOT SET')}")
    print(f"Command: {server.get('command', 'NOT SET')}")
    print(f"Args: {server.get('args', [])}")
    print(f"Timeout: {server.get('timeout', 'NOT SET')}ms")
    
    # Validate required fields
    errors = []
    if server.get('type') != 'stdio':
        errors.append("Transport should be 'stdio'")
    if not server.get('command'):
        errors.append("Command not specified")
    if not server.get('args'):
        errors.append("Args not specified")
    
    if errors:
        print(f"\nConfig issues: {', '.join(errors)}")
    else:
        print("\nConfig validation: PASSED")
        
except Exception as e:
    print(f"Config validation: FAILED - {e}")
    sys.exit(1)
PYTEST
```

## STEP 7.5: Tool Count Verification
```bash
echo ""
echo "=== Tool Count Verification ==="
python << 'PYTEST'
import sys
sys.path.insert(0, '.')

# Count @mcp.tool() decorated functions
import ast

with open('./mcp_server/main.py', 'r') as f:
    source = f.read()

# Count occurrences of @mcp.tool()
tool_count = source.count('@mcp.tool()')
print(f"Tools defined: {tool_count}")

if tool_count == 14:
    print("Tool count: PASSED (14 tools)")
else:
    print(f"Tool count: WARNING (expected 14, found {tool_count})")
PYTEST
```

## STEP 7.6: Generate Validation Report
```bash
cat > ./mcp-validation-report.md << 'REPORT'
# MCP Validation Report

**Date**: $(date -Iseconds)
**Skill Package**: eros-schedule-generator
**MCP Server**: eros-db

## Summary

| Check | Status | Details |
|-------|--------|---------|
| File Structure | | |
| Server Import | | |
| Database Connectivity | | |
| MCP Config | | |
| Tool Count | | |

## Test Results

### File Structure
[Results from Step 7.1]

### Server Import
[Results from Step 7.2]

### Database Tools
[Results from Step 7.3]

### Config Validation
[Results from Step 7.4]

### Tool Count
[Results from Step 7.5]

## Tools Verified (14)

| # | Tool | Category | Test Status |
|---|------|----------|-------------|
| 1 | get_creator_profile | Creator | |
| 2 | get_active_creators | Creator | |
| 3 | get_vault_availability | Creator | |
| 4 | get_content_type_rankings | Creator | |
| 5 | get_persona_profile | Creator | |
| 6 | get_volume_config | Schedule | |
| 7 | get_active_volume_triggers | Schedule | |
| 8 | get_performance_trends | Schedule | |
| 9 | save_schedule | Schedule | |
| 10 | save_volume_triggers | Schedule | |
| 11 | get_batch_captions_by_content_types | Caption | |
| 12 | get_send_type_captions | Caption | |
| 13 | validate_caption_structure | Caption | |
| 14 | get_send_types | Config | |

## Issues Found

[List any issues discovered]

## Ready for Production

[ ] Yes - All checks passed
[ ] No - Issues need resolution

---
*Validation completed by Phase 7 - sre-engineer*
REPORT

echo ""
echo "Validation report created: ./mcp-validation-report.md"
```

## OUTPUT REQUIREMENTS
- [ ] All structure checks pass
- [ ] Server imports successfully
- [ ] Database tools execute correctly
- [ ] Config validates correctly
- [ ] All 14 tools present
- [ ] Validation report created

## COMPLETION CONFIRMATION
State: "PHASE 7 COMPLETE: MCP validation passed. All 14 tools verified. Report at ./mcp-validation-report.md"
```

---

## PHASE 8: DOCUMENTATION & CLEANUP
**Executor**: `documentation-engineer` (sonnet)  
**Estimated Time**: 5-10 minutes  
**Dependencies**: Phase 7 complete  
**Outputs**: `./docs/MCP_SETUP_GUIDE.md`, updated README.md, cleaned artifacts

### Task Description
Create final documentation and clean up setup artifacts.

### Detailed Instructions

```markdown
You are creating final documentation and performing cleanup.

## STEP 8.1: Create MCP Setup Guide
Create `./docs/MCP_SETUP_GUIDE.md`:

```markdown
# EROS MCP Setup Guide

**Version**: 1.0.0
**Last Updated**: [DATE]
**Server**: eros-db

## Overview

The EROS Schedule Generator uses an MCP server (`eros-db`) to access the SQLite database containing creator profiles, captions, and scheduling data.

## Prerequisites

- Python 3.10+
- MCP SDK: `pip install mcp`
- Database: `./data/eros_sd_main.db`

## Configuration Files

| File | Purpose |
|------|---------|
| `.mcp.json` | MCP server configuration |
| `./mcp_server/main.py` | Server implementation |
| `./data/eros_sd_main.db` | SQLite database |

## Verifying Setup

### 1. Check MCP Status
```
/mcp status
```
Should show `eros-db` as connected.

### 2. List Available Tools
```
/mcp tools eros-db
```
Should list all 14 tools.

### 3. Test Tool Call
```
/mcp call eros-db get_active_creators --limit 5
```

## Troubleshooting

### Server Not Connecting

1. Verify database exists:
   ```bash
   ls -la ./data/eros_sd_main.db
   ```

2. Test server import:
   ```bash
   python -c "from mcp_server.main import mcp; print(mcp.name)"
   ```

3. Check MCP SDK installed:
   ```bash
   pip show mcp
   ```

4. Restart Claude Code session

### Database Errors

1. Check integrity:
   ```bash
   sqlite3 ./data/eros_sd_main.db "PRAGMA integrity_check;"
   ```

2. Verify permissions:
   ```bash
   ls -la ./data/
   ```

## Available Tools

### Creator Tools (5)
- `get_creator_profile` - Profile with analytics
- `get_active_creators` - List active creators
- `get_vault_availability` - HARD GATE data
- `get_content_type_rankings` - HARD GATE data
- `get_persona_profile` - Tone/archetype

### Schedule Tools (5)
- `get_volume_config` - Volume tier config
- `get_active_volume_triggers` - Performance triggers
- `get_performance_trends` - Health metrics
- `save_schedule` - Persist schedule
- `save_volume_triggers` - Persist triggers

### Caption Tools (3)
- `get_batch_captions_by_content_types` - Batch retrieval
- `get_send_type_captions` - By send type
- `validate_caption_structure` - Quality check

### Config Tools (1)
- `get_send_types` - 22-type taxonomy

---
*EROS Schedule Generator MCP Documentation*
```

## STEP 8.2: Update README.md
Add MCP section to README.md:

```markdown
## MCP Server

The skill uses an MCP server (`eros-db`) for database access.

### Quick Start
1. Ensure database at `./data/eros_sd_main.db`
2. Restart Claude Code
3. Verify: `/mcp status`

### Available Tools
14 tools across 4 categories (Creator, Schedule, Caption, Config).

See `docs/MCP_SETUP_GUIDE.md` for details.
```

## STEP 8.3: Update .gitignore
Ensure comprehensive .gitignore:

```bash
cat >> .gitignore << 'GITIGNORE'

# MCP Setup Artifacts
mcp-audit-report.md
mcp-validation-report.md
data/schema-*.txt
data/schema-*.sql
data/record-counts.txt

# MCP Server
mcp_server/__pycache__/
mcp_server/*.pyc

# Archives
archived/

# Claude Code local settings
.claude/settings.local.json
GITIGNORE

echo "Updated .gitignore"
```

## STEP 8.4: Archive Setup Artifacts
```bash
SETUP_ARCHIVE="./archived/setup-$(date +%Y%m%d)"
mkdir -p "$SETUP_ARCHIVE"

# Move (not copy) setup artifacts
mv ./mcp-audit-report.md "$SETUP_ARCHIVE/" 2>/dev/null || true
mv ./mcp-validation-report.md "$SETUP_ARCHIVE/" 2>/dev/null || true
mv ./data/schema-tables.txt "$SETUP_ARCHIVE/" 2>/dev/null || true
mv ./data/schema-full.sql "$SETUP_ARCHIVE/" 2>/dev/null || true
mv ./data/record-counts.txt "$SETUP_ARCHIVE/" 2>/dev/null || true

echo "Archived setup artifacts to $SETUP_ARCHIVE/"
ls -la "$SETUP_ARCHIVE/"
```

## STEP 8.5: Final Summary
```bash
echo ""
echo "=============================================="
echo "EROS MCP INFRASTRUCTURE SETUP COMPLETE"
echo "=============================================="
echo ""
echo "Files Created:"
echo "  ✓ .mcp.json"
echo "  ✓ ./mcp_server/main.py (14 tools)"
echo "  ✓ ./data/eros_sd_main.db"
echo "  ✓ ./data/db-config.json"
echo "  ✓ ./docs/MCP_SETUP_GUIDE.md"
echo "  ✓ .claude/agents/schedule-generator.md"
echo "  ✓ .claude/agents/schedule-validator.md"
echo ""
echo "Files Modified:"
echo "  ✓ ./skills/eros-schedule-generator/SKILL.md (v5.2.0)"
echo "  ✓ ./python/adapters.py"
echo "  ✓ ./python/preflight.py"
echo "  ✓ README.md"
echo "  ✓ .gitignore"
echo ""
echo "NEXT STEPS:"
echo "  1. RESTART CLAUDE CODE (required)"
echo "  2. Run: /mcp status"
echo "  3. Verify: eros-db shows 'connected'"
echo "  4. Test: generate schedule for [creator] [date]"
echo ""
echo "=============================================="
```

## OUTPUT REQUIREMENTS
- [ ] MCP Setup Guide created at `./docs/MCP_SETUP_GUIDE.md`
- [ ] README.md updated with MCP section
- [ ] .gitignore updated
- [ ] Setup artifacts archived
- [ ] Final summary displayed

## COMPLETION CONFIRMATION
State: "PHASE 8 COMPLETE: Documentation finalized. EROS MCP infrastructure setup complete! Restart Claude Code to activate."
```

---

## POST-EXECUTION CHECKLIST

After ALL phases complete successfully:

### 1. ⚡ RESTART CLAUDE CODE (REQUIRED)
Close and reopen Claude Code to activate MCP configuration.

### 2. Verify MCP Status
```
/mcp status
```
**Expected**: `eros-db` listed as "connected"

### 3. Test Tool Listing
```
/mcp tools eros-db
```
**Expected**: All 14 tools listed

### 4. Functional Test
```
generate schedule for grace_bennett 2026-01-13
```
**Expected**: Schedule generated using MCP tools

### 5. If Issues Occur

**MCP not connecting:**
1. Check `.mcp.json` exists and is valid JSON
2. Verify `./data/eros_sd_main.db` exists
3. Run `pip install mcp --upgrade`
4. Check Python version >= 3.10
5. Restart Claude Code again

**Database errors:**
1. Run integrity check: `sqlite3 ./data/eros_sd_main.db "PRAGMA integrity_check;"`
2. Check file permissions: `ls -la ./data/`
3. Verify table names match server expectations

**Tool errors:**
1. Test import: `python -c "from mcp_server.main import mcp; print(mcp.name)"`
2. Check server logs in stderr
3. Review `./docs/MCP_SETUP_GUIDE.md` troubleshooting section

---

## QUICK REFERENCE

### Files Created
| File | Purpose |
|------|---------|
| `.mcp.json` | MCP server configuration |
| `./mcp_server/main.py` | Server + all 14 tools |
| `./data/eros_sd_main.db` | SQLite database |
| `./data/db-config.json` | Database configuration |
| `./docs/MCP_SETUP_GUIDE.md` | Setup documentation |
| `.claude/agents/*.md` | Subagent definitions |

### MCP Tools (14 total)
| # | Tool | Category |
|---|------|----------|
| 1 | `get_creator_profile` | Creator |
| 2 | `get_active_creators` | Creator |
| 3 | `get_vault_availability` | Creator (GATE) |
| 4 | `get_content_type_rankings` | Creator (GATE) |
| 5 | `get_persona_profile` | Creator |
| 6 | `get_volume_config` | Schedule |
| 7 | `get_active_volume_triggers` | Schedule |
| 8 | `get_performance_trends` | Schedule |
| 9 | `save_schedule` | Schedule |
| 10 | `save_volume_triggers` | Schedule |
| 11 | `get_batch_captions_by_content_types` | Caption |
| 12 | `get_send_type_captions` | Caption |
| 13 | `validate_caption_structure` | Caption |
| 14 | `get_send_types` | Config |

### Subagent Model Assignment
| Agent | Model | Phase |
|-------|-------|-------|
| schedule-generator | Sonnet | 2 |
| schedule-validator | Opus | 3 |

---

*Generated for EROS Schedule Generator MCP Infrastructure*  
*Claude Code v2.0.76+ | MCP Specification 2025-11-25*  
*Prompt Version: 3.0.0 (FINAL)*
