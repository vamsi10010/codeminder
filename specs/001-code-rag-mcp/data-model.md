# Data Model: CodeMinder - Code RAG MCP Server

**Phase 1 Output** | **Date**: 2025-12-07

## Entity Relationship Overview

```
File (1) ──────< (N) CodeChunk (1) ────── (1) Embedding
  │                                              │
  └──────────────────────────────────────────────┴─── stored in LanceDB
```

---

## 1. File

Represents a source code file in the monitored codebase. **File metadata is persisted to LanceDB** in a separate table to enable startup reconciliation and efficient file_id lookups.

### Attributes

| Attribute | Type | Description | Constraints |
|-----------|------|-------------|-------------|
| `file_id` | UUID | Unique identifier | Primary key, generated |
| `absolute_path` | str | Full file system path | Required, unique |
| `relative_path` | str | Path relative to codebase root | Required |
| `language` | str | Programming language | Required, e.g., "python", "javascript" |
| `last_modified` | datetime | File modification timestamp | Required, updated on change |
| `last_indexed` | datetime | When file was last parsed/indexed | Required |
| `parse_status` | enum | SUCCESS \| SYNTAX_ERROR \| SKIPPED | Required |
| `error_message` | str | Details if parse_status != SUCCESS | Nullable |
| `chunk_count` | int | Number of chunks extracted from this file | Required, >= 0 |

### Relationships

- **Has many** CodeChunks (1:N) - A file is split into multiple logical code units

### Storage

- **Persisted in LanceDB**: File records are stored in a dedicated `file_registry` table
- **Primary key**: `file_id` (UUID)
- **Indexed by**: `absolute_path` for fast lookups during re-indexing
- **Survives restarts**: File registry is loaded from LanceDB on startup

### Business Rules

- `absolute_path` must be within configured `codebase_path` and must be unique
- `language` is detected from file extension (.py → "python")
- Files with `parse_status = SYNTAX_ERROR` may fall back to line-based chunking
- When file is deleted from filesystem, File record and all associated CodeChunks must be removed
- `last_modified` is synced from filesystem mtime on startup reconciliation
- `chunk_count` is updated atomically when file is re-indexed

---

## 2. CodeChunk

Represents a logical unit of code extracted via either AST parsing (function, class, method) or line-based splitting.

### Attributes

| Attribute | Type | Description | Constraints |
|-----------|------|-------------|-------------|
| `chunk_id` | UUID | Unique identifier | Primary key, generated |
| `file_id` | UUID | Foreign key to File | Required, indexed |
| `source_code` | str | The actual code text | Required, 1-8192 tokens |
| `context_path` | str | File path with line range | Required, e.g., "auth_service.py:42-58" |
| `start_line` | int | Line number where chunk starts (1-indexed) | Required, > 0 |
| `end_line` | int | Line number where chunk ends (1-indexed) | Required, >= start_line |
| `token_count` | int | Number of tokens in source_code | Required, > 0, <= 8192 |
| `node_type` | str | AST node type or "line_chunk" | Required, e.g., "function_definition", "if_statement", "expression" for ast strategy; "line_chunk" for line strategy |
| `sequence_number` | int | Sequence index for split nodes | Required, 0 for unsplit, 1+ for split parts |
| `language` | str | Inherited from File | Required |
| `created_at` | datetime | When chunk was created | Required |

### Relationships

- **Belongs to** File (N:1) - Each chunk comes from exactly one file
- **Has one** Embedding (1:1) - Each chunk has one vector representation

### Business Rules

- **context path construction**: Format is `filename:start_line-end_line`
  - **Filename**: Relative path from codebase root (e.g., `src/auth/service.py`)
  - **Line range**: `start_line-end_line` (1-indexed, inclusive)
  - **Examples**:
    - `auth_service.py:42-58` - function spanning lines 42 to 58
    - `src/utils/helpers.py:102-115` - nested function in subdirectory
    - `models/user.py:25-89` - class definition
- **Token count** is computed using tiktoken library before storage
- **AST strategy**: Chunks with `token_count > 2048` (default limit) are recursively split into child AST nodes (statements, expressions); each chunk must be syntactically valid (complete AST node)
- **Line strategy**: Files are split by raw token count using sliding window; chunks have `node_type = "line_chunk"` and may not be syntactically complete units
- When file is re-indexed, all old chunks are deleted atomically before new ones are inserted

