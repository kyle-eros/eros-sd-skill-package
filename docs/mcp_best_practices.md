Comprehensive Best Practices Summary for MCP Tools in Multi-Agent Pipelines

       Based on exhaustive research of Claude Code v2.1.3+ and Agent SDK documentation, here's a complete set of current best practices for
       optimizing MCP tools within multi-agent pipeline workflows:

       ---
       1. MCP TOOL INTERFACE DESIGN

       Input/Output Schema Best Practices

       Schema Consistency & Clarity:
       - Use JSON Schema with explicit type and required fields
       - Include detailed description fields for every input parameter (Claude uses these to decide when to invoke)
       - Name parameters to be self-documenting (avoid abbreviations)
       - Define enums for constrained inputs (e.g., "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]})
       - Provide examples in descriptions when possible
       - Use additionalProperties: false to enforce strict schema validation

       Return Schema Contracts:
       - Establish consistent return field naming across related tools (avoid result, data, response inconsistently)
       - Use TypedDict or dataclass patterns for return values to ensure type safety
       - Include status/success indicators explicitly in responses
       - Return structured data, not raw strings (JSON objects, typed dicts)
       - Document all possible return fields—empty optional fields cause parsing ambiguity

       Backwards Compatibility:
       - Never remove or rename required fields without major version bump
       - New optional fields with defaults are safe to add
       - When changing semantics, use new field names rather than repurposing old ones
       - Maintain field ordering for API predictability

       Tool Naming Conventions

       - Use mcp__servername__toolname format in Claude Code
       - Keep names lowercase with underscores, descriptive but concise
       - Group related tools with consistent prefixes (e.g., get_creator_profile, get_allowed_content_types vs fetch_creator_info,
       fetch_vault_info)
       - Avoid verbs like "fetch"—use get for retrievals consistently

       ---
       2. ERROR HANDLING & RESILIENCE PATTERNS

       Circuit Breaker Pattern (Critical for Reliability)

       From your CLAUDE.md context, MCP validation is ZERO TOLERANCE:
       - Implement pre-flight validation before MCP calls
       - Fail fast with clear error messages, never silent failures
       - Never fall back to raw SQL—MCP-first always
       - Log every meaningful operation; errors must be traceable

       In Practice:
       # Four-layer defense system pattern
       1. Schema validation (input conformance)
       2. Pre-execution guards (business rules check)
       3. Execution with timeout (prevent hangs)
       4. Result validation (output conformance)

       Error Response Standards

       - Include error codes in MCP tool output (not just strings)
       - Provide context in error messages: what failed, why, recovery hints
       - Return structured error objects, not exception stack traces
       - Include request metadata in error response for debugging
       - Use is_error or status field consistently

       Retry Logic

       - Implement exponential backoff for transient failures (database timeouts, network issues)
       - Distinguish between retriable (timeout, rate limit) and permanent errors (validation, auth)
       - Set MCP tool timeout via MCP_TIMEOUT environment variable (default reasonable, e.g., 10s)
       - Don't retry silently—log retries for observability
       - Cap retries at 3-5 attempts maximum

       ---
       3. MULTI-AGENT SKILL PACKAGE PIPELINE ORCHESTRATION

       Skill Package Structure

       Progressive Disclosure Pattern (Critical for Context Efficiency):
       skill-name/
       ├── SKILL.md              # Overview + trigger conditions (under 500 lines)
       ├── REFERENCE.md          # Detailed API docs (loaded only when needed)
       ├── EXAMPLES.md           # Usage examples
       └── scripts/
           └── helper.py         # Utility scripts (executed, not loaded into context)

       SKILL.md Metadata Optimization:
       ---
       name: schedule-generator
       description: "Generates optimized creator schedules. Use when optimizing OnlyFans content distribution, creating weekly schedules, or 
       planning send timing."
       allowed-tools: Read,Bash,mcp__eros-db__*
       model: sonnet  # Route expensive work to appropriate models
       context: fork  # For complex multi-step operations
       skills: [validation-helpers]  # Reference other skills if needed
       ---

       Inter-Agent Communication Patterns

       Skill-to-Subagent Delegation:
       - Subagents can be spawned via Task tool, but skills run in main conversation
       - Use skills for guidance/knowledge, subagents for isolated complex work
       - Skills don't spawn subagents (no nesting)—chain via main conversation

       Context Passing Strategy:
       - Skills inherit parent conversation context automatically
       - Explicitly reference required MCP tools in allowed-tools (comma-separated or YAML list)
       - Use context: fork for high-output operations to preserve main context
       - Memory hierarchy: enterprise > project > user > session (higher overrides lower)

       Pipeline Phase Orchestration

       Parallel vs Sequential Execution:
       - MCP tools in the same phase execute independently when possible—invoke as parallel tool calls
       - Phases with dependencies must be sequential
       - Use context: fork for isolated phases that produce verbose output
       - Document phase dependencies explicitly in CLAUDE.md

       Phase Context Management:
       - Each phase should focus on one logical task (separation of concerns)
       - Return structured summaries from phases, not raw outputs
       - Document expected input/output schemas between phases
       - Pre-cache data that multiple phases depend on (e.g., creator profiles at start)

       ---
       4. DATABASE INTEGRATION VIA MCP (SQLite-Specific)

       Query Optimization for MCP Tools

       Pre-Computed Views vs Real-Time Calculation:
       - Create views for frequently accessed aggregations (performance_trends, volume_config)
       - Cache-friendly patterns: retrieve once, pass through pipeline
       - Avoid N+1 queries—use JOINs within single MCP call
       - Return paginated results for large datasets (cursor-based pagination preferred)

       Caching Strategies:
       - Pre-cache at pipeline start: Load creator profiles, content type rankings once, pass as context
       - Tool-level caching: If MCP tool recalculates same data, implement internal cache with TTL
       - Conversation-level caching: Store intermediate results in memory hierarchy
       - Never cache user-specific private data across sessions

       Query Execution Patterns:
       # Good: Single MCP call with JOIN
       get_creator_profile(creator_id)  # Returns nested: profile + persona + performance

       # Bad: Multiple sequential calls (N+1 pattern)
       get_creator_profile(creator_id)
       get_persona_profile(creator_id)
       get_performance_trends(creator_id)

       Input Validation in MCP Tools

       - Validate all inputs against expected types/ranges before query execution
       - Return validation errors explicitly, never silently adjust parameters
       - Document validation rules in tool description
       - Handle NULL/missing values with clear defaults

       ---
       5. CLAUDE CODE MEMORY & CONTEXT HIERARCHY

       Memory Hierarchy (Highest to Lowest Priority)

       1. Enterprise (/Library/Application Support/ClaudeCode/CLAUDE.md): Org-wide policies
       2. Project (.claude/CLAUDE.md or .claude/rules/*.md): Team-shared instructions
       3. User (~/.claude/CLAUDE.md): Personal preferences
       4. Project Local (CLAUDE.local.md): Personal project-specific (not version controlled)

       Pre-Caching Patterns

       At Session Start:
       - Load critical MCP tool metadata
       - Cache creator profiles, content types, volume configs
       - Store in conversation memory for reuse across phases
       - Use context: fork to prevent large caches from bloating main context

       During Pipeline:
       - Pass cached data through conversation context
       - Reference by variable name, avoid redundant MCP calls
       - Clear non-essential caches after phase completion

       Context Window Management

       - Monitor token usage with /cost command
       - Use context: fork for phases that produce >2000 lines of output
       - Implement auto-compaction (enabled by default)
       - Subagent transcripts persist independently; main conversation compaction doesn't affect them

       ---
       6. TOOL CONTRACT DESIGN FOR PIPELINE CONSUMERS

       Return Schema Consistency

       Pattern: Consistent Field Names Across Similar Tools
       # ✓ Good consistency
       get_creator_profile() → {creator_id, profile_data, persona, performance_metrics, error: null}
       get_content_type_rankings() → {creator_id, rankings: [...], cached_at, error: null}

       # ✗ Bad inconsistency
       get_creator_profile() → {id, data, persona, stats, error_message}
       get_content_type_rankings() → {creator_id, result: [...], timestamp, error}

       Field Naming Conventions:
       - Use is_ prefix for booleans (is_active, is_cached)
       - Use _at suffix for timestamps (created_at, cached_at)
       - Use _count suffix for quantities (message_count, send_count)
       - Pluralize collections (rankings, creators, not ranking, creator)
       - Avoid single-letter abbreviations in return values

       Consumer Expectation Alignment

       Document In Tool Description:
       - What the tool does in plain English
       - Required vs optional inputs
       - Guaranteed vs conditional output fields
       - Failure modes and error handling
       - Response size (small, medium, large—important for context management)

       Example Description:
       "Retrieves creator performance trends. Returns trending metrics (engagement, view_rate,
       revenue) over last 30 days. Cached hourly. Returns empty trends if creator has <7 days data."

       Backwards Compatibility Strategy

       - Add new optional fields with defaults
       - Never remove or rename required fields
       - Version responses (version: "2.0") for major structural changes
       - Document deprecations in descriptions
       - Maintain old field aliases during transition period

       ---
       7. SUBAGENT & TASK DELEGATION

       When to Use Subagents

       - High-volume output operations: run tests, fetch logs, process datasets
       - Isolated workflows: code review, security scanning, separate from main flow
       - Tool restrictions needed: limit certain agent to read-only, specific MCP tools
       - Different model requirements: use cheaper model (Haiku) for exploration phases

       Subagent Configuration Best Practices

       ---
       name: phase-validator
       description: "Validates pipeline outputs against quality gates. Use proactively after phase completion."
       model: sonnet  # Balances capability + cost
       tools: Read,Grep,Bash,mcp__eros-db__*
       permissionMode: plan  # Read-only validation
       hooks:
         PreToolUse:
           - matcher: "Bash"
             hooks:
               - type: command
                 command: "./scripts/validate-query.sh $TOOL_INPUT"
       ---

       Subagent Lifecycle Management

       - Subagent transcripts persist independently of main conversation
       - Can resume subagents to continue work: Resume that phase-validator and check X
       - Subagents can't spawn nested subagents (use Skills instead)
       - Auto-compaction applies to subagent transcripts independently

       ---
       8. VALIDATION & QUALITY GATES

       Four-Layer Defense System (Your Pattern)

       1. Input Validation: Check parameter types, ranges, required fields
       2. Pre-Execution Guards: Business logic validation (creator exists, state valid)
       3. Execution: MCP call with timeout, error handling
       4. Output Validation: Result schema conformance, field population

       Quality Gates in Pipeline

       - Phase input validation: Verify upstream output before consuming
       - Phase output validation: Independent subagent validates deliverables
       - End-to-end validation: Cross-phase consistency checks
       - Fail-fast philosophy: Don't pass invalid data to next phase

       ---
       9. PERFORMANCE OPTIMIZATION

       MCP Output Limits

       - Default max: 25,000 tokens per MCP tool output
       - Warning threshold: 10,000 tokens
       - Increase with MAX_MCP_OUTPUT_TOKENS env var if needed
       - Design tools to paginate/filter rather than return massive responses

       Parallel Tool Execution

       - When tool calls are independent, invoke together: Claude will parallelize
       - Example: get_creator_profile, get_content_rankings, get_volume_config in one prompt
       - All results returned in single tool result block
       - Reduces round trips, improves latency

       Pre-Computation & Caching

       - Pre-load critical data at pipeline start
       - Use views for complex aggregations (compute once per hour, cache)
       - Build indexes for frequently filtered queries
       - Document what's cached and TTL

       ---
       10. DEPLOYMENT & CONFIGURATION

       MCP Installation Scopes (Highest to Lowest Priority)

       1. CLI flags (--agents, --mcp): Session-specific
       2. Project (.mcp.json): Team-shared, version controlled
       3. User (~/.claude.json under mcpServers): Personal cross-project
       4. Plugin: Auto-loaded when plugin enabled

       Configuration Best Practices

       {
         "mcpServers": {
           "eros-db": {
             "type": "stdio",
             "command": "python",
             "args": ["/path/to/eros_mcp_server.py"],
             "env": {
               "DB_PATH": "${DB_PATH:-/var/eros.db}",
               "LOG_LEVEL": "${LOG_LEVEL:-info}"
             }
           }
         }
       }

       - Use environment variable expansion (${VAR:-default})
       - Absolute paths for server executables
       - Document all env vars required
       - Version MCP server command (if applicable)

       Managed Configuration

       - managed-mcp.json for exclusive server control (system-wide)
       - allowedMcpServers / deniedMcpServers for policy-based control
       - Command matching requires exact array match: ["npx", "-y", "package"] ≠ ["npx", "package"]
       - URL wildcards supported: https://*.internal.corp/*

       ---
       SUMMARY: Refactoring Checklist

       When refactoring an MCP tool within your EROS pipeline:

       - Schema: Consistent field names, clear descriptions, proper types
       - Error Handling: Structured errors, four-layer validation
       - Return Values: TypedDict/dataclass, backwards compatible
       - Tool Description: Specific trigger keywords, expected input/output documented
       - Caching: Pre-load at pipeline start, avoid N+1 queries
       - Performance: Paginate large results, parallelize independent calls
       - Testing: Unit tests for validation, integration tests with pipeline
       - Documentation: Update SKILL.md, REFERENCE.md with new/changed fields
       - Backwards Compatibility: Handle old field names during transition
       - Monitoring: Log all MCP calls, errors, execution time

       ---
       Key Files for Reference

       Claude Code Docs:
       - /code.claude.com/docs/en/mcp.md - MCP installation & configuration
       - /code.claude.com/docs/en/skills.md - Skill design & progressive disclosure
       - /code.claude.com/docs/en/sub-agents.md - Subagent patterns & delegation
       - /code.claude.com/docs/en/memory.md - Memory hierarchy & context management

       Agent SDK Docs:
       - /platform.claude.com/docs/en/agent-sdk/mcp.md - SDK MCP integration
       - /platform.claude.com/docs/en/agents-and-tools/tool-use/overview.md - Tool contract design

       Your Project:
       - /Users/kylemerriman/Developer/eros-sd-skill-package/CLAUDE.md - Your documented preferences
       - Your settings.json defines allowed MCP tools, permission modes, and MCP server configurations

       This comprehensive framework should guide your MCP tool refactor toward optimal performance, reliability, and maintainability within
       your multi-agent EROS pipeline.