#!/bin/bash
# ralph_skill_edit.sh — Quick launcher for skill package editing loops
# Location: .claude/skills/skill-editor/

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  RALPH SKILL EDITOR${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

print_usage() {
    cat << 'EOF'
Usage: ralph_skill_edit.sh <command> [options]

Commands:
  add       Add a new section to a skill file
  edit      Edit an existing section
  refactor  Refactor/restructure content
  delete    Remove a section (with reference cleanup)

Options:
  -f, --file FILE         Target file to modify (required)
  -s, --section NAME      Section name (required)
  -d, --desc DESCRIPTION  Brief description of change
  -r, --related FILES     Comma-separated related files
  -p, --pattern FILE      Reference pattern to follow
  -i, --iterations N      Max iterations (default: 12)

Examples:
  # Add a new phase to EROS workflow
  ./ralph_skill_edit.sh add -f .claude/skills/eros-schedule-generator/SKILL.md -s "Phase 4: Validation" -d "Add validation phase"

  # Edit existing EROS prompt
  ./ralph_skill_edit.sh edit -f .claude/skills/eros-schedule-validator/REFERENCE/validation.md -s "Hard Gates" -d "Add new gate documentation"

  # Refactor section across EROS skills
  ./ralph_skill_edit.sh refactor -f .claude/skills/eros-schedule-generator/SKILL.md -s "MCP Tools" -r ".claude/skills/eros-schedule-validator/SKILL.md" -d "Update tool references"

  # Delete obsolete section
  ./ralph_skill_edit.sh delete -f .claude/skills/mcp-refactor/SKILL.md -s "Deprecated Pattern" -d "Remove unused pattern"
EOF
}

# Parse arguments
EDIT_TYPE=""
TARGET_FILE=""
SECTION_NAME=""
DESCRIPTION=""
RELATED_FILES=""
REFERENCE_PATTERN=""
MAX_ITERATIONS=12

while [[ $# -gt 0 ]]; do
    case $1 in
        add|edit|refactor|delete)
            EDIT_TYPE="$1"
            shift
            ;;
        -f|--file)
            TARGET_FILE="$2"
            shift 2
            ;;
        -s|--section)
            SECTION_NAME="$2"
            shift 2
            ;;
        -d|--desc)
            DESCRIPTION="$2"
            shift 2
            ;;
        -r|--related)
            RELATED_FILES="$2"
            shift 2
            ;;
        -p|--pattern)
            REFERENCE_PATTERN="$2"
            shift 2
            ;;
        -i|--iterations)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$EDIT_TYPE" ]]; then
    echo -e "${RED}Error: Command required (add|edit|refactor|delete)${NC}"
    print_usage
    exit 1
fi

if [[ -z "$TARGET_FILE" ]]; then
    echo -e "${RED}Error: Target file required (-f)${NC}"
    print_usage
    exit 1
fi

if [[ -z "$SECTION_NAME" ]]; then
    echo -e "${RED}Error: Section name required (-s)${NC}"
    print_usage
    exit 1
fi

if [[ -z "$DESCRIPTION" ]]; then
    DESCRIPTION="$EDIT_TYPE $SECTION_NAME in $TARGET_FILE"
fi

# Export for prompt
export EDIT_TYPE
export TARGET_FILE
export SECTION_NAME
export DESCRIPTION
export RELATED_FILES
export REFERENCE_PATTERN

# Get script directory - updated for .claude/skills/skill-editor/ location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/PROMPT_skill_edit.md"

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo -e "${RED}Error: Prompt file not found: $PROMPT_FILE${NC}"
    exit 1
fi

# Detect EROS skill editing
EROS_MODE=false
[[ "$TARGET_FILE" == *"eros-"* ]] && {
    EROS_MODE=true
}

# Build the prompt with substitutions
build_prompt() {
    cat "$PROMPT_FILE" | \
        sed "s|\$EDIT_TYPE|$EDIT_TYPE|g" | \
        sed "s|\$TARGET_FILE|$TARGET_FILE|g" | \
        sed "s|\$SECTION_NAME|$SECTION_NAME|g" | \
        sed "s|\$DESCRIPTION|$DESCRIPTION|g" | \
        sed "s|\$RELATED_FILES|$RELATED_FILES|g" | \
        sed "s|\$REFERENCE_PATTERN|$REFERENCE_PATTERN|g"
}

# Print summary
print_header
echo ""
echo -e "${YELLOW}Operation:${NC} $EDIT_TYPE"
echo -e "${YELLOW}Target:${NC} $TARGET_FILE"
echo -e "${YELLOW}Section:${NC} $SECTION_NAME"
echo -e "${YELLOW}Description:${NC} $DESCRIPTION"
[[ -n "$RELATED_FILES" ]] && echo -e "${YELLOW}Related:${NC} $RELATED_FILES"
[[ -n "$REFERENCE_PATTERN" ]] && echo -e "${YELLOW}Pattern:${NC} $REFERENCE_PATTERN"
echo -e "${YELLOW}Max Iterations:${NC} $MAX_ITERATIONS"

# EROS mode detection and pre-flight
if [[ "$EROS_MODE" == "true" ]]; then
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  EROS MODE ACTIVE${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Domain constraints will be enforced:${NC}"
    echo -e "  • 5 Hard Gates (Vault, AVOID, Page Type, Diversity, Flyer)"
    echo -e "  • 16 must-keep MCP tools"
    echo -e "  • ValidationCertificate v3.0 schema"
    echo -e "  • CreatorContext 10-field schema"
    echo -e "  • Pricing bounds (\$5-\$50)"
    echo ""
    echo -e "${CYAN}Pre-flight: Checking LEARNINGS.md HIGH confidence...${NC}"
    if [[ -f "LEARNINGS.md" ]]; then
        grep -A5 "## HIGH Confidence" LEARNINGS.md 2>/dev/null | head -15 || echo "  (No HIGH section found)"
    else
        echo -e "  ${YELLOW}⚠️ LEARNINGS.md not found - verify domain constraints manually${NC}"
    fi
    echo ""
fi

echo -e "${GREEN}Starting Ralph loop...${NC}"
echo ""

# Run the Ralph loop
/ralph-loop "$(build_prompt)" \
    --max-iterations "$MAX_ITERATIONS" \
    --completion-promise "SKILL_EDIT_COMPLETE"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  RALPH SKILL EDITOR FINISHED${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
