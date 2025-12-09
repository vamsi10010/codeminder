# Feature Specification: CodeMinder - Code RAG MCP Server

**Feature Branch**: `001-code-rag-mcp`  
**Created**: 2025-12-07  
**Last Updated**: 2025-12-09 - Added configurable chunking strategy feature  
**Status**: Draft  
**Input**: User description: "Develop codeminder, an MCP server that implements retrieval augmented generation for code bases"

## Clarifications

### Session 2025-12-07

- Q: Vector Database Storage & Persistence - How should the vector index be stored? → A: In-memory with optional disk persistence
- Q: MCP Server Configuration & Codebase Path - How should the MCP server know which codebase directory to index? → A: Configuration file (e.g., .codeminder.json with codebase_path)
- Q: Error Response Format - When the MCP server encounters errors, what format should error responses follow? → A: Structured error objects with codes, messages, and context
- Q: Observability & Logging Strategy - What level of logging and observability should the system provide? → A: Structured logging with levels (DEBUG, INFO, WARN, ERROR) to file and stderr
- Q: Initial Index Build Trigger - When should the system perform the initial indexing of the codebase? → A: Via explicit MCP tool call (e.g., index_codebase)
- Q: File Watcher Behavior in Phase 1 - Should the file watcher be included in Phase 1 MVP? → A: Included in Phase 1 MVP (auto-updates enabled from start)
- Q: Re-indexing Strategy - When a file is modified, how should the system update the index? → A: Delete old chunks, re-parse entire file (simple, reliable)
- Q: Search Behavior During Re-indexing - What should happen if a search request arrives while a file is being re-indexed? → A: Complete re-index atomically, then respond (ensures consistency)
- Q: Handling Rapid Successive File Changes - What should happen if the same file is modified multiple times in quick succession? → A: Debounce with delay (wait 500ms for changes to settle)
- Q: Batch Update Handling (Git Operations) - What should happen when many files change simultaneously? → A: Parallel processing with configurable concurrency limit (from 1 to X files at once)

## User Scenarios *(mandatory)*

### User Story 1 - Semantic Code Search via MCP (Priority: P1)

An AI coding assistant (like Claude or Gemini) needs to find relevant code in a large codebase to answer a developer's question or implement a feature. The assistant invokes the CodeMinder MCP tool with a natural language query like "Find the authentication logic" and receives complete, executable code units with proper context.

**Why this priority**: This is the core value proposition - enabling AI assistants to intelligently retrieve code. Without this, CodeMinder has no purpose. This delivers immediate value as a working semantic search tool.

**Acceptance Scenarios**:

1. **Given** an AI agent invokes the `index_codebase` MCP tool, **When** indexing completes, **Then** the system confirms success and the codebase is ready for search
2. **Given** a codebase is indexed with AST-based chunks, **When** an AI agent queries "Find user authentication code", **Then** the system returns relevant functions/classes with full context (file path, class hierarchy, line numbers)
3. **Given** a large class or function exceeds token limits, **When** the system indexes it, **Then** it recursively breaks it into smaller valid AST nodes (methods, statements, expressions) while preserving the context path (File > Class > Method > Statement[N])
4. **Given** an AI agent receives search results, **When** it attempts to use the code, **Then** each chunk is syntactically valid and can be parsed independently (complete statements or expressions)
5. **Given** multiple relevant code units exist, **When** a query is made, **Then** results are ranked by semantic similarity with the most relevant appearing first

---

### User Story 2 - Automatic Index Maintenance (Priority: P1)

A developer is actively coding and saves changes to files. CodeMinder automatically detects the file changes and updates its index in the background without requiring manual commands or server restarts.

**Why this priority**: Real-time sync ensures the AI always works with current code, preventing bugs from stale information. This is essential for Phase 1 MVP to provide a seamless development experience without manual re-indexing.

**Acceptance Scenarios**:

1. **Given** the file watcher is running, **When** a developer saves changes to a Python file, **Then** the system deletes all old chunks for that file and re-parses the entire file within 2 seconds
2. **Given** a file is deleted, **When** the system detects the deletion, **Then** all chunks from that file are removed from the index
3. **Given** a new file is created, **When** the system detects it, **Then** the file is automatically parsed and indexed
4. **Given** multiple files change simultaneously (e.g., git checkout), **When** the watcher detects the changes, **Then** all files are re-indexed in parallel up to the configured concurrency limit
5. **Given** a file is being re-indexed, **When** old chunks are deleted and new chunks are added, **Then** search results reflect only the new version (no partial/mixed results)
6. **Given** a file is modified multiple times within 500ms, **When** the debounce period elapses, **Then** the system re-indexes the file only once with the latest content