### Example Data

```python
# Example 1: Function chunk
CodeChunk(
    chunk_id="550e8400-e29b-41d4-a716-446655440000",
    file_id="<file-uuid>",
    source_code="def authenticate(username, password):\n    # ...",
    context_path="auth_service.py:42-58",
    start_line=42,
    end_line=58,
    token_count=384,
    node_type="function_definition",
    sequence_number=0,
    language="python"
)

# Example 2: Statement chunk from split function
CodeChunk(
    chunk_id="660e8400-e29b-41d4-a716-446655440001",
    file_id="<file-uuid>",
    source_code="logger.error('Validation failed')\nlog_details(data)",
    context_path="auth_service.py:102-103",
    start_line=102,
    end_line=103,
    token_count=156,
    node_type="expression_statement",
    sequence_number=0,
    language="python"
)

# Example 3: For loop chunk
CodeChunk(
    chunk_id="770e8400-e29b-41d4-a716-446655440002",
    file_id="<file-uuid>",
    source_code="for item in data:\n    process(item)",
    context_path="auth_service.py:115-116",
    start_line=115,
    end_line=116,
    token_count=180,
    node_type="for_statement",
    sequence_number=0,
    language="python"
)

# Example 4: Line-based chunk (line strategy)
CodeChunk(
    chunk_id="880e8400-e29b-41d4-a716-446655440003",
    file_id="<file-uuid>",
    source_code="    return user\n\ndef validate_email(email):",
    context_path="auth_service.py:67-68",
    start_line=67,
    end_line=68,
    token_count=512,
    node_type="line_chunk",
    sequence_number=2,
    language="python"
)
```

---

## 3. Embedding

Represents the vector embedding of a CodeChunk, generated by sentence-transformers.

### Attributes

| Attribute | Type | Description | Constraints |
|-----------|------|-------------|-------------|
| `embedding_id` | UUID | Unique identifier | Primary key, generated |
| `chunk_id` | UUID | Foreign key to CodeChunk | Required, unique (1:1), indexed |
| `vector` | float[] | Embedding vector (dimensions vary by model) | Required, 768 dims (jinaai/jina-embeddings-v2-base-code default) or 384 dims (MiniLM) |
| `model_version` | str | Embedding model identifier | Required, e.g., "jinaai/jina-embeddings-v2-base-code" |
| `created_at` | datetime | When embedding was generated | Required |

### Relationships

- **Belongs to** CodeChunk (1:1) - Each embedding corresponds to exactly one chunk

### Business Rules

- `vector` is generated locally using sentence-transformers with `source_code` as input
- `model_version` is stored to detect when re-embedding is needed (e.g., model upgrade or config change)
- Embeddings are stored in LanceDB for efficient similarity search
- When CodeChunk is deleted, its Embedding is also deleted (cascade)
- Vector dimensions determined by configured model (e.g., 768 for Jina, 384 for MiniLM)

### Storage Implementation (LanceDB)

```python
# LanceDB code_chunks table schema
chunk_schema = {
    "chunk_id": str,              # UUID as string
    "file_id": str,               # Foreign key to file_registry
    "file_path": str,             # Denormalized for display
    "relative_path": str,         # Relative to codebase root
    "source_code": str,           # Code text
    "context_path": str,          # filename:start_line-end_line
    "start_line": int,
    "end_line": int,
    "token_count": int,
    "node_type": str,
    "language": str,
    "vector": vector(dim),        # Variable dimensions based on model
    "model_version": str,
    "created_at": timestamp
}

# LanceDB file_registry table schema (NEW)
file_schema = {
    "file_id": str,               # UUID as string, primary key
    "absolute_path": str,         # Full filesystem path, indexed
    "relative_path": str,         # Path relative to codebase root
    "language": str,              # Programming language
    "last_modified": timestamp,   # From filesystem mtime
    "last_indexed": timestamp,    # When indexing completed
    "parse_status": str,          # SUCCESS | SYNTAX_ERROR | SKIPPED
    "error_message": str,         # Nullable
    "chunk_count": int            # Number of chunks for this file
}
```

