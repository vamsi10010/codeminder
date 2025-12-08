# Research: CodeMinder - Code RAG MCP Server

**Phase 0 Output** | **Date**: 2025-12-07

## Research Tasks Completed

This document consolidates findings for all NEEDS CLARIFICATION items from the technical context and design decisions that required investigation.

---

## 1. Tree-sitter for Multi-Language AST Parsing

**Decision**: Use Tree-sitter with Python bindings (tree-sitter + tree-sitter-python)

**Rationale**:
- Incremental parsing: Fast re-parsing when files change (critical for file watcher)
- Multi-language support: Single API for Python, JavaScript, TypeScript (Phase 2 ready)
- Robust error recovery: Continues parsing even with syntax errors
- Query system: Can extract specific node types (functions, classes) efficiently

**Alternatives Considered**:
- Python's `ast` module: Python-only, would require complete rewrite for multi-language
- LibCST: Python-only, more complex API for our needs
- rope/jedi: Designed for IDE features, overkill for chunking

**Implementation Notes**:
- Install tree-sitter and tree-sitter-python via pip
- Parse files into AST, traverse depth-first to identify logical boundaries
- Node types of interest: `function_definition`, `class_definition`, `module`

---

## 2. sentence-transformers for Local Code Embeddings

**Decision**: Use sentence-transformers with configurable models for local embedding generation

**Rationale**:
- **No API dependency**: Runs completely offline, no external service required
- **Privacy**: Code never leaves local machine (critical for proprietary codebases)
- **Configurable**: Users can select models based on their hardware capabilities
- **No rate limits**: Process as much code as needed without API quotas
- **Cost**: Free to run, no per-request charges

**Recommended Models**:
- **Default**: `jinaai/jina-embeddings-v2-base-code` (768-dim, 8k context, ~1GB RAM)
- **Lightweight**: `microsoft/codebert-base` (768-dim, 512 tokens, ~500MB RAM)
- **High-quality**: `Salesforce/codet5-base` (768-dim, code-optimized, ~900MB RAM)
- **Budget**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, fast, ~80MB RAM)

**Alternatives Considered**:
- Jina AI API: Requires API key, network dependency, costs money at scale
- OpenAI embeddings: Same issues plus not code-optimized
- Custom-trained model: Too complex for initial release

**Implementation Notes**:
- Install sentence-transformers via pip (includes PyTorch)
- Model auto-downloads on first run to `~/.cache/huggingface/`
- Batch embedding for efficiency (process multiple chunks together)
- Device selection: Auto-detect GPU if available, fallback to CPU

**Code Example**:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    config.embedding_model,
    device='cuda' if torch.cuda.is_available() else 'cpu'
)
embeddings = model.encode(code_chunks, batch_size=32, show_progress_bar=True)
```

---

## 3. LanceDB for Embedded Vector Storage

**Decision**: Use LanceDB with in-memory operation and disk persistence

**Rationale**:
- **Embedded**: Runs in-process, no separate server (simpler deployment)
- **Persistence**: Built-in disk storage to `.codeminder/vector_db/` (survives restarts)
- **Performance**: Columnar format optimized for vector similarity search
- **Python-native**: First-class Python support with pandas/pyarrow integration
- **License**: Apache 2.0

**Alternatives Considered**:
- ChromaDB: Similar embedded DB, but LanceDB has better performance for large datasets
- FAISS: In-memory only, would lose index on restart (requires custom persistence)
- Qdrant: Client-server architecture, overkill for local tool

**Implementation Notes**:
- Create database: `lance.connect(".codeminder/vector_db/")`
- Table schema: `chunk_id`, `file_path`, `code`, `context_path`, `vector`, `metadata`
- Use ANN (Approximate Nearest Neighbors) search with cosine similarity

**Code Example**:
```python
import lancedb
db = lancedb.connect(".codeminder/vector_db/")
table = db.create_table("code_chunks", data=chunks_df)
results = table.search(query_vector).limit(20).to_pandas()
```

---

## 4. FastMCP for Model Context Protocol Server

**Decision**: Use FastMCP (Python library) for MCP server implementation

**Rationale**:
- **Decorator-based**: Simple `@mcp.tool()` syntax for defining tools
- **Type safety**: Pydantic models for request/response validation
- **Built-in JSON-RPC**: Handles MCP protocol details automatically
- **Async support**: Non-blocking I/O for file watching and search
- **Active development**: Maintained by Anthropic

**Alternatives Considered**:
- Raw JSON-RPC implementation: Too low-level, reinventing the wheel
- Custom MCP library: Unnecessary complexity, FastMCP is standardized

**Implementation Notes**:
```python
from fastmcp import FastMCP

