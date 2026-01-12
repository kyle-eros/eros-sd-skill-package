# Progressive Disclosure in Claude Code

## Overview

This document breaks down the emerging paradigm shift in AI agent architecture: **progressive disclosure**. Multiple industry leaders—Cloudflare, Anthropic, Vercel, and Cursor—have independently arrived at the same conclusion about how to build more effective AI agents.

---

## The Core Insight

> **Progressively disclose only what you need to the model, when you need it.**

The industry trend for implementing this: give agents a **file system** and **bash**, then let them discover and load resources on demand using standard methods like `grep`, `glob`, and `find`.

---

## The Problem with Traditional MCP Usage

### How We Were Using MCP (Wrong)

When loading MCP servers directly as tools to the LLM, several issues emerge:

- **Context bloat**: MCPs sit in context even when never used
- **Wasted tokens**: Paying for tool definitions on every request "just in case"
- **Degraded performance**: Large context windows reduce model accuracy
- **Limited scalability**: Can only reasonably have 5-20 MCP servers before performance degrades

### The Realization

Models are exceptionally good at **writing code**—they're not necessarily great at leveraging MCP tool schemas directly. The question became: *What if the model just wrote the code to find and use the MCPs it needs?*

---

## Industry Convergence

### Cloudflare (September 2024)

**Blog Post**: "Code Mode: The Better Way to Use MCP"

Key insight: Instead of generating JSON tool calls, generate **TypeScript code** that runs in a sandbox. The MCP server becomes a TypeScript API in isolated sandboxes.

**Result**: **98.7% reduction in token usage**

### Anthropic (Advanced Tool Use Release)

Introduced several correlated features:

| Feature | Description |
|---------|-------------|
| **Tool Search Tool** | Discovers tools on demand instead of loading all definitions upfront |
| **Programmatic Tool Calling** | Invokes tools in a code execution environment |
| **Memory Tool** | File-based simple markdown files |

**Token Reduction Example**:
- Previous approach: **77,000 tokens** of context
- With Tool Search Tool: **8,700 tokens**
- **85% reduction** while maintaining full tool library access

**Accuracy Improvements** (internal testing on MCP evaluations):
| Model | Before | After |
|-------|--------|-------|
| Opus 4 | 49% | 74% |
| Opus 4.5 | 79.5% | 88.1% |

### Cursor (Recent)

Confirmed the same pattern with their own implementation:
- **46.9% reduction** in total agent tokens

---

## The New Architecture

### Paradigm Shift

| Old Approach | New Approach |
|--------------|--------------|
| Load everything upfront | Discover on demand |
| Burn tokens on unused tools | Load only what's needed |
| Limited by context window | Scalable to thousands of tools |
| Complex orchestration required | File system + bash handles discovery |

### Core Components

1. **File System Access**: Read, write, search files
2. **Bash Execution**: Run commands, scripts, git operations
3. **Code Execution**: Call MCP servers programmatically

### The Mental Model

> **Give the agent a file system and get out of the way.**

| Concept | Implementation |
|---------|----------------|
| Tools | Become files |
| Discovery | Becomes search |
| Execution | Becomes code |
| Context | Remains small |

---

## Skills: Progressive Disclosure in Claude Code

### What Are Skills?

Skills are the primary mechanism for progressive disclosure in Claude Code. They consist of:

- **Front matter**: Minimal metadata disclosed to the model (10-100 tokens)
- **Skill file**: Full instructions loaded only when invoked
- **References**: Can chain to other files, scripts, or sub-skills

### How Skills Work

```
┌─────────────────────────────────────────────┐
│           Agent Context (Always)            │
│  ┌───────────────────────────────────────┐  │
│  │ Skill Front Matter (minimal tokens)   │  │
│  │ - Name: Web Research                  │  │
│  │ - Description: Uses Firecrawl...      │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                    │
                    ▼ (only when needed)
┌─────────────────────────────────────────────┐
│         Skill File (loaded on demand)       │
│  - Full instructions                        │
│  - Tool configurations                      │
│  - References to other files/scripts        │
└─────────────────────────────────────────────┘
                    │
                    ▼ (if referenced)
┌─────────────────────────────────────────────┐
│         Sub-skills / Scripts / Docs         │
│  - Additional context as needed             │
│  - Hierarchical discovery                   │
└─────────────────────────────────────────────┘
```

### Skill Architecture Options

1. **Flat directory**: All skills at the same level
2. **Hierarchical structure**: Skills with sub-skills, allowing progressive discovery down the lineage

### Example Use Cases

