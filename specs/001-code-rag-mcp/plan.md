# Implementation Plan: CodeMinder - Code RAG MCP Server

**Branch**: `001-code-rag-mcp` | **Date**: 2025-12-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-code-rag-mcp/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

**Primary Requirement**: Build an MCP server that bridges the "context gap" in AI coding assistants by enabling intelligent, syntax-aware code retrieval through AST-based chunking and semantic search.

**Technical Approach**: 
- **Parsing**: Tree-sitter for language-agnostic AST parsing ensuring code is chunked by valid syntax (functions/classes) rather than arbitrary lines
- **Embeddings**: sentence-transformers for local, privacy-preserving embedding generation with configurable models (default: jinaai/jina-embeddings-v2-base-code)
- **Database**: LanceDB as embedded, serverless vector database running in-process for local operation
- **Server**: FastMCP (Python) for Model Context Protocol implementation via decorators
- **File Watcher**: Watchfiles (Rust-based) for automatic re-indexing with debouncing
- **Algorithm**: Adaptive "Largest Valid Node" AST chunking strategy with context tagging

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: 
- Tree-sitter (AST parsing with language bindings)
- sentence-transformers (local embedding generation with configurable models)
- LanceDB (embedded vector database with in-memory + disk persistence)
- FastMCP (MCP server implementation via decorators)
- Watchfiles (Rust-based file watching with debouncing)
- tiktoken (token counting for adaptive chunking)

**Storage**: 
- Vector embeddings: LanceDB (in-memory with optional disk persistence to `.codeminder/` directory)
- Configuration: JSON file (`.codeminder.json` in codebase root)
- Logs: Structured logs to file (`.codeminder/codeminder.log`) and stderr



**Target Platform**: Linux/macOS developer machines (local MCP server)  
**Project Type**: Single Python project with MCP server  
**Performance Goals**: 
- Search queries: <1 second for codebases up to 100k LOC
- Initial indexing: 5 seconds per 1,000 LOC
- Re-indexing: <2 seconds per file (with 500ms debounce)
- Parallel processing: 4 files simultaneously (configurable 1-16)

**Constraints**: 
- <100ms response time for interactive MCP operations (status checks)
- <8GB RAM for typical developer laptop
- Syntactic validity: 100% (each chunk is a complete, parseable AST node)
- File watcher: 8+ hours continuous operation without memory leaks

**Scale/Scope**: 
- Phase 1: Python codebases, single language
- Target size: 100k-500k LOC codebases
- Chunk limit: 2048 tokens (configurable, aligned with embedding model)
- Search results: Top 20 by default (configurable)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with constitution principles:

- [x] **Code Quality First**: Architecture supports clean, maintainable code
  - Single responsibility: ✓ (separate modules for parsing, embedding, search, MCP server, file watching)
  - Code style and quality tooling: ✓ (ruff for linting/formatting, mypy for type checking)
  - Public APIs documented: ✓ (MCP tools will have comprehensive docstrings)
- [x] **User Experience Above All**: Design prioritizes user success
  - User scenarios defined first: ✓ (3 user stories with acceptance criteria in spec)
  - Error messages actionable: ✓ (structured error objects with codes, messages, recovery suggestions)
  - Sensible defaults provided: ✓ (.codeminder.json with defaults, auto-detect common settings)
  - Response time targets identified: ✓ (<1s search, <2s re-index, <100ms status)
- [x] **Simplicity Over Complexity**: Simplest viable solution chosen
  - YAGNI applied: ✓ (Phase 1 Python-only, defers graph overlay to Phase 2)
  - Dependencies justified: ✓ (Tree-sitter: multi-language AST; LanceDB: embedded vector DB; FastMCP: MCP protocol)
  - Each module has single clear purpose: ✓ (chunker, embedder, searcher, watcher, server)
- [x] **Proper Abstractions**: Abstractions earn their existence
  - No premature abstractions: ✓ (delete-and-reparse for updates, not complex diff-based incremental)
  - Clear boundaries: ✓ (AST parsing → chunking → embedding → vector storage → search)
- [x] **Performance Consciousness**: Performance adequate and measurable
  - Performance requirements documented: ✓ (see Technical Context above)
  - Benchmarks planned: ✓ (indexing speed, search latency, memory usage)
  - Resource limits identified: ✓ (<8GB RAM, <1s search, 8+ hours uptime)

*All checks pass. No violations requiring justification.*

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
codeminder/                          # Repository root
├── .codeminder.json                 # Configuration file (created by user)
├── pyproject.toml                   # Python project metadata (uv-managed)
├── README.md                        # Project documentation
├── src/
│   └── codeminder/
│       ├── __init__.py
│       ├── server.py                # FastMCP server with tool decorators
│       ├── config.py                # Configuration loading and validation
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── ast_parser.py        # Tree-sitter AST parsing
│       │   └── chunker.py           # Adaptive "Largest Valid Node" chunking
│       ├── embeddings/
│       │   ├── __init__.py
│       │   ├── embedder.py          # Jina Embeddings integration
│       │   └── token_counter.py     # tiktoken-based token counting
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── vector_db.py         # LanceDB operations (CRUD)
│       │   └── models.py            # Data models (CodeChunk, Embedding, File)
│       ├── search/
│       │   ├── __init__.py
│       │   └── searcher.py          # Semantic search with ranking
│       ├── watcher/
│       │   ├── __init__.py
│       │   └── file_watcher.py      # Watchfiles-based monitoring with debounce
│       └── utils/
│           ├── __init__.py
│           ├── logger.py            # Structured logging setup
│           └── errors.py            # Custom error classes with codes
├── .codeminder/                     # Runtime data directory (gitignored)
│   ├── vector_db/                   # LanceDB persistent storage
│   └── codeminder.log               # Structured log file
└── .specify/                        # Project specifications
    └── specs/001-code-rag-mcp/
```

**Structure Decision**: Single Python project using `src/` layout for proper packaging. Modular design with clear separation of concerns:
- `parser/`: AST parsing and chunking (Tree-sitter)
- `embeddings/`: Code embedding generation (Jina)
- `storage/`: Vector database operations (LanceDB)
- `search/`: Semantic search and ranking
- `watcher/`: File system monitoring (Watchfiles)
- `server.py`: MCP server entry point (FastMCP)
- `config.py`: Configuration management
- `utils/`: Cross-cutting concerns (logging, errors)

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**Status**: No violations. All constitution checks pass without requiring justification.

The design follows YAGNI principles:
- Phase 1 focuses on Python-only (multi-language deferred to Phase 2)
- Simple delete-and-reparse strategy (not complex incremental diff updates)
- Embedded database (not remote service)
- Straightforward MCP decorators (not custom protocol extensions)
