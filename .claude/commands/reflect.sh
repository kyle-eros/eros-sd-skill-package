#!/bin/bash
# EROS Reflect Command - Analyze session and update learnings

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEARNINGS_PATH="${SCRIPT_DIR}/../LEARNINGS.md"
SKILL_PATH="${SCRIPT_DIR}/../skills/eros-generator/SKILL.md"
CONFIG_FILE="${HOME}/.eros_reflect_config"

case "$1" in
    on)
        echo "AUTO_REFLECT=true" > "$CONFIG_FILE"
        echo "Automatic reflection enabled"
        ;;
    off)
        echo "AUTO_REFLECT=false" > "$CONFIG_FILE"
        echo "Automatic reflection disabled"
        ;;
    status)
        if grep -q "AUTO_REFLECT=true" "$CONFIG_FILE" 2>/dev/null; then
            echo "Automatic reflection: ENABLED"
        else
            echo "Automatic reflection: DISABLED"
        fi
        echo "Learnings file: $LEARNINGS_PATH"
        echo "Skill file: $SKILL_PATH"
        echo "Config file: $CONFIG_FILE"
        ;;
    history)
        echo "Last 10 commits touching LEARNINGS.md or SKILL.md:"
        git log --oneline -10 -- "$LEARNINGS_PATH" "$SKILL_PATH" 2>/dev/null || echo "No commits found or not in a git repository"
        ;;
    *)
        echo "Usage: reflect.sh {on|off|status|history}"
        echo ""
        echo "Commands:"
        echo "  on      - Enable automatic reflection"
        echo "  off     - Disable automatic reflection"
        echo "  status  - Show current reflection settings"
        echo "  history - Show last 10 commits touching learnings files"
        ;;
esac
