# MCP Refactor Backpressure System

## What is Backpressure?

Backpressure is the automatic rejection mechanism that prevents Ralph loops from exiting prematurely. Each phase has validation gates that must ALL pass before the loop can output its completion promise.

**Key Principle:** Tests, linters, and validation scripts create automatic rejection of wrong outputs. If they fail, Claude knows to fix them in the next iteration.

---

## Phase 1: Review Backpressure

### Validator: verify_review.py

```python
#!/usr/bin/env python3
"""
Phase 1 backpressure validator.
Run after review.md generation to verify quality gates.
"""

from pathlib import Path
import re
import sys

def verify_review(tool_name: str) -> tuple[bool, list[str]]:
    errors = []
    review_path = f"mcp_refactoring_workspace/{tool_name}/review.md"

    # Gate 1: File exists
    if not Path(review_path).exists():
        errors.append("GATE_FAIL: review.md not created")
        return False, errors

    content = Path(review_path).read_text()

    # Gate 2: No placeholder text
    placeholders = ["[TBD]", "[TODO]", "[PLACEHOLDER]", "[FILL IN]"]
    for ph in placeholders:
        if ph in content:
            errors.append(f"GATE_FAIL: Placeholder found: {ph}")

    # Gate 3: Required sections present
    required_sections = [
        "## Quick Reference",
        "## 1. Current Implementation",
        "## 2. Database Layer",
        "## 3. Pipeline Position",
        "## 4. Issues",
        "## 5. Refactoring Plan",
        "## 6. Interview Questions"
    ]
    for section in required_sections:
        if section not in content:
            errors.append(f"GATE_FAIL: Missing section: {section}")

    # Gate 4: Line numbers filled in
    line_patterns = [
        r"Lines\s*\|\s*\[",      # "Lines | ["
        r"lines\s+\[START",      # "lines [START"
        r":\s*\[LINE\]",         # ": [LINE]"
    ]
    for pattern in line_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            errors.append("GATE_FAIL: Line number placeholders found")
            break

    # Gate 5: Schema verification present
    if "Column Verification" not in content and "Schema" not in content:
        errors.append("GATE_WARN: No schema verification section found")

    # Gate 6: Issues section has content
    issues_section = re.search(r"## 4\. Issues(.*?)(?=## 5|$)", content, re.DOTALL)
    if issues_section:
        issues_content = issues_section.group(1)
        if len(issues_content.strip()) < 50:
            errors.append("GATE_WARN: Issues section appears empty")

    # Gate 7: Interview questions present
    interview_section = re.search(r"## 6\. Interview Questions(.*?)$", content, re.DOTALL)
    if interview_section:
        if "Decisions Required" not in interview_section.group(1):
            errors.append("GATE_WARN: No decisions required in interview section")

    return len([e for e in errors if "GATE_FAIL" in e]) == 0, errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_review.py <tool_name>")
        sys.exit(1)

    tool_name = sys.argv[1]
    passed, errors = verify_review(tool_name)

    print(f"=== Review Verification: {tool_name} ===")
    if passed:
        print("RESULT: PASS")
        for e in errors:
            if "WARN" in e:
                print(f"  {e}")
        sys.exit(0)
    else:
        print("RESULT: FAIL")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
```

### Gate Summary

| Gate | Check | Failure Action |
|------|-------|----------------|
| 1 | File exists | Loop must create file |
| 2 | No placeholders | Loop must fill all fields |
| 3 | All sections | Loop must add missing sections |
| 4 | Line numbers | Loop must verify via Read |
| 5 | Schema verification | Loop must add PRAGMA check |
| 6 | Issues content | Loop must document findings |
| 7 | Interview questions | Loop must identify decisions |

---

## Phase 2: Spec Backpressure

### Validator: verify_spec.py

```python
#!/usr/bin/env python3
"""
Phase 2 backpressure validator.
Run after spec generation to verify quality gates.
"""

from pathlib import Path
import re
import sys

def verify_spec(tool_name: str) -> tuple[bool, list[str]]:
    errors = []
    spec_path = f"mcp_refactoring_workspace/{tool_name}/{tool_name}.md"

    # Gate 1: File exists
    if not Path(spec_path).exists():
        errors.append("GATE_FAIL: Spec file not created")
        return False, errors

    content = Path(spec_path).read_text()

    # Gate 2: All phases have complete structure
    phases = re.findall(r'### Phase (\d+):', content)
    for phase_num in phases:
        phase_pattern = rf'### Phase {phase_num}:(.*?)(?=### Phase \d+:|## \d+\.|$)'
        phase_match = re.search(phase_pattern, content, re.DOTALL)
        if phase_match:
            phase_content = phase_match.group(1)
            required = ["**Before:**", "**After:**", "**Verification:**", "**Commit:**"]
            for req in required:
                if req not in phase_content:
                    errors.append(f"GATE_FAIL: Phase {phase_num} missing {req}")

    # Gate 3: No vague language
    vague_phrases = [
        "as needed", "if appropriate", "when necessary",
        "as applicable", "where relevant", "[TBD]", "[TODO]"
    ]
    for phrase in vague_phrases:
        if phrase.lower() in content.lower():
            errors.append(f"GATE_FAIL: Vague phrase: '{phrase}'")

    # Gate 4: Code blocks are valid Python
    code_blocks = re.findall(r'```python\n(.*?)```', content, re.DOTALL)
    for i, block in enumerate(code_blocks):
        block = block.strip()
        if not block:
            continue
        # Skip blocks that are templates/examples with [placeholders]
        if '[' in block and ']' in block:
            continue
        try:
            compile(block, f'<block_{i}>', 'exec')
        except SyntaxError as e:
            errors.append(f"GATE_FAIL: Invalid Python in block {i}: {e.msg}")

    # Gate 5: Required sections present
    required_sections = [
        "## 1. Objectives",
        "## 2. Current Implementation",
        "## 3. Target Implementation",
        "## 4. Implementation Phases"
    ]
    for section in required_sections:
        if section not in content:
            errors.append(f"GATE_FAIL: Missing section: {section}")

    # Gate 6: Has at least one implementation phase
    if not phases:
        errors.append("GATE_FAIL: No implementation phases found")

    return len([e for e in errors if "GATE_FAIL" in e]) == 0, errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_spec.py <tool_name>")
        sys.exit(1)

    tool_name = sys.argv[1]
    passed, errors = verify_spec(tool_name)

    print(f"=== Spec Verification: {tool_name} ===")
    if passed:
        print("RESULT: PASS")
        sys.exit(0)
    else:
        print("RESULT: FAIL")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
```