- **Web Research Skill**: Contains Firecrawl configuration, loaded only when web research is needed
- **Code Review Skill**: Chains to linting scripts, style guides
- **Database Skill**: References connection configs, query templates

---

## Experimental: MCP CLI Flag

> ⚠️ **Alpha Feature** - May change or be removed

Claude Code has an experimental flag for tool search capability:

```bash
# Enables tool search instead of loading all MCP tools into context
# Check current documentation for the exact flag name
```

**Benefits**:
- Reduces MCP context from tens of thousands of tokens to near-zero
- Maintains access to all MCP servers
- Allows for much more ambitious tool libraries

**Considerations**:
- Still a work in progress
- May not work quite as well as having MCPs directly in context for all use cases
- Worth experimenting with for large tool libraries

---

## Memory: Keep It Simple

### The Approach

Memory in this paradigm is just **files**:

- `claude.md` files
- Markdown documentation
- Scripts
- Skills

### Why This Works

| Complex Approach | Simple Approach |
|------------------|-----------------|
| Embeddings | Plain text files |
| Vector databases | File system search |
| Complex retrieval | Agentic search |

As noted by developers at Anthropic: "Instead of all the embeddings and vector stuff, just have that agentic search. It just felt better. It just works well."

### Operations

- **Read**: Load files when needed
- **Edit**: Update files with new information
- **Search**: Find relevant files using standard tools

> *"If it's simple for us, it's going to be simple for agents."*

---

## Context Management

### Automatic Cleanup

Anthropic noted that Claude can automatically clear old tool results as context limits approach. This enables:

- Progressive removal of less relevant context
- Sustained operation over longer sessions
- More efficient context utilization

### Working Memory Model

```
┌─────────────────────────────────────┐
│         Long-term Memory            │
│  (Files, Skills, Scripts on disk)   │
└──────────────────┬──────────────────┘
                   │
                   ▼ Load on demand
┌─────────────────────────────────────┐
│         Working Memory              │
│  (Current context window)           │
│  - Active task context              │
│  - Recently used tool results       │
│  - Current skill instructions       │
└──────────────────┬──────────────────┘
                   │
                   ▼ Clear when stale
┌─────────────────────────────────────┐
│         Archived/Cleared            │
│  (Old tool results, completed       │
│   sub-task context)                 │
└─────────────────────────────────────┘
```

---

## What This Enables

### Before Progressive Disclosure

- Keep tasks small
- Minimize tool use
- Watch for context limits
- Worry about context resetting
- Limited to 5-20 MCP servers

### After Progressive Disclosure

- **Multi-hour autonomous runs**
- **Dozens to thousands of tool integrations**
- **Complex workflows without complex orchestration**
- **Context is no longer the bottleneck**
- Systems can have memory, working memory, write helper scripts, and update skills dynamically

---

## The 2026 Paradigm

The convergence points to this architecture for agentic development:

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Runtime                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ File System │  │    Bash     │  │ Code Execution  │  │
│  │   Access    │  │  Commands   │  │   (for MCP)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│                           │                              │
│                           ▼                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Ephemeral Sandboxes                   │  │
│  │  - Read/write file systems                        │  │
│  │  - Spin up applications                           │  │
│  │  - Execute scripts                                │  │
│  │  - Shut down when complete                        │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Key Players Using This Pattern

- **Anthropic**: Claude.ai web app uses sandboxes, writes to file systems
- **Vercel**: Sandbox products
- **Cloudflare**: Isolated sandbox execution
- **Daytona**: Development sandboxes
- **Lovable**: Form of sandboxes for app generation

---

## Summary: The New Rules

| Principle | Implementation |
|-----------|----------------|
| **Tools as files** | Store tool definitions in the file system |
| **Loaded on demand** | Only read tools when actually needed |
| **Skills for progressive disclosure** | Front matter visible, full content loaded when invoked |
| **Bash is all you need** | Standard commands for discovery and execution |
| **Keep context small** | Aggressive context management, clear old results |
| **Memory = Files** | Simple markdown, no complex embeddings needed |

---

## Key Takeaways

1. **The industry has converged**: Cloudflare, Anthropic, Cursor all arrived at the same conclusion independently
2. **Progressive disclosure works**: 85-98% token reduction with improved accuracy
3. **File systems + bash = discovery**: No need for complex orchestration
4. **Skills enable scale**: From tens to potentially thousands of capabilities
5. **Simplicity wins**: Plain files beat complex vector/embedding systems
6. **2026 will be about sandboxes**: Ephemeral file systems for agentic development

> *"MCP, file system, and code execution—that might be the answer, at least as it stands right now."*