---

## 4. Configuration (not persisted entity, loaded from .codeminder.json)

Application configuration loaded at startup.

### Attributes

| Attribute | Type | Description | Default |
|-----------|------|-------------|------|
| `codebase_path` | str | Root directory to index | "." (current directory) |
| `chunking_strategy` | str | Chunking method: "ast" or "line" | "ast" |
| `embedding_model` | str | HuggingFace model ID | "jinaai/jina-embeddings-v2-base-code" |
| `token_limit` | int | Max tokens per chunk | 2048 |
| `max_search_results` | int | Number of results to return | 20 |
| `concurrency_limit` | int | Parallel file processing limit | 4 |
| `debounce_ms` | int | File change debounce delay (ms) | 500 |
| `log_level` | str | Logging verbosity | "INFO" |
| `persist_index` | bool | Enable disk persistence | true |
| `excluded_patterns` | list[str] | File patterns to skip | ["*.pyc", "__pycache__", ".git"] |

---

## Indexing Lifecycle (State Transitions)

### Server Startup Reconciliation (CRITICAL)

**Purpose**: Synchronize persisted File registry with current filesystem state

**Flow**:
```python
1. Load Configuration from .codeminder.json
   └─> Returns: Config object

2. VectorDB.connect() → Connects to LanceDB
   └─> Opens/creates: file_registry table, code_chunks table

3. VectorDB.load_file_registry() → dict[absolute_path, File]
   └─> Returns: All File records from file_registry table
   └─> Data: file_id, paths, language, timestamps, parse_status, chunk_count

4. Scanner.scan(codebase_path) → list[absolute_path]
   └─> Returns: All code files on filesystem (respects excluded_patterns)

5. Reconcile filesystem vs registry:
   
   For each file in filesystem:
     If file NOT in registry:
       └─> New file → Add to reconciliation queue (action: INDEX)
     
     If file IN registry:
       fs_mtime = Path(file).stat().st_mtime
       If fs_mtime > file.last_indexed:
         └─> Modified file → Add to queue (action: REINDEX)
       Else:
         └─> Up-to-date → Skip
   
   For each file in registry:
     If file NOT on filesystem:
       └─> Deleted file → Add to queue (action: DELETE)

6. IndexingService.process_reconciliation_queue()
   └─> Process actions in parallel (up to concurrency_limit)
   └─> For INDEX/REINDEX: parse → chunk → embed → store
   └─> For DELETE: remove File + cascade delete chunks

7. FileWatcher.start() → Begin monitoring for changes
```

**Component Communication**:
- **VectorDB** provides: `load_file_registry()` → dict[str, File]
- **Scanner** provides: `scan()` → list[str] (file paths)
- **Reconciler** (in IndexingService): Compares registry vs filesystem
- **IndexingService** orchestrates: parse → chunk → embed → store pipeline

**Data Objects Passed**:
- `File` objects: Passed from VectorDB → Reconciler → IndexingService
- `CodeChunk` list: Passed from Chunker → Embedder → VectorDB
- `Embedding` vectors: Passed from Embedder → VectorDB (merged with chunks)

---

### Initial Indexing (`index_codebase` tool)

**Trigger**: AI assistant calls MCP tool or first-time startup

**Flow**:
```python
1. Scanner.scan(codebase_path)
   └─> Returns: list[absolute_path] of code files

2. For each file (parallel, up to concurrency_limit):
   
   a. Create File record:
      file = File(
          file_id=uuid4(),
          absolute_path=path,
          relative_path=relative_to(codebase_path),
          language=detect_language(path),
          last_modified=Path(path).stat().st_mtime,
          parse_status=ParseStatus.PROCESSING
      )
      VectorDB.upsert_file(file)  # Persist immediately
   
   b. ASTParser(file.absolute_path)
      └─> Returns: tree, source_bytes
   
   c. Chunker.chunk(tree, source_bytes)
      └─> Returns: list[CodeChunk] with file_id = file.file_id
   
   d. Embedder.embed([chunk.source_code for chunk in chunks])
      └─> Returns: list[vector] (same order as chunks)
   
   e. VectorDB.insert_chunks(chunks, embeddings)
      └─> Stores chunks + vectors in code_chunks table
   
   f. Update File record:
      file.parse_status = ParseStatus.SUCCESS
      file.chunk_count = len(chunks)
      file.last_indexed = datetime.now()
      VectorDB.upsert_file(file)  # Persist updates

3. Return summary:
   {
     "files_indexed": count,
     "total_chunks": sum(chunk_counts),
     "status": "success"
   }
```