---

### User Story 3 - Multi-Language Support (Priority: P2)

A codebase contains multiple programming languages (Python, JavaScript, TypeScript). CodeMinder can parse and index all supported languages, allowing AI assistants to search across the entire codebase regardless of language.

**Why this priority**: Most real-world projects are polyglot. This is deferred to Phase 2 to keep Phase 1 focused on Python-only, but remains important for broader adoption.

**Acceptance Scenarios**:

1. **Given** a repository contains Python and JavaScript files, **When** the system indexes the codebase, **Then** both languages are parsed with language-appropriate AST parsers
2. **Given** a query like "authentication middleware", **When** searching across languages, **Then** results include relevant matches from both Python decorators and JavaScript middleware functions
3. **Given** a language lacks semantic understanding, **When** indexing that file type, **Then** the system falls back to basic chunking with clear documentation of reduced accuracy

---

### Edge Cases

- What happens when a file has syntax errors and cannot be parsed into an AST?
  - System should log the error with structured error object (code: PARSE_ERROR, file path, line number), skip semantic chunking for that file, and optionally fall back to simple line-based chunking
- How does the system handle extremely large files (>10,000 lines)?
  - AST parsing should handle any valid syntax; chunking naturally breaks it into retrievable units
- What happens when the vector database is corrupted or unavailable?
  - System should return structured error object (code: DB_UNAVAILABLE, message, recovery suggestions) to the MCP client and fail gracefully without crashing
- How does the system handle binary files or non-code files?
  - System should skip files that aren't recognized code (based on extension filtering or magic number detection)
- What happens when the same query returns too many results (>100 chunks)?
  - System should limit results to top N (configurable, default 20) ranked by relevance score
- What happens when a search arrives during a file re-index operation?
  - System waits for atomic completion of the re-index before executing the search to ensure consistent results (no mixed old/new chunks)
- What happens when a file is modified many times rapidly (e.g., 10 edits in 2 seconds)?
  - System debounces changes with 500ms delay, re-indexing only once after changes settle to prevent thrashing
- What happens when a git branch switch changes 100+ files simultaneously?
  - System processes files in parallel up to the configured concurrency limit (default 4), completing all updates before reflecting changes in search results

## Requirements *(mandatory)*

### Functional Requirements

#### Phase 1: Core Semantic Search (MVP)

