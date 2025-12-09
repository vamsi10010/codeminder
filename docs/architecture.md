# CodeMinder Architecture

**Version**: 1.0 (User Story 1)  
**Last Updated**: December 2025

This document explains the technical architecture, design decisions, and algorithms behind CodeMinder's semantic code search capabilities.

---

## Table of Contents

- [System Overview](#system-overview)
- [Core Components](#core-components)
- [AST Chunking Algorithm](#ast-chunking-algorithm)
- [Data Flow](#data-flow)
- [Storage Architecture](#storage-architecture)
- [Startup Reconciliation](#startup-reconciliation)
- [Search Pipeline](#search-pipeline)
- [Performance Considerations](#performance-considerations)
- [Design Decisions](#design-decisions)

---

## System Overview

CodeMinder is a Model Context Protocol (MCP) server that enables AI assistants to perform intelligent code search using semantic understanding rather than simple text matching.

### Architecture Principles

1. **Syntax-Aware Chunking**: Every code chunk is a complete, parseable AST node (function, class, statement, or expression)
2. **Local-First**: All processing happens on your machine - code never leaves your environment
3. **Persistence**: File registry and embeddings survive server restarts
4. **Efficient Updates**: Only re-indexes files that actually changed
5. **Modular Design**: Clear separation of concerns across parser, embedder, storage, and search components

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Client                              │
│                   (Claude Desktop, Cursor)                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP Protocol (stdio)
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      FastMCP Server                             │
│                    (src/codeminder/server.py)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MCP Tools:                                               │  │
│  │  • index_codebase()  - Manual re-index trigger            │  │
│  │  • search_code()     - Semantic search query              │  │
│  │  • get_index_status() - Index statistics                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Parser     │  │  Embeddings  │  │   Search     │         │
│  │   Module     │  │   Module     │  │   Module     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Storage Module (LanceDB)                     │  │
│  │  • file_registry table  - File metadata                   │  │
│  │  • code_chunks table    - Code + embeddings               │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                             │
                             │ Persistence
                             ▼
                    ┌────────────────────┐
                    │   .codeminder/     │
                    │   • vector_db/     │
                    │   • codeminder.log │
                    └────────────────────┘
```

---

## Core Components

### 1. Parser Module (`src/codeminder/parser/`)

**Responsibility**: Convert source files into semantically meaningful code chunks

**Components**:
- **`ast_parser.py`**: Tree-sitter integration for language-agnostic AST parsing
- **`chunker.py`**: Adaptive "Largest Valid Node" chunking algorithm
- **`token_counter.py`**: tiktoken-based token counting for chunk size validation
- **`scanner.py`**: Recursive directory traversal with file filtering

**Key Features**:
- Multi-language AST parsing (Python in Phase 1, extensible to JS/TS/Java)
- Error-resilient parsing (continues even with syntax errors)
- Configurable token limits (default 2048, range 512-8192)

### 2. Embeddings Module (`src/codeminder/embeddings/`)

**Responsibility**: Generate vector embeddings for code chunks using local models

**Components**:
- **`embedder.py`**: sentence-transformers integration with GPU/CPU auto-detection

**Key Features**:
- **Privacy-preserving**: Code never sent to external APIs
- **Configurable models**: Users choose based on hardware capabilities
  - Default: `jinaai/jina-embeddings-v2-base-code` (768-dim, 8k context)
  - Lightweight: `microsoft/codebert-base` (~500MB)
  - Budget: `sentence-transformers/all-MiniLM-L6-v2` (~80MB)
- **Batch processing**: Encodes multiple chunks together for efficiency
- **Device optimization**: Automatic GPU detection with CPU fallback

### 3. Storage Module (`src/codeminder/storage/`)

**Responsibility**: Persist file registry and code embeddings to disk

**Components**:
- **`vector_db.py`**: LanceDB operations (connect, create tables, CRUD, search)
- **`models.py`**: Pydantic data models (File, CodeChunk, Embedding)

**Storage Tables**:

| Table | Purpose | Schema Key Fields |
|-------|---------|-------------------|
| `file_registry` | File metadata tracking | `file_id`, `absolute_path`, `last_modified`, `last_indexed` |
| `code_chunks` | Code + embeddings | `chunk_id`, `file_id`, `source_code`, `vector`, `context_path` |

**Key Features**:
- **Embedded database**: Runs in-process, no separate server needed
- **Columnar format**: Optimized for vector similarity search (ANN)
- **Persistent storage**: Survives server restarts (`.codeminder/vector_db/`)
- **Indexed lookups**: O(1) file lookup by `absolute_path`

### 4. Search Module (`src/codeminder/search/`)

**Responsibility**: Execute semantic search queries and rank results

**Components**:
- **`searcher.py`**: Query embedding, vector search, result formatting

**Key Features**:
- **Cosine similarity**: Measures semantic closeness between query and code
- **Approximate Nearest Neighbors (ANN)**: Fast search for large codebases
- **Configurable result limit**: Default 20, range 1-100
- **Context preservation**: Returns code with file paths and line numbers

### 5. MCP Server (`src/codeminder/server.py`)

**Responsibility**: Expose indexing and search capabilities via MCP protocol

**Key Features**:
- **FastMCP decorators**: Simple `@mcp.tool()` syntax for tool definitions
- **Async operations**: Non-blocking I/O for file processing
- **Startup reconciliation**: Automatic detection of changed files on server start
- **Parallel processing**: Configurable concurrency (default 4, range 1-16)

---

## AST Chunking Algorithm

The core innovation of CodeMinder is the **Adaptive "Largest Valid Node"** chunking strategy, which ensures every code chunk is syntactically valid and semantically meaningful.

### Why AST-Based Chunking?

**Problem**: Traditional line-based chunking (e.g., "every 50 lines") creates invalid code snippets:
- Splits functions in the middle
- Breaks class definitions
- Cuts off control flow statements
- Loses semantic context

**Solution**: Parse code into Abstract Syntax Tree (AST) and chunk at logical boundaries:
- Functions and methods
- Classes
- Statements (if, for, while, try/except)
- Expressions (when statements are too large)

### Algorithm: "Largest Valid Node"

**Goal**: Create the largest possible chunks that fit within the token limit while maintaining syntactic validity.

**Steps**:

1. **Parse File**: Use Tree-sitter to generate AST
   ```python
   tree = parser.parse(source_code.encode())
   root_node = tree.root_node
   ```

2. **Traverse AST**: Depth-first search, tracking semantic path
   ```python
   def chunk_ast_node(node, file_path, max_tokens=2048, seq_num=0):
       code = node.text.decode()
       tokens = count_tokens(code)
       
       # Build context_path: filename:start_line-end_line
       start_line = node.start_point[0] + 1
       end_line = node.end_point[0] + 1
       context_path = f"{file_path}:{start_line}-{end_line}"
   ```

3. **Size Check**:
   - **If tokens ≤ limit**: Yield as single chunk (stop descending)
   - **If tokens > limit**: Descend into named children (split into smaller units)
   - **If atomic node > limit**: Yield with warning (rare: very long strings/comments)

4. **Context Path Construction**:
   - Format: `filename:start_line-end_line`
   - Example: `auth_service.py:42-58`
   - Enables LLM to understand code location and hierarchy

5. **Node Type Tracking**:
   - Store AST node type: `function_definition`, `class_definition`, `if_statement`, `expression`
   - Helps with result ranking and filtering

### Example: Chunking a Python File

**Input** (`auth_service.py`):
```python
class AuthService:
    def __init__(self, config):
        self.config = config
        self.jwt_handler = JWTHandler(config.secret_key)
    
    def authenticate(self, username, password):
        """Authenticate user with credentials."""
        user = self.user_repo.find_by_username(username)
        if not user:
            raise AuthenticationError('User not found')
        
        if not self.verify_password(password, user.password_hash):
            raise AuthenticationError('Invalid password')
        
        token = self.jwt_handler.create_token({'user_id': user.id})
        return {'token': token, 'user': user}
    
    def verify_password(self, password, hash):
        return bcrypt.checkpw(password.encode(), hash)
```

**Output Chunks** (assuming token limit 512):

| Chunk | Context Path | Node Type | Tokens | Code |
|-------|--------------|-----------|--------|------|
| 1 | `auth_service.py:1-4` | `function_definition` | 98 | `def __init__(self, config): ...` |
| 2 | `auth_service.py:6-17` | `function_definition` | 245 | `def authenticate(self, username, password): ...` |
| 3 | `auth_service.py:19-20` | `function_definition` | 42 | `def verify_password(self, password, hash): ...` |

**Benefits**:
- Each chunk is **syntactically valid** (can be parsed independently)
- Context path shows **exact location** in original file
- Node type enables **semantic filtering** (e.g., "find all functions")
- Token count ensures **embedding model compatibility**

### Handling Large Functions

If a single function exceeds the token limit, the algorithm recursively splits it:

**Example**: 3000-token function with token limit 2048

1. **Attempt**: Yield entire function → Too large (3000 > 2048)
2. **Descend**: Split into child nodes (statements, expressions)
3. **Yield**: Each statement/expression as separate chunk with sequence number

**Result**:
- Chunk 1: `function_name.py:42-58` (seq 0) - First N statements
- Chunk 2: `function_name.py:59-73` (seq 1) - Next N statements
- Chunk 3: `function_name.py:74-89` (seq 2) - Remaining statements

**Sequence Number Tracking**:
- `sequence_number = 0`: Unsplit chunk (entire function/class)
- `sequence_number ≥ 1`: Part of a split node (maintains ordering)

---

## Data Flow

### Indexing Flow (Startup or Manual Trigger)

```
1. Load Configuration (.codeminder.json)
   ↓
2. Connect to LanceDB (.codeminder/vector_db/)
   ↓
3. Load File Registry from LanceDB
   ↓
4. Scan Filesystem (recursive directory traversal)
   ↓
5. Compare Registry vs Filesystem (startup reconciliation)
   ├─ New files      → Queue for indexing
   ├─ Modified files → Queue for re-indexing (compare mtime vs last_indexed)
   └─ Deleted files  → Queue for deletion
   ↓
6. Process Queued Files (parallel, semaphore-limited)
   │
   ├─ For each NEW/MODIFIED file:
   │  ├─ Parse → AST (Tree-sitter)
   │  ├─ Chunk → CodeChunks (adaptive algorithm)
   │  ├─ Embed → Vectors (sentence-transformers)
   │  ├─ Store → LanceDB (atomic delete old + insert new)
   │  └─ Update File Registry (last_indexed, chunk_count)
   │
   └─ For each DELETED file:
      ├─ Delete chunks from code_chunks table
      └─ Delete file from file_registry table
   ↓
7. Return Summary (files_indexed, chunks_created, duration)
```

### Search Flow

```
1. Receive Query (natural language, e.g., "authentication logic")
   ↓
2. Embed Query → Vector (same model as code embeddings)
   ↓
3. Vector Search (ANN, cosine similarity)
   ├─ Query: code_chunks table
   ├─ Distance metric: cosine similarity
   └─ Limit: max_search_results (default 20)
   ↓
4. Rank Results (by similarity score, descending)
   ↓
5. Format Response
   ├─ source_code
   ├─ context_path (filename:start_line-end_line)
   ├─ similarity_score
   └─ node_type
   ↓
6. Return to MCP Client
```

---

## Storage Architecture

### LanceDB Schema

**Table: `file_registry`**

Persists file metadata to enable efficient startup reconciliation.

```python
{
    "file_id": "uuid",              # Primary key
    "absolute_path": "str",         # Indexed for O(1) lookup
    "relative_path": "str",         # For display in results
    "language": "str",              # "python", "javascript", etc.
    "last_modified": "timestamp",   # Filesystem mtime
    "last_indexed": "timestamp",    # When CodeMinder last processed this file
    "parse_status": "enum",         # SUCCESS | SYNTAX_ERROR | SKIPPED
    "error_message": "str",         # Details if parse_status != SUCCESS
    "chunk_count": "int"            # Number of chunks extracted
}
```

**Table: `code_chunks`**

Stores code snippets with their vector embeddings.

```python
{
    "chunk_id": "uuid",             # Primary key
    "file_id": "uuid",              # Foreign key to file_registry
    "source_code": "str",           # The actual code text
    "context_path": "str",          # "filename:start_line-end_line"
    "start_line": "int",            # Line number where chunk starts (1-indexed)
    "end_line": "int",              # Line number where chunk ends (1-indexed)
    "token_count": "int",           # Number of tokens in source_code
    "node_type": "str",             # AST node type (e.g., "function_definition")
    "sequence_number": "int",       # 0 for unsplit, 1+ for split chunks
    "language": "str",              # Inherited from file
    "vector": "array[float]",       # Embedding vector (768-dim for Jina)
    "created_at": "timestamp"       # When chunk was created
}
```

### Persistence Strategy

**On Startup**:
- Load `file_registry` from disk (LanceDB)
- Compare with filesystem to detect changes
- Only re-index files where `filesystem_mtime > last_indexed`

**On Re-Index**:
- Atomic operation: DELETE old chunks + INSERT new chunks
- Update `File.last_indexed` timestamp
- Prevents partial/inconsistent state

**On File Delete**:
- Cascade delete: Remove all chunks with matching `file_id`
- Remove file from `file_registry`

---

## Startup Reconciliation

**Problem**: How to efficiently update the index when the server was offline and files changed?

**Solution**: Compare persisted file registry with current filesystem state.

### Reconciliation Algorithm

```python
def reconcile_on_startup():
    # 1. Load persisted file registry from LanceDB
    registry = db.load_file_registry()
    
    # 2. Scan filesystem for current state
    filesystem_files = scan_directory(config.codebase_path)
    
    # 3. Compare and categorize changes
    actions = []
    
    # Check for NEW and MODIFIED files
    for fs_file in filesystem_files:
        registry_file = registry.get(fs_file.absolute_path)
        
        if not registry_file:
            actions.append(("INDEX", fs_file))  # New file
        elif fs_file.mtime > registry_file.last_indexed:
            actions.append(("REINDEX", fs_file))  # Modified file
    
    # Check for DELETED files
    for reg_file in registry.values():
        if reg_file.absolute_path not in filesystem_files:
            actions.append(("DELETE", reg_file))
    
    # 4. Execute actions in parallel (semaphore-limited)
    await process_actions(actions, concurrency_limit=4)
    
    # 5. Return summary
    return {
        "new_files": count("INDEX"),
        "modified_files": count("REINDEX"),
        "deleted_files": count("DELETE")
    }
```

### Performance Benefits

- **Incremental updates**: Only processes changed files
- **Fast startup**: Typical reconciliation takes 2-5 seconds for small changes
- **Crash recovery**: Server can resume indexing from last known state
- **Efficient storage**: File metadata persisted alongside embeddings

### Example Scenarios

**Scenario 1: First startup**
- Registry: Empty
- Filesystem: 142 files
- Action: INDEX all 142 files (full indexing)

**Scenario 2: Code changes while server offline**
- Registry: 142 files (last_indexed: 2025-12-09 10:00)
- Filesystem: 142 files (2 modified at 10:30, 1 new, 1 deleted)
- Actions:
  - REINDEX: 2 files (mtime > last_indexed)
  - INDEX: 1 file (new)
  - DELETE: 1 file (removed)
- Duration: ~3 seconds (only processes 4 files, not all 142)

---

## Search Pipeline

### Semantic Search Process

1. **Query Embedding**:
   ```python
   query_vector = embedder.encode([query])[0]  # Same model as code
   ```

2. **Vector Search**:
   ```python
   results = code_chunks_table.search(query_vector) \
       .metric("cosine") \
       .limit(config.max_search_results) \
       .to_pandas()
   ```

3. **Result Ranking**:
   - Primary: Cosine similarity score (higher = more relevant)
   - Secondary: Node type (functions/classes ranked higher than expressions)

4. **Response Formatting**:
   ```json
   {
       "results": [
           {
               "source_code": "def authenticate(...):",
               "context_path": "auth_service.py:42-58",
               "similarity_score": 0.89,
               "node_type": "function_definition",
               "language": "python"
           }
       ]
   }
   ```

### Search Quality

**Factors affecting search quality**:
- **Embedding model**: Better models → better semantic understanding
- **Token limit**: Larger chunks → more context, but less granular
- **Chunk size**: Smaller chunks → more precise matches, but less context
- **Query phrasing**: More specific queries → better results

---

## Performance Considerations

### Indexing Performance

**Target**: 5 seconds per 1,000 LOC

**Optimizations**:
- **Parallel processing**: 4 files simultaneously (configurable 1-16)
- **Batch embedding**: Process multiple chunks together
- **GPU acceleration**: Automatic GPU detection for embedding generation
- **Incremental updates**: Only re-index changed files

### Search Performance

**Target**: <1 second for codebases up to 100k LOC

**Optimizations**:
- **ANN search**: Approximate Nearest Neighbors (fast, ~95% accurate)
- **Columnar storage**: LanceDB optimized for vector operations
- **Indexed lookups**: O(1) file_id lookup during re-indexing

### Memory Management

**Embedding Model**: ~1GB RAM (jinaai/jina-embeddings-v2-base-code)
**Vector Storage**: ~1MB per 1,000 chunks (768-dim float32)
**Typical Usage**: <2GB total for 100k LOC codebase

**GPU Memory Management**:
- `torch.cuda.empty_cache()` after batch encoding
- Inference mode context manager (disables gradient computation)
- Periodic cleanup after large operations

---

## Design Decisions

### Why Tree-sitter for AST Parsing?

**Chosen**: Tree-sitter  
**Alternatives**: Python `ast` module, LibCST, rope/jedi

**Rationale**:
- ✅ **Multi-language**: Single API for Python, JS, TS (Phase 2 ready)
- ✅ **Incremental parsing**: Fast re-parsing when files change
- ✅ **Error recovery**: Continues parsing despite syntax errors
- ✅ **Query system**: Efficient extraction of specific node types

### Why sentence-transformers for Embeddings?

**Chosen**: sentence-transformers (local models)  
**Alternatives**: OpenAI API, Jina AI API, custom-trained

**Rationale**:
- ✅ **Privacy**: Code never leaves local machine
- ✅ **No API costs**: Free to run unlimited queries
- ✅ **No rate limits**: Process as fast as hardware allows
- ✅ **Configurable**: Users choose models based on hardware

### Why LanceDB for Vector Storage?

**Chosen**: LanceDB  
**Alternatives**: ChromaDB, FAISS, Qdrant

**Rationale**:
- ✅ **Embedded**: Runs in-process, no separate server
- ✅ **Persistent**: Survives restarts automatically
- ✅ **Performant**: Columnar format optimized for vectors
- ✅ **Simple**: First-class Python support

### Why Delete-and-Reparse for Updates?

**Chosen**: Atomic delete + re-index entire file  
**Alternative**: Incremental diff-based updates

**Rationale**:
- ✅ **Simplicity**: No complex diff logic to maintain
- ✅ **Correctness**: No risk of partial/inconsistent state
- ✅ **Performance**: Re-indexing a file takes <2 seconds
- ✅ **YAGNI**: Premature optimization avoided

### Why Persist File Registry?

**Chosen**: Store File metadata in LanceDB `file_registry` table  
**Alternative**: Re-scan filesystem on every startup

**Rationale**:
- ✅ **Efficiency**: Only re-index files that changed
- ✅ **Fast startup**: Reconciliation takes 2-5s vs full re-index (20-60s)
- ✅ **Crash recovery**: Can resume from last known state
- ✅ **Consistency**: Single source of truth (LanceDB)

---

## Future Enhancements

### User Story 2: Real-Time File Watching

**Status**: Planned (not yet implemented)

**Changes**:
- Add `watchfiles` integration for real-time change detection
- 500ms debounce to batch rapid edits
- Live updates without server restart

### Phase 2: Multi-Language Support

**Status**: Planned

**Changes**:
- Add Tree-sitter language bindings (JS, TS, Java, Go, etc.)
- Language detection from file extensions
- Language-specific chunking strategies

### Phase 3: Code Graph Overlay

**Status**: Planned

**Changes**:
- Parse import statements and function calls
- Build knowledge graph of code relationships
- Hybrid retrieval (vector + graph traversal)

---

## Conclusion

CodeMinder's architecture prioritizes:
- **Syntactic validity**: Every chunk is parseable code
- **Privacy**: Local processing, no external API calls
- **Efficiency**: Incremental updates, fast startup reconciliation
- **Simplicity**: Clear separation of concerns, maintainable codebase

For more details, see:
- [Configuration Reference](configuration.md)
- [Full Specification](../specs/001-code-rag-mcp/)