mcp = FastMCP("CodeMinder")

@mcp.tool()
async def search_code(query: str, limit: int = 20) -> list[dict]:
    """Search codebase for relevant code snippets."""
    # Implementation here
    pass

@mcp.tool()
async def index_codebase() -> dict:
    """Trigger initial indexing of configured codebase."""
    # Implementation here
    pass
```

---

## 5. Watchfiles for File System Monitoring

**Decision**: Use watchfiles (Rust-based Python library) for file watching

**Rationale**:
- **Performance**: Rust implementation is faster than pure-Python alternatives
- **Debouncing**: Built-in support for change batching (prevents thrashing)
- **Cross-platform**: Works on Linux, macOS, Windows (uses native APIs)
- **Simple API**: Async iterator pattern integrates well with FastMCP

**Alternatives Considered**:
- watchdog: Pure Python, slower, more complex API
- Built-in OS modules (inotify, FSEvents): Platform-specific, low-level

**Implementation Notes**:
```python
from watchfiles import awatch

async def watch_codebase(path: str):
    async for changes in awatch(path, debounce=500):  # 500ms debounce
        for change_type, file_path in changes:
            if change_type == Change.modified:
                await reindex_file(file_path)
```

---

## 6. Adaptive AST Chunking Algorithm

**Decision**: Implement "Largest Valid Node" strategy with context tagging

**Algorithm**:
1. **Parse**: Generate AST using Tree-sitter
2. **Traverse**: Depth-first search starting from root
3. **Size Check**:
   - If node's token count ≤ limit (2048): Yield as single chunk, stop descending
   - If node > limit: Descend into named children (split class into methods, split function into statements)
   - If statement/expression > limit: Descend further (split compound statements, expressions)
   - If atomic node > limit: Yield with warning (rare case: extremely long strings or comments)
4. **Context Tagging**: Prepend each chunk with `File: path.py > Class: Name > Method: func[N]` where [N] is sequence number for split nodes
5. **Chunk Identification**: Assign unique IDs and track AST node type (function_definition, if_statement, expression, etc.)

**Rationale**:
- **Syntactic validity**: Each chunk is a complete, parseable AST node (function, class, statement, or expression)
- **Adaptive granularity**: Splits large functions into individual statements or expression blocks when needed
- **Context preservation**: LLM understands code hierarchy from tags including sequence numbers for split nodes

**Implementation Pseudocode**:
```python
def chunk_ast_node(node, context_path="", max_tokens=2048, seq_num=0):
    code = node.text.decode()
    tokens = count_tokens(code)
    
    if tokens <= max_tokens:
        yield CodeChunk(
            code=code,
            context_path=f"{context_path}[{seq_num}]" if seq_num > 0 else context_path,
            node_type=node.type,
            start_line=node.start_point[0],
            end_line=node.end_point[0],
            sequence_number=seq_num
        )
    elif node.named_children:
        # Recursively split into child nodes (methods, statements, expressions)
        for idx, child in enumerate(node.named_children):
            child_name = getattr(child, 'name', None) or f"{child.type}"
            child_context = f"{context_path} > {child_name}"
            yield from chunk_ast_node(child, child_context, max_tokens, idx)
    else:
        # Atomic node exceeding limit (rare: very long string/comment)
        logger.warning(f"Atomic node exceeds limit: {context_path}")
        yield CodeChunk(
            code=code,
            context_path=f"{context_path}[OVERSIZED]",
            node_type=node.type,
            start_line=node.start_point[0],
            end_line=node.end_point[0],
            sequence_number=0
        )