**Component Communication**:
- **IndexingService** calls: Scanner → ASTParser → Chunker → Embedder → VectorDB
- **VectorDB** methods: `upsert_file(File)`, `insert_chunks(list[CodeChunk], list[vector])`

**Data Objects Passed**:
- Scanner → IndexingService: `list[str]` (file paths)
- ASTParser → Chunker: `tree`, `source_bytes`
- Chunker → Embedder: `list[CodeChunk]`
- Embedder → VectorDB: `list[vector]`
- IndexingService → VectorDB: `File`, `list[CodeChunk]`

---

### Re-indexing on File Change (file watcher)

**Trigger**: File watcher detects modification (after 500ms debounce)

**Flow**:
```python
1. FileWatcher detects change: (Change.modified, absolute_path)
   └─> After 500ms debounce, triggers re-index

2. VectorDB.get_file_by_path(absolute_path)
   └─> Returns: File object (includes file_id)
   └─> If not found: Treat as new file (call INDEX flow)

3. ATOMIC RE-INDEX (with lock):
   
   async with reindex_lock:
     a. VectorDB.delete_chunks_by_file_id(file.file_id)
        └─> DELETE FROM code_chunks WHERE file_id = ?
     
     b. ASTParser(file.absolute_path)
        └─> Returns: tree, source_bytes
     
     c. Chunker.chunk(tree, source_bytes)
        └─> Returns: list[CodeChunk] (new chunks with same file_id)
     
     d. Embedder.embed([chunk.source_code for chunk in chunks])
        └─> Returns: list[vector]
     
     e. VectorDB.insert_chunks(chunks, embeddings)
        └─> INSERT new chunks + vectors
     
     f. Update File record:
        file.last_modified = Path(path).stat().st_mtime
        file.last_indexed = datetime.now()
        file.chunk_count = len(chunks)
        VectorDB.upsert_file(file)

4. Release lock → Search queries can proceed
```

**Component Communication**:
- **FileWatcher** calls: VectorDB.get_file_by_path() → IndexingService.reindex_file()
- **IndexingService** coordinates: delete → parse → chunk → embed → store

**Data Objects Passed**:
- FileWatcher → IndexingService: `absolute_path` (str)
- VectorDB → IndexingService: `File` object
- IndexingService uses same pipeline as initial indexing

**Consistency Guarantee**: Lock ensures search never sees mixed old/new chunks

---

### File Deletion (file watcher)

**Trigger**: File watcher detects deletion event

**Flow**:
```python
1. FileWatcher detects: (Change.deleted, absolute_path)

2. VectorDB.get_file_by_path(absolute_path)
   └─> Returns: File object (or None if already deleted)

3. If File exists:
   
   async with reindex_lock:
     a. VectorDB.delete_chunks_by_file_id(file.file_id)
        └─> DELETE FROM code_chunks WHERE file_id = ?
     
     b. VectorDB.delete_file(file.file_id)
        └─> DELETE FROM file_registry WHERE file_id = ?
```

**Component Communication**:
- **FileWatcher** calls: VectorDB.get_file_by_path() → VectorDB.delete_file()

**Data Objects Passed**:
- FileWatcher → VectorDB: `absolute_path` (str)
- VectorDB returns: `File` object (for file_id lookup)

---

## Search Flow (Data Retrieval)

1. User invokes `search_code(query="authentication logic", limit=20)`
2. Generate query embedding: `query_vector = embed(query)`
3. LanceDB similarity search:
   ```python
   results = table.search(query_vector).limit(20).to_pandas()
   ```
4. For each result:
   - Extract `chunk_id`, `file_path`, `code`, `context_path`, `start_line`, `end_line`
   - Compute similarity score (cosine distance)
5. Return ranked list of CodeChunk metadata + code snippets

---

## Data Persistence Strategy

### In-Memory (during runtime)

