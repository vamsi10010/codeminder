# MCP Tool Contracts: CodeMinder

**Phase 1 Output** | **Date**: 2025-12-07

This document defines the Model Context Protocol (MCP) tool interfaces for CodeMinder.

---

## Tool 1: `index_codebase`

Triggers initial indexing of the configured codebase directory.

### Request

```json
{
  "name": "index_codebase",
  "arguments": {}
}
```

**Parameters**: None (uses configuration from `.codeminder.json`)

### Response (Success)

```json
{
  "status": "success",
  "summary": {
    "files_indexed": 142,
    "chunks_created": 3891,
    "duration_seconds": 23.4,
    "errors": []
  },
  "details": {
    "codebase_path": "/home/user/project",
    "total_lines_of_code": 45230,
    "languages": {
      "python": 142
    }
  }
}
```

### Response (Partial Success with Errors)

```json
{
  "status": "partial_success",
  "summary": {
    "files_indexed": 140,
    "files_failed": 2,
    "chunks_created": 3780,
    "duration_seconds": 24.1,
    "errors": [
      {
        "file": "src/broken.py",
        "error_code": "PARSE_ERROR",
        "message": "Syntax error at line 42",
        "recovery": "Fix syntax errors or exclude file from indexing"
      },
      {
        "file": "src/huge.py",
        "error_code": "PARSE_WARNING",
        "message": "File size 12MB exceeds recommended 10MB limit",
        "recovery": "Consider splitting large files"
      }
    ]
  }
}
```

### Response (Failure)

```json
{
  "error": {
    "code": "CONFIG_ERROR",
    "message": "Invalid configuration file",
    "context": {
      "config_path": ".codeminder.json",
      "validation_errors": [
        "codebase_path: field required",
        "token_limit: must be positive integer"
      ]
    },
    "recovery": "Fix .codeminder.json and retry"
  }
}
```

### Behavior

**First-time indexing** (no existing LanceDB):
- Scans `codebase_path` recursively for code files
- Skips files matching `excluded_patterns` (.pyc, __pycache__, .git, etc.)
- Processes files in parallel up to `concurrency_limit`
- Creates `File`, `CodeChunk`, and `Embedding` records
- Persists File metadata to `file_registry` table in LanceDB
- Returns summary with counts and any non-fatal errors

**Subsequent runs** (existing LanceDB):
- Automatically runs **startup reconciliation** on server initialization:
  1. Loads File registry from LanceDB
  2. Scans filesystem to detect changes
  3. Compares filesystem mtime vs `last_indexed` timestamp
  4. Re-indexes only modified/new files, deletes removed files
  5. Updates File records with new timestamps
- Manual `index_codebase` call forces full re-scan (useful for debugging)
- Index survives server restarts via LanceDB persistence

### Performance

- Target: 5 seconds per 1,000 LOC
- Example: 100k LOC codebase → ~8 minutes initial indexing
- Concurrent processing reduces total time proportionally

---

## Tool 2: `search_code`

Searches the indexed codebase for code snippets matching a natural language query.

### Request

```json
{
  "name": "search_code",
  "arguments": {
    "query": "authentication logic using JWT tokens",
    "limit": 20
  }
}
```

**Parameters**:
- `query` (string, required): Natural language description of desired code
- `limit` (integer, optional, default=20): Maximum number of results to return (1-100)

### Response (Success)

```json
{
  "status": "success",
  "query": "authentication logic using JWT tokens",
  "results": [
    {
      "rank": 1,
      "similarity_score": 0.89,
      "file": {
        "path": "src/auth/jwt_handler.py",
        "relative_path": "src/auth/jwt_handler.py"
      },
      "chunk": {
        "context_path": "src/auth/jwt_handler.py:42-50",
        "code": "def verify_token(self, token: str) -> dict:\n    \"\"\"Verify JWT token and return payload.\"\"\"\n    try:\n        payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])\n        return payload\n    except jwt.ExpiredSignatureError:\n        raise AuthenticationError('Token has expired')\n    except jwt.InvalidTokenError:\n        raise AuthenticationError('Invalid token')",
        "start_line": 42,
        "end_line": 50,
        "token_count": 156
      }
    },
    {
      "rank": 2,
      "similarity_score": 0.85,
      "file": {
        "path": "src/auth/middleware.py",
        "relative_path": "src/auth/middleware.py"
      },
      "chunk": {
        "context_path": "src/auth/middleware.py:15-24",
        "code": "def authenticate_request(request: Request) -> User:\n    \"\"\"Extract and verify JWT from request headers.\"\"\"\n    token = request.headers.get('Authorization')\n    if not token or not token.startswith('Bearer '):\n        raise AuthenticationError('Missing or invalid Authorization header')\n    token = token[7:]  # Remove 'Bearer ' prefix\n    handler = JWTHandler()\n    payload = handler.verify_token(token)\n    return User.from_payload(payload)",
        "start_line": 15,
        "end_line": 24,
        "token_count": 198
      }
    }
  ],
  "metadata": {
    "total_chunks_searched": 3891,
    "search_duration_ms": 234,
    "results_returned": 2
  }
}
```