```

---

## 7. Debouncing Strategy for File Changes

**Decision**: 500ms debounce window with "last change wins" semantics

**Rationale**:
- **Prevents thrashing**: Auto-save every 2 seconds triggers only 1 re-index
- **Balances latency**: 500ms is imperceptible to users but batches rapid edits
- **Implementation**: Watchfiles library has built-in `debounce` parameter

**Alternatives Considered**:
- No debouncing: Would cause excessive re-indexing (bad for performance)
- 1 second debounce: Too slow, user would notice delay
- 200ms debounce: Too fast, wouldn't batch auto-save effectively

---

## 8. Parallel Re-indexing Strategy

**Decision**: Configurable concurrency limit (default 4, range 1-16) using asyncio.Semaphore

**Rationale**:
- **Batch operations**: Git checkout with 50 files processes 4 at a time
- **Resource control**: Prevents overwhelming CPU/memory on large changes
- **Configurable**: Users can tune based on their hardware

**Implementation**:
```python
import asyncio

semaphore = asyncio.Semaphore(config.concurrency_limit)

async def reindex_file(file_path: str):
    async with semaphore:
        # Parse, chunk, embed, store
        pass
```

---

## 9. Configuration File Format

**Decision**: `.codeminder.json` in codebase root with sensible defaults

**Schema**:
```json
{
  "codebase_path": ".",
  "embedding_model": "jinaai/jina-embeddings-v2-base-code",
  "token_limit": 2048,
  "max_search_results": 20,
  "concurrency_limit": 4,
  "debounce_ms": 500,
  "log_level": "INFO",
  "persist_index": true
}
```

**Rationale**:
- JSON: Widely understood, easy to edit
- Sensible defaults: Works out-of-box for most use cases
- `embedding_model`: Any HuggingFace model ID (allows user customization)

---

## 10. Structured Error Codes

**Decision**: Define error code enum with recovery suggestions

**Error Code Categories**:
- `CONFIG_ERROR`: Invalid `.codeminder.json` (show validation errors)
- `PARSE_ERROR`: Syntax error in source file (fallback to line-based chunking)
- `EMBEDDING_ERROR`: Failed to generate embeddings (model download/loading failure, GPU OOM)
- `DB_UNAVAILABLE`: Vector database connection failed (check `.codeminder/` permissions)
- `INDEX_NOT_READY`: Search requested before initial indexing complete (call index_codebase first)
- `SEARCH_ERROR`: Search operation failed (invalid query, database error)
- `WATCHER_ERROR`: File watcher initialization failed (check file permissions)

**Response Format**:
```json
{
  "error": {
    "code": "PARSE_ERROR",
    "message": "Failed to parse file due to syntax errors",
    "context": {
      "file": "src/broken.py",
      "line": 42,
      "details": "Unexpected token"
    },
    "recovery": "Fix syntax errors or exclude file from indexing"
  }
}
```

---

## Summary of Technical Decisions

| Component | Technology | Key Benefit |
|-----------|-----------|-------------|
| AST Parsing | Tree-sitter | Multi-language, incremental, error-resilient |
| Embeddings | sentence-transformers | Local, private, configurable models |
| Vector DB | LanceDB | Embedded, persistent, performant |
| MCP Server | FastMCP | Decorator-based, async, type-safe |
| File Watcher | Watchfiles | Rust-fast, debouncing, cross-platform |
| Chunking | Adaptive AST | Syntactic integrity, context preservation |
| Parallelism | asyncio.Semaphore | Configurable concurrency, resource control |

All research tasks complete. Ready to proceed to Phase 1 (data model and contracts).