- **File registry cache**: `dict[absolute_path, File]` loaded from LanceDB
  - Purpose: Fast lookups during re-indexing without DB query
  - Synced: Updates are persisted to LanceDB immediately
- **Active re-indexing queue**: `asyncio.Queue` for file change events
- **Reindex lock**: `asyncio.Lock` to prevent concurrent chunk updates

### Disk Persistence (LanceDB at `.codeminder/vector_db/`)

- **`file_registry` table**: All File metadata
  - Indexed by: `file_id` (primary), `absolute_path` (for lookups)
  - Purpose: Track which files have been indexed and when
  - Survives: Server restarts, enables startup reconciliation

- **`code_chunks` table**: All CodeChunk + Embedding vectors
  - Indexed by: `chunk_id` (primary), `file_id` (foreign key)
  - Purpose: Store code chunks with semantic embeddings
  - Survives: Server restarts

- **Configuration**: `.codeminder.json` in codebase root
- **Logs**: `.codeminder/codeminder.log` (structured JSON logs)

### Startup Behavior

**On first run** (no existing LanceDB):
1. Create `file_registry` and `code_chunks` tables
2. Scan filesystem and index all code files
3. Persist all File + CodeChunk records

**On subsequent runs** (LanceDB exists):
1. Load `file_registry` from LanceDB into memory
2. Scan filesystem to detect changes (new, modified, deleted files)
3. Reconcile: Re-index only files that changed since `last_indexed`
4. Update File records with new timestamps

**Result**: Server always starts with accurate index reflecting current filesystem state

---

## Validation Rules

### At File Indexing

- File must exist and be readable
- File size must be < 10MB (warn if larger, still process)
- File must have recognized extension (.py for Phase 1)

### At Chunk Creation

- `source_code` must not be empty
- `token_count` must be > 0 and <= 8192 (Jina model limit)
- `start_line` <= `end_line`
- `context_path` must be well-formed (no empty segments)

### At Search

- `query` string must not be empty
- `limit` must be > 0 and <= 100

---

## Performance Considerations

### Indexing Throughput

- Target: 5 seconds per 1,000 LOC
- Bottleneck: Embedding API calls (batch embeddings where possible)
- Parallelism: Default 4 concurrent files (tunable)

### Search Latency

- Target: < 1 second for 100k LOC codebase
- LanceDB ANN search: O(log N) complexity
- Top-20 results: No significant overhead

### Memory Usage

- In-memory index: ~50MB per 10k chunks (768 floats per chunk)
- Target: < 2GB RAM for 100k LOC codebase
- Disk persistence: ~100MB per 10k chunks (with metadata)

---

## Component Interaction & Data Flow

### Key Components

| Component | Responsibility | Inputs | Outputs |
|-----------|---------------|--------|----------|
| **VectorDB** | Persist/retrieve File + CodeChunk data | File, CodeChunk, query_vector | File, CodeChunk, search results |
| **Scanner** | Find code files on filesystem | codebase_path, excluded_patterns | list[absolute_path] |
| **ASTParser** | Parse file into AST | file_path | tree, source_bytes, language |
| **Chunker** | Split AST into chunks | tree, source_bytes, file_id | list[CodeChunk] |
| **Embedder** | Generate embeddings | list[source_code] | list[vector] |
| **IndexingService** | Orchestrate indexing pipeline | list[file_path] | indexing summary |
| **FileWatcher** | Detect filesystem changes | codebase_path | file change events |
| **Searcher** | Execute semantic search | query string | ranked search results |
| **MCPServer** | Expose tools to AI assistants | MCP requests | MCP responses |