### Gate Summary

| Gate | Check | Failure Action |
|------|-------|----------------|
| 1 | File exists | Loop must create file |
| 2 | Phase structure | Loop must add Before/After/Verify/Commit |
| 3 | No vague language | Loop must be specific |
| 4 | Valid Python | Loop must fix syntax errors |
| 5 | Required sections | Loop must add missing sections |
| 6 | Has phases | Loop must define implementation |

---

## Phase 3: Execution Backpressure

### Validator: verify_phase.py

```python
#!/usr/bin/env python3
"""
Phase 3 backpressure validator.
Run after each implementation phase to verify gates.
"""

import subprocess
import sys

def verify_phase(tool_name: str, phase_num: int) -> tuple[bool, list[str]]:
    errors = []

    # Gate 1: Tests pass
    result = subprocess.run(
        ["pytest", "python/tests/", "-q", "--tb=no"],
        capture_output=True, text=True,
        timeout=120
    )
    if result.returncode != 0:
        # Extract just the summary line
        lines = result.stdout.strip().split('\n')
        summary = lines[-1] if lines else "Unknown failure"
        errors.append(f"GATE_FAIL: Tests failed: {summary}")

    # Gate 2: Working tree clean
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True
    )
    if status.stdout.strip():
        uncommitted = status.stdout.strip().split('\n')[:3]
        errors.append(f"GATE_FAIL: Uncommitted files: {uncommitted}")

    # Gate 3: Recent commit exists for this tool
    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        capture_output=True, text=True
    )
    commit_msg = log.stdout.strip().lower()
    if tool_name.lower().replace('_', '') not in commit_msg.replace('_', ''):
        errors.append(f"GATE_WARN: Commit may not be for {tool_name}: '{commit_msg}'")

    # Gate 4: No merge conflicts
    conflict_check = subprocess.run(
        ["git", "diff", "--check"],
        capture_output=True, text=True
    )
    if "conflict" in conflict_check.stdout.lower():
        errors.append("GATE_FAIL: Merge conflicts detected")

    return len([e for e in errors if "GATE_FAIL" in e]) == 0, errors

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: verify_phase.py <tool_name> <phase_num>")
        sys.exit(1)

    tool_name = sys.argv[1]
    phase_num = int(sys.argv[2])
    passed, errors = verify_phase(tool_name, phase_num)

    print(f"=== Phase {phase_num} Verification: {tool_name} ===")
    if passed:
        print("RESULT: PASS")
        for e in errors:
            if "WARN" in e:
                print(f"  {e}")
        sys.exit(0)
    else:
        print("RESULT: FAIL")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
```

### Gate Summary

| Gate | Check | Failure Action |
|------|-------|----------------|
| 1 | pytest passes | Loop must fix code or update tests |
| 2 | Tree clean | Loop must commit or revert |
| 3 | Commit exists | Loop must create commit |
| 4 | No conflicts | Loop must resolve conflicts |

---

## Backpressure Flow Diagram

```
LOOP ITERATION N
       │
       ▼
┌──────────────┐
│   Execute    │
│    Task      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Write     │
│   Output     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Run       │
│  Validator   │
└──────┬───────┘
       │
   ┌───┴───┐
   │       │
  FAIL   PASS
   │       │
   │       ▼
   │  ┌──────────────┐
   │  │   Output     │
   │  │  <promise>   │
   │  │   DONE       │
   │  └──────────────┘
   │
   ▼
┌──────────────┐
│   Review     │
│   Errors     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Fix       │
│   Issues     │
└──────┬───────┘
       │
       ▼
  ITERATION N+1
```

---

## Integration with Ralph Loops

### Prompt Pattern

Include backpressure in every loop prompt:

```bash
/ralph-loop "...

## Backpressure
After completing task, run validator:
python verify_[phase].py $TOOL_NAME [phase_num]

If RESULT: FAIL:
- Read error messages
- Fix issues
- Do NOT output completion promise
- Continue to next iteration

If RESULT: PASS:
- Output: <promise>[PHASE]_DONE</promise>
- Loop will exit

..." --max-iterations N --completion-promise "[PHASE]_DONE"
```

### Failure Modes

| Failure Type | Loop Behavior |
|--------------|---------------|
| Soft fail (WARN) | Continue, may exit |
| Hard fail (FAIL) | Must fix, cannot exit |
| Repeated fail (>5) | Consider /cancel-ralph |
| Stuck (no progress) | Add more signs, restart |
