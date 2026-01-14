# Ralph Wiggum Method - Simplified Guide

## What Is It?

Ralph Wiggum is a technique that keeps Claude Code running in a loop until a task is **actually done**—not just when Claude *thinks* it's done.

**The basic idea:** Instead of expecting Claude to get it right the first time, you let it try, fail, see what broke, and try again automatically. Over and over until it works.

Named after the Simpsons character who's confused and makes mistakes, but keeps going until something works.

---

## Why Does It Work?

**Traditional approach:** Tell Claude exactly what to do → Hope it works → Fix it manually if it doesn't

**Ralph approach:** Define what "done" looks like → Let Claude loop until it gets there → Failures teach it what to fix

The key insight: **Predictable failures are better than unpredictable successes.** When Claude fails in a loop, it sees what broke and fixes it next round.

---

## How It Works (Simple Version)

1. You give Claude a task with **clear success criteria**
2. Claude works on it
3. When Claude tries to exit, the loop catches it
4. Loop checks: "Did you actually finish?"
5. If no → Feed Claude the same prompt again (it can see what it built last time)
6. Repeat until done or max iterations reached

**Each round, Claude sees its previous work** and builds on it. Git commits act as checkpoints.

---

## Basic Setup

### Install the Plugin
```bash
/plugin marketplace add anthropics/claude-code
/plugin install ralph-wiggum@claude-plugins-official
```

### Run a Loop
```bash
/ralph-loop "Your task here. Success criteria:
- Criteria 1
- Criteria 2
Output <promise>DONE</promise> when complete." --max-iterations 20 --completion-promise "DONE"
```

### Cancel If Needed
```bash
/cancel-ralph
```

---

## Writing Good Prompts

**A good Ralph prompt has 4 parts:**

1. **Clear task** (one sentence)
2. **Measurable success criteria** (specific, testable)
3. **Process for progress** (what to do each iteration)
4. **Completion signal** (the exact text to output when done)

### Good Example
```
Migrate tests from Jest to Vitest. Success criteria:
- All tests pass
- Config files updated
- README updated
Output <promise>DONE</promise> when complete.
```

### Bad Example
```
Make the code cleaner and nicer.
```
↑ Can't measure "cleaner" or "nicer" — the loop won't know when to stop.

---

## Best Use Cases

✅ **Great for:**
- Test migrations
- Framework upgrades
- Adding test coverage
- Large refactors with clear specs
- Mechanical, repetitive tasks

❌ **Not great for:**
- Vague requirements ("make it better")
- Security-sensitive code (auth, payments)
- Architectural decisions
- Anything requiring human judgment/taste

---

## Key Tips

### 1. Always Set Max Iterations
Never run without `--max-iterations`. Start with 10-20, not 50.

### 2. Use Backpressure
Tests, linters, and type-checks automatically reject bad code. If tests fail, Claude knows to fix them.

### 3. Add "Signs" When It Fails
When Claude makes the same mistake repeatedly, add explicit instructions to prevent it:
- "Don't assume features aren't implemented—search first"
- "Only modify files in the /src directory"

### 4. One Task Per Loop
Don't cram multiple goals into one loop. Chain them instead:
```bash
/ralph-loop "Phase 1: Build database models..." --max-iterations 15
/ralph-loop "Phase 2: Build API endpoints..." --max-iterations 20
```

### 5. Sandbox for Overnight Runs
If running unattended, **always use a sandboxed environment** (Docker, VM, etc.). The `--dangerously-skip-permissions` flag bypasses safety checks.

---

## Cost Awareness

- 50 iterations on a large codebase = $50-100+ in API costs
- Failed attempts still cost money
- Start small, increase iterations as needed

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `/ralph-loop "prompt" --max-iterations N` | Start a loop |
| `--completion-promise "TEXT"` | What Claude outputs when done |
| `/cancel-ralph` | Stop the loop |

---

## TL;DR

1. Define exactly what "done" means
2. Let Claude loop until it gets there
3. Failures teach Claude what to fix
4. Always set max iterations
5. Use tests/linters as automatic feedback
6. Sandbox if running unattended