- **FR-001**: System MUST parse code files into Abstract Syntax Trees (AST) to identify logical boundaries such as functions, classes, methods, statements, and expressions
- **FR-002**: System MUST chunk code at valid AST node boundaries, ensuring each chunk is syntactically valid (can be parsed independently)
- **FR-003**: System MUST apply adaptive sizing - if a chunk's source_code fits within token limits (limit applies to code text only, not metadata), index it whole; otherwise recursively descend to child nodes (e.g., split large functions into individual statements or expression blocks)
- **FR-003a**: System MUST support two chunking strategies configurable via .codeminder.json: (1) "ast" strategy (default) that chunks at AST node boundaries ensuring syntactic validity, and (2) "line" strategy that splits files by raw token count without AST parsing, using sliding window approach with line-based boundaries
- **FR-004**: System MUST tag each code chunk with metadata including file path, line numbers, context path in format `filename:start_line-end_line` (see data-model.md for specification), AST node type (e.g., function_definition, if_statement, expression) for ast strategy or "line_chunk" for line strategy, and chunk sequence number for split nodes
- **FR-005**: System MUST embed code chunks into vector representations using a semantic embedding model suitable for code
- **FR-006**: System MUST store embeddings in a vector database that supports similarity search, operating in-memory with optional disk persistence to avoid full re-indexing on restart
- **FR-007**: System MUST expose an MCP-compliant server interface following the Model Context Protocol specification
- **FR-007a**: System MUST read configuration from a file (e.g., .codeminder.json) specifying the codebase path to index, token limits, persistence settings, and parallel processing concurrency limit
- **FR-007a-1**: System MUST persist File metadata to `.codeminder/vector_db/file_registry.lance` and validate path accessibility on startup
- **FR-007b**: System MUST provide an MCP tool named `index_codebase` that triggers initial indexing of the configured codebase directory. If indexing is already in progress, return error with code INDEX_IN_PROGRESS and estimated completion time
- **FR-008**: System MUST provide a callable MCP tool named `search_code` that accepts natural language queries
- **FR-009**: System MUST return search results formatted for LLM consumption including code snippet, file path, line numbers, and context path
- **FR-009a**: System MUST return structured error objects containing error code, human-readable message, and context object with fields: file_path (optional string), line_number (optional int), details (optional dict with additional error-specific data) when errors occur
- **FR-010**: System MUST rank search results by semantic similarity (vector distance) with most relevant results first
- **FR-011**: System MUST support Python code parsing and indexing as the sole language in Phase 1 using Tree-sitter with Python grammar (architecture supports future multi-language expansion in Phase 2)
- **FR-011a**: System MUST implement structured logging with configurable levels (DEBUG, INFO, WARN, ERROR) output to both log file (.codeminder/codeminder.log) and stderr for debugging and monitoring. Event levels: DEBUG (token counts, chunk creation details), INFO (file indexed, search queries), WARN (parse fallback, performance degradation), ERROR (indexing failures, search errors, watcher errors)
- **FR-012**: System MUST implement a background file watcher that monitors the codebase directory for changes. Symlinks within the codebase directory are followed and monitored; symlinks pointing outside codebase_path are ignored
- **FR-013**: System MUST automatically re-parse and re-index files when they are modified and saved by deleting all old chunks for that file and re-parsing the entire file atomically (no partial updates visible to search)
- **FR-014**: System MUST remove index entries for deleted files
- **FR-015**: System MUST add index entries for newly created files
- **FR-016**: System MUST complete re-indexing of changed files within 5 seconds total from file save event (including 500ms debounce delay for processing time)
- **FR-016a**: System MUST ensure search requests during file re-indexing wait for atomic completion of the update before returning results to maintain consistency
- **FR-016b**: System MUST debounce file change events with a 500ms per-file delay (resets on each change to the same file) to avoid thrashing when files are modified in rapid succession (e.g., auto-save)
- **FR-016c**: System MUST support parallel processing of multiple file changes with configurable concurrency limit (default 4 files, range 1-16) to handle batch operations like git branch switches efficiently

#### Phase 2: Enhanced Retrieval (Future)

- **FR-017**: System MUST build a code graph overlay that maps imports, function calls, and inheritance relationships
- **FR-018**: System MUST implement Reciprocal Rank Fusion (RRF) combining semantic similarity with structural importance (centrality scores)
- **FR-019**: System MUST calculate centrality scores using graph algorithms (e.g., PageRank) to identify widely-used code

### Key Entities

- **CodeChunk**: Represents a logical unit of code extracted from AST parsing
  - Attributes: unique ID, source code text, file path, start line, end line, context path (hierarchy), AST node type, chunk sequence number (for split nodes), language, token count
  - Relationships: belongs to a File, may have parent CodeChunk (for nested structures), may have sibling chunks (for split large nodes)

- **Embedding**: Vector representation of a CodeChunk
  - Attributes: chunk ID (foreign key), vector (float array), embedding model version
  - Relationships: one-to-one with CodeChunk

- **File**: Represents a source code file in the codebase
  - Attributes: absolute file path, relative path, language, last modified timestamp, parse status (success/error)
  - Relationships: contains many CodeChunks

- **CodeGraph** (Phase 2): Represents structural relationships between code units
  - Attributes: node ID (chunk ID), edge type (import/call/inheritance), target node ID, weight
  - Relationships: connects CodeChunks in a directed graph

- **MCPServer**: The Model Context Protocol server instance
  - Attributes: server name, version, available tools, configuration
  - Relationships: serves requests for CodeChunk searches

## Success Criteria *(mandatory)*

### Measurable Outcomes

#### Phase 1 Success Criteria