### Response (No Results)

```json
{
  "status": "success",
  "query": "blockchain implementation",
  "results": [],
  "metadata": {
    "total_chunks_searched": 3891,
    "search_duration_ms": 189,
    "results_returned": 0
  },
  "suggestion": "No matching code found. Try broader keywords or ensure codebase is indexed."
}
```

### Response (Failure - Not Indexed)

```json
{
  "error": {
    "code": "INDEX_NOT_READY",
    "message": "Codebase has not been indexed yet",
    "context": {
      "indexed_files": 0
    },
    "recovery": "Run index_codebase tool first"
  }
}
```

### Response (Failure - DB Unavailable)

```json
{
  "error": {
    "code": "DB_UNAVAILABLE",
    "message": "Vector database connection failed",
    "context": {
      "db_path": ".codeminder/vector_db/",
      "error_details": "Permission denied"
    },
    "recovery": "Check file permissions for .codeminder/ directory"
  }
}
```

### Behavior

- Generates query embedding using Jina Embeddings v2
- Performs ANN (Approximate Nearest Neighbors) search in LanceDB
- Returns top N results ranked by cosine similarity
- Each result includes:
  - File path and line numbers
  - Complete code snippet (syntactically valid)
  - Context path showing hierarchy
  - Similarity score (0-1, higher is better)
- If re-indexing is in progress, waits for atomic completion before searching

### Performance

- Target: < 1 second for 100k LOC codebase
- LanceDB ANN search: O(log N) complexity
- Embedding generation: ~50ms per query

---

## Tool 3: `get_index_status` (Optional, informational)

Returns current indexing status and statistics.

### Request

```json
{
  "name": "get_index_status",
  "arguments": {}
}
```

### Response

```json
{
  "status": "ready",
  "statistics": {
    "files_indexed": 142,
    "total_chunks": 3891,
    "total_lines_of_code": 45230,
    "index_size_mb": 87.3,
    "last_indexed": "2025-12-07T10:30:45Z"
  },
  "registry": {
    "persisted": true,
    "files_in_registry": 142,
    "registry_table_size_mb": 2.1,
    "last_reconciliation": "2025-12-07T09:15:22Z"
  },
  "reconciliation": {
    "startup_scan_completed": true,
    "files_reindexed_on_startup": 3,
    "files_deleted_on_startup": 1,
    "new_files_indexed": 0
  },
  "file_watcher": {
    "enabled": true,
    "watching_path": "/home/user/project",
    "pending_updates": 0
  },
  "configuration": {
    "codebase_path": "/home/user/project",
    "chunking_strategy": "ast",
    "token_limit": 2048,
    "concurrency_limit": 4,
    "debounce_ms": 500
  }
}
```

---

## Error Code Reference

| Code | Description | Common Causes | Recovery Action |
|------|-------------|---------------|-----------------|
| `CONFIG_ERROR` | Invalid configuration | Missing/malformed .codeminder.json | Fix configuration file |
| `INDEX_NOT_READY` | Codebase not indexed | index_codebase not run yet | Run index_codebase tool |
| `DB_UNAVAILABLE` | Vector DB connection failed | Permission issues, disk full | Check .codeminder/ directory permissions |
| `PARSE_ERROR` | File syntax error | Invalid Python syntax | Fix syntax or exclude file |
| `EMBEDDING_ERROR` | Failed to generate embeddings | API key invalid, network issue | Check JINA_API_KEY, network |
| `WATCHER_ERROR` | File watcher failed | Permission issues | Check codebase directory permissions |
| `INVALID_QUERY` | Search query invalid | Empty query string | Provide non-empty query |

---

## MCP Protocol Compliance

CodeMinder implements MCP tools following the Model Context Protocol specification:

- **JSON-RPC 2.0**: All requests/responses use JSON-RPC format
- **Tool Discovery**: Server exposes tool metadata via `tools/list` method
- **Type Safety**: Parameters validated using Pydantic models
- **Async Execution**: Tools are async-capable for non-blocking I/O
- **Error Handling**: Follows MCP error response format with structured error objects

Example tool registration (FastMCP):

```python
@mcp.tool()
async def search_code(query: str, limit: int = 20) -> dict:
    """
    Search codebase for relevant code snippets.
    
    Args:
        query: Natural language description of desired code
        limit: Maximum number of results (1-100, default 20)
    
    Returns:
        Dict with status, results array, and metadata
    
    Raises:
        MCPError: With structured error object
    """
    # Implementation
```

---

## Summary

The MCP tool contracts define:
- **2 core tools**: `index_codebase` and `search_code`
- **1 optional tool**: `get_index_status` for diagnostics
- **Structured responses**: Consistent success/error format
- **Error codes**: 7 well-defined error types with recovery actions
- **Performance targets**: <1s search, 5s per 1k LOC indexing
- **MCP compliance**: Follows Model Context Protocol specification

All contracts are designed for AI agent consumption with clear, actionable responses.