### Data Object Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                        SERVER STARTUP                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    VectorDB.load_file_registry()
                              │
                              ├─> File objects → In-memory cache
                              │
                              ▼
                      Scanner.scan(codebase_path)
                              │
                              ├─> list[file_path]
                              │
                              ▼
                   Reconcile: Compare mtime vs last_indexed
                              │
                              ├─> Files to reindex/index/delete
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                     INDEXING PIPELINE                            │
└──────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   New File            Modified File          Deleted File
        │                     │                     │
        ├─> Create File       ├─> Load File        ├─> Load File
        │   object            │   from cache        │   from cache
        │                     │                     │
        │                     ├─> Delete old        ├─> Delete File
        │                     │   chunks            │   + chunks
        │                     │                     │
        ├─────────────────────┘                     │
        │                                           │
        ▼                                           │
   ASTParser(file_path)                             │
        │                                           │
        ├─> tree, source_bytes                      │
        │                                           │
        ▼                                           │
   Chunker.chunk(tree, file_id)                     │
        │                                           │
        ├─> list[CodeChunk]                         │
        │                                           │
        ▼                                           │
   Embedder.embed(source_codes)                     │
        │                                           │
        ├─> list[vector]                            │
        │                                           │
        ▼                                           │
   VectorDB.insert_chunks(chunks, vectors)          │
        │                                           │
        ├─> Persist to LanceDB                      │
        │                                           │
        ▼                                           │
   VectorDB.upsert_file(file)                       │
        │                                           │
        ├─> Update file_registry table              │
        │                                           │
        └─────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                      FILE WATCHER                                │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ├─> Monitor filesystem changes
                              ├─> Debounce 500ms
                              ├─> Trigger re-index pipeline
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                    SEARCH PIPELINE                               │
└──────────────────────────────────────────────────────────────────┘
                              │
                     MCP Tool: search_code(query)
                              │
                              ├─> Embedder.embed(query)
                              │   └─> query_vector
                              │
                              ├─> VectorDB.search(query_vector)
                              │   └─> list[CodeChunk + similarity]
                              │
                              ├─> Searcher.rank_and_format(results)
                              │   └─> Ranked results with context
                              │
                              ▼
                        Return to AI assistant
```

### Method Call Sequences

**Startup Reconciliation**:
```python
# VectorDB provides
file_registry = vector_db.load_file_registry()
  → Returns: dict[absolute_path, File]

# Scanner provides
fs_files = scanner.scan(codebase_path)
  → Returns: list[absolute_path]

# IndexingService reconciles
actions = indexing_service.reconcile(file_registry, fs_files)
  → For each action: INDEX | REINDEX | DELETE

# IndexingService processes
for action in actions:
    if action.type == INDEX or REINDEX:
        chunks = indexing_service.index_file(action.file_path)
          → Calls: parser → chunker → embedder → vector_db.insert_chunks()
          → Calls: vector_db.upsert_file(File)
    elif action.type == DELETE:
        vector_db.delete_file(action.file_id)
```

**File Re-indexing (File Watcher)**:
```python
# FileWatcher triggers
file_watcher.on_change(file_path)
  → Calls: vector_db.get_file_by_path(file_path)
  → Returns: File (includes file_id)
  → Calls: indexing_service.reindex_file(file)

# IndexingService coordinates
indexing_service.reindex_file(file):
  async with reindex_lock:
    → Calls: vector_db.delete_chunks_by_file_id(file.file_id)
    → Calls: parser.parse(file.absolute_path)
    → Calls: chunker.chunk(tree, file.file_id)
    → Calls: embedder.embed(chunks)
    → Calls: vector_db.insert_chunks(chunks, vectors)
    → Calls: vector_db.upsert_file(file)  # Update timestamps
```

**Search Query**:
```python
# MCP Server receives
mcp_server.search_code(query, limit):
  → Calls: searcher.search(query, limit)

# Searcher coordinates
searcher.search(query, limit):
  → Calls: embedder.embed([query])
  → Returns: query_vector
  → Calls: vector_db.search(query_vector, limit)
  → Returns: list[{chunk_id, source_code, context_path, similarity, ...}]
  → Formats: Adds file paths, ranks by similarity
  → Returns: Ranked results to MCP Server
```

---

## Summary

The data model is designed for:
- **Syntactic integrity**: Chunks are complete AST nodes
- **Context preservation**: Hierarchical paths enable semantic understanding
- **Performance**: Embedded LanceDB + parallel processing
- **Simplicity**: Delete-and-reparse strategy (no complex diff logic)
- **Persistence**: File registry + chunks survive restarts via disk-backed LanceDB
- **Consistency**: Startup reconciliation ensures index reflects current filesystem state
- **Efficiency**: Only changed files are re-indexed, not entire codebase

All entities are validated at creation and follow clear lifecycle rules.