- **SC-001**: AI assistants can locate correct code files to edit given a bug description with >70% accuracy on a SWE-bench subset
- **SC-002**: Retrieved code chunks are syntactically valid at AST node granularity with 100% integrity (each chunk is a complete AST node: function, statement, or expression)
- **SC-003**: Search queries return results in under 1 second for codebases up to 100,000 lines of code
- **SC-004**: AI assistants can solve HumanEval problems using only retrieved "hidden" helper functions with >60% success rate
- **SC-005**: The MCP server successfully responds to 99% of valid search requests without crashes or errors
- **SC-006**: Initial codebase indexing completes within 5 seconds per 1,000 lines of code
- **SC-012**: Users can select chunking strategy ("ast" or "line") via configuration, and the system correctly applies the chosen strategy during indexing with appropriate metadata (node_type reflects strategy used)

#### Phase 2 Success Criteria

- **SC-007**: File changes are reflected in search results within 5 seconds total from file save event (including 500ms debounce delay for 4.5s processing time)
- **SC-008**: The file watcher operates continuously for 8+ hours without memory leaks or performance degradation
- **SC-009**: Multi-language indexing supports at least Python, JavaScript, and TypeScript with language-appropriate AST parsing

#### Phase 2+ Success Criteria (Future)

- **SC-010**: Hybrid retrieval (vector + graph) improves retrieval recall by >20% compared to vector-only search on complex codebases with deep dependency chains
- **SC-011**: Graph-enhanced search correctly identifies "important" files (high centrality) that are structurally critical but semantically distinct from queries

## Assumptions

1. **Embedding Model**: Use sentence-transformers for local embedding generation with configurable models (default: jinaai/jina-embeddings-v2-base-code with 768-dim, 8k context). No external API required.
2. **Token Limits**: Default token limit of 2048 tokens per chunk (configurable), supporting large functions while enabling adaptive splitting to statements/expressions when needed
3. **Vector Database**: Use LanceDB for embedded vector storage with in-memory operation and disk persistence to `.codeminder/vector_db/` (survives restarts, no separate server)
4. **MCP Protocol**: Assume the Model Context Protocol specification is publicly documented and stable
5. **Initial Language**: Phase 1 focuses exclusively on Python; AST parsing uses Tree-sitter with Python bindings (enables Phase 2 multi-language support)
6. **File System**: Assume POSIX-compliant file systems (Linux/macOS primary targets; Windows support via path normalization)
7. **Concurrency**: Parallel file processing in Phase 1 with configurable concurrency limit (default 4, range 1-16) using asyncio.Semaphore for handling batch file changes
8. **Deployment**: The MCP server runs locally on the developer's machine with configuration via .codeminder.json file in the codebase root, not as a remote service
9. **Security**: Assume the codebase being indexed is trusted; no sandboxing or malicious code protection in Phase 1

## Scope Boundaries

### In Scope (Phase 1)

- AST-based code chunking for Python (default strategy)
- Line-based code chunking as alternative strategy
- Configurable chunking strategy selection
- Semantic search using vector embeddings
- MCP server implementation with `search_code` and `index_codebase` tools
- Real-time file watching and automatic re-indexing
- Structured error handling with error codes
- Structured logging with configurable levels (DEBUG, INFO, WARN, ERROR)

### In Scope (Phase 2)

- Multi-language support (JavaScript, TypeScript)
- Performance optimization for large codebases
- Code graph overlay and hybrid retrieval (RRF)

### Out of Scope (All Phases)

- Code editing or modification capabilities (read-only system)
- Authentication or multi-user access control
- Remote/cloud deployment or API hosting
- Code execution functionality
- Integration with specific IDEs (MCP handles this)
- Version control integration (git blame, history)

## Dependencies

- Python 3.12+ runtime environment
- Tree-sitter (AST parsing with Python bindings - tree-sitter + tree-sitter-python)
- sentence-transformers (local embedding generation with configurable models, includes PyTorch)
- LanceDB (embedded vector database with in-memory + disk persistence)
- FastMCP (MCP server framework with decorator-based tool registration)
- Watchfiles (Rust-based file watching library with built-in debouncing)
- tiktoken (token counting for adaptive chunking algorithm)
- ruff (linting and formatting)
- mypy (type checking with strict mode)
- uv (package management and virtual environments)

## Constraints

- Must maintain syntactic integrity - each chunk must be a valid, parseable AST node (function, statement, or expression)
- Must preserve hierarchical context in all returned chunks (file > class > method path)
- Must respond to search queries within 1 second for typical codebases
- Must use existing MCP protocol standards (no custom extensions in Phase 1)
- Must operate within memory constraints of a typical developer laptop (8GB RAM minimum)
- Phase 1 delivery target: 3 days for working MVP with Python support only
