# CodeMinder Configuration Reference

**Version**: 1.0  
**Last Updated**: December 2025

Complete reference for configuring CodeMinder via `.codeminder.json`.

---

## Table of Contents

- [Configuration File Location](#configuration-file-location)
- [Configuration Schema](#configuration-schema)
- [Configuration Options](#configuration-options)
- [Embedding Model Selection](#embedding-model-selection)
- [Performance Tuning](#performance-tuning)
- [Use Case Examples](#use-case-examples)
- [Validation Rules](#validation-rules)
- [Troubleshooting](#troubleshooting)

---

## Configuration File Location

CodeMinder looks for `.codeminder.json` in your **codebase root directory** (the directory specified as `workingDirectory` in your MCP client configuration).

**Example directory structure**:
```
your-project/
├── .codeminder.json          ← Configuration file
├── .codeminder/              ← Runtime data (auto-created)
│   ├── vector_db/            ← LanceDB storage
│   └── codeminder.log        ← Structured logs
├── src/
│   └── your_code.py
└── ...
```

---

## Configuration Schema

**Minimal configuration** (uses defaults):
```json
{
  "codebase_path": "."
}
```

**Complete configuration** (all options):
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

---

## Configuration Options

### `codebase_path` (required)

**Type**: `string`  
**Description**: Directory to index and monitor for code files  
**Constraints**: Must be a valid, readable directory path

**Examples**:
```json
{
  "codebase_path": "."                          // Current directory
}
```

```json
{
  "codebase_path": "./src"                      // Subdirectory only
}
```

```json
{
  "codebase_path": "/home/user/projects/app"    // Absolute path
}
```

**Notes**:
- Relative paths are resolved from the MCP server's working directory
- Must be readable by the user running CodeMinder
- All Python files (`.py`) in this path and subdirectories will be indexed

---

### `embedding_model`

**Type**: `string`  
**Default**: `"jinaai/jina-embeddings-v2-base-code"`  
**Description**: HuggingFace model ID for generating code embeddings

**Recommended Models**:

| Model | Dimensions | Context | RAM | Use Case |
|-------|------------|---------|-----|----------|
| `jinaai/jina-embeddings-v2-base-code` | 768 | 8192 tokens | ~1GB | **Default** - Best quality for code |
| `microsoft/codebert-base` | 768 | 512 tokens | ~500MB | Lightweight, code-optimized |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | 256 tokens | ~80MB | Low-resource machines |
| `Salesforce/codet5-base` | 768 | 512 tokens | ~900MB | High-quality code embeddings |

**Example**:
```json
{
  "embedding_model": "microsoft/codebert-base"
}
```

**Notes**:
- Model is downloaded from HuggingFace on first run (cached to `~/.cache/huggingface/`)
- GPU automatically detected and used if available (with CPU fallback)
- Changing models requires full re-index (different vector dimensions)

**Custom Models**:
You can use any sentence-transformers compatible model from HuggingFace:
```json
{
  "embedding_model": "BAAI/bge-large-en-v1.5"    // General-purpose, high quality
}
```

---

### `token_limit`

**Type**: `integer`  
**Default**: `2048`  
**Range**: `512` - `8192`  
**Description**: Maximum tokens per code chunk

**Examples**:
```json
{
  "token_limit": 1024    // Smaller chunks, more granular search
}
```

```json
{
  "token_limit": 4096    // Larger chunks, more context
}
```

**Trade-offs**:

| Token Limit | Pros | Cons |
|-------------|------|------|
| **512-1024** | • More granular results<br>• Faster indexing<br>• Less memory | • Less context per chunk<br>• May split functions |
| **2048** (default) | • Good balance<br>• Most functions fit | • Balanced performance |
| **4096-8192** | • Maximum context<br>• Fewer chunks | • Slower indexing<br>• More memory<br>• Model must support |

**Notes**:
- Token counting uses `tiktoken` (same as OpenAI)
- Chunks exceeding limit are recursively split at statement/expression boundaries
- Ensure your embedding model supports the context length (Jina supports 8192)

---

### `max_search_results`

**Type**: `integer`  
**Default**: `20`  
**Range**: `1` - `100`  
**Description**: Number of search results to return

**Examples**:
```json
{
  "max_search_results": 10    // Fewer, more relevant results
}
```

```json
{
  "max_search_results": 50    // Comprehensive search
}
```

**Guidelines**:
- **Small codebases (<10k LOC)**: 10-15 results sufficient
- **Medium codebases (10k-50k LOC)**: 20-30 results (default)
- **Large codebases (>50k LOC)**: 30-50 results for better coverage

**Notes**:
- Results are ranked by cosine similarity (most relevant first)
- Increasing limit has minimal performance impact (<10ms)

---

### `concurrency_limit`

**Type**: `integer`  
**Default**: `4`  
**Range**: `1` - `16`  
**Description**: Number of files to process in parallel during indexing

**Examples**:
```json
{
  "concurrency_limit": 2    // Conservative (low-end machines)
}
```

```json
{
  "concurrency_limit": 8    // Aggressive (multi-core CPUs)
}
```

**Guidelines by CPU cores**:

| CPU Cores | Recommended | Notes |
|-----------|-------------|-------|
| 2-4 cores | 2-4 | Conservative for laptops |
| 4-8 cores | 4-6 | Default for most machines |
| 8+ cores | 8-12 | High-performance workstations |

**Notes**:
- Higher concurrency = faster indexing, but more CPU/memory usage
- GPU memory limits may require lower concurrency when using GPU acceleration
- Monitor memory usage during initial indexing and adjust accordingly

---

### `debounce_ms`

**Type**: `integer`  
**Default**: `500` (milliseconds)  
**Range**: `100` - `5000`  
**Description**: Delay before processing file changes (for future file watching feature)

**Examples**:
```json
{
  "debounce_ms": 300    // Faster response, more re-index triggers
}
```

```json
{
  "debounce_ms": 1000   // Fewer triggers, batches more changes
}
```

**Guidelines**:
- **Fast typers**: 300-500ms (catches individual edits)
- **Auto-save enabled**: 500-1000ms (batches rapid saves)
- **Large files**: 1000-2000ms (avoids thrashing)

**Notes**:
- Currently unused (User Story 1 only has startup reconciliation)
- Will be used by file watcher in User Story 2 implementation

---

### `log_level`

**Type**: `string`  
**Default**: `"INFO"`  
**Options**: `"DEBUG"`, `"INFO"`, `"WARN"`, `"ERROR"`  
**Description**: Logging verbosity level

**Examples**:
```json
{
  "log_level": "DEBUG"    // Maximum verbosity (development)
}
```

```json
{
  "log_level": "ERROR"    // Only errors (production)
}
```

**Log Levels**:

| Level | What's Logged | Use Case |
|-------|---------------|----------|
| **DEBUG** | Everything (function calls, variables) | Development, troubleshooting |
| **INFO** | Operations (indexing, searches) | Normal operation (default) |
| **WARN** | Warnings (syntax errors, performance) | Production monitoring |
| **ERROR** | Errors only (crashes, failures) | Production (minimal logs) |

**Log Output**:
- **File**: `.codeminder/codeminder.log` (structured JSON)
- **Stderr**: Console output (human-readable)

**Example log entry** (INFO level):
```json
{
  "timestamp": "2025-12-09T10:30:45.123Z",
  "level": "INFO",
  "message": "File re-indexed successfully",
  "context": {
    "file": "src/auth.py",
    "chunks_created": 23,
    "duration_ms": 1245
  }
}
```

---

### `persist_index`

**Type**: `boolean`  
**Default**: `true`  
**Description**: Save index to disk for restart persistence

**Examples**:
```json
{
  "persist_index": false    // In-memory only (dev/testing)
}
```

**Use Cases**:

| Setting | Use Case | Behavior |
|---------|----------|----------|
| `true` (default) | **Production** | Index survives restarts, startup reconciliation |
| `false` | **Development/Testing** | Fresh index on every startup, no disk I/O |

**Notes**:
- Setting to `false` means full re-index on every server start
- Useful for testing or when disk space is limited
- File registry is still used for tracking during session

---

## Embedding Model Selection

### Decision Matrix

Choose your embedding model based on:

1. **Available RAM**:
   - <1GB free: `sentence-transformers/all-MiniLM-L6-v2`
   - 1-2GB free: `microsoft/codebert-base`
   - 2GB+ free: `jinaai/jina-embeddings-v2-base-code` (recommended)

2. **Codebase Size**:
   - <10k LOC: Any model works
   - 10k-100k LOC: CodeBERT or Jina recommended
   - >100k LOC: Jina for best quality

3. **Hardware**:
   - **No GPU**: Use lighter models (CodeBERT, MiniLM)
   - **GPU available**: Jina (best quality, GPU-accelerated)

### Model Comparison

| Aspect | Jina Code | CodeBERT | MiniLM |
|--------|-----------|----------|--------|
| **Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Speed** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **RAM** | 1GB | 500MB | 80MB |
| **Context** | 8192 tokens | 512 tokens | 256 tokens |
| **Code-specific** | ✅ Yes | ✅ Yes | ❌ General |

---

## Performance Tuning

### For Large Codebases (>100k LOC)

**Problem**: Initial indexing takes too long

**Solutions**:

1. **Use lightweight model**:
   ```json
   {
     "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
     "concurrency_limit": 8
   }
   ```

2. **Reduce chunk size**:
   ```json
   {
     "token_limit": 1024,
     "concurrency_limit": 8
   }
   ```

3. **Index subdirectory only**:
   ```json
   {
     "codebase_path": "./src"    // Skip tests, docs, etc.
   }
   ```

### For Low-Memory Machines

**Problem**: Server crashes with OOM (Out of Memory)

**Solutions**:

1. **Use lightweight model**:
   ```json
   {
     "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
   }
   ```

2. **Reduce concurrency**:
   ```json
   {
     "concurrency_limit": 1
   }
   ```

3. **Reduce chunk size**:
   ```json
   {
     "token_limit": 1024
   }
   ```

### For Better Search Quality

**Problem**: Search results not relevant enough

**Solutions**:

1. **Use high-quality model**:
   ```json
   {
     "embedding_model": "jinaai/jina-embeddings-v2-base-code"
   }
   ```

2. **Increase search results**:
   ```json
   {
     "max_search_results": 50
   }
   ```

3. **Larger context windows**:
   ```json
   {
     "token_limit": 4096
   }
   ```

### For Faster Indexing

**Problem**: Initial indexing too slow

**Solutions**:

1. **Increase concurrency** (if CPU/RAM allows):
   ```json
   {
     "concurrency_limit": 8
   }
   ```

2. **Use faster model**:
   ```json
   {
     "embedding_model": "microsoft/codebert-base"
   }
   ```

3. **Smaller chunks**:
   ```json
   {
     "token_limit": 1024
   }
   ```

---

## Use Case Examples

### Example 1: Developer Laptop (8GB RAM, 4 cores)

**Use case**: Medium codebase (50k LOC), occasional searches

```json
{
  "codebase_path": ".",
  "embedding_model": "microsoft/codebert-base",
  "token_limit": 2048,
  "max_search_results": 20,
  "concurrency_limit": 4,
  "log_level": "INFO",
  "persist_index": true
}
```

### Example 2: High-End Workstation (32GB RAM, 16 cores, GPU)

**Use case**: Large codebase (200k LOC), frequent searches

```json
{
  "codebase_path": ".",
  "embedding_model": "jinaai/jina-embeddings-v2-base-code",
  "token_limit": 4096,
  "max_search_results": 50,
  "concurrency_limit": 12,
  "log_level": "INFO",
  "persist_index": true
}
```

### Example 3: Budget Laptop (4GB RAM, 2 cores)

**Use case**: Small codebase (10k LOC), limited resources

```json
{
  "codebase_path": "./src",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "token_limit": 1024,
  "max_search_results": 15,
  "concurrency_limit": 2,
  "log_level": "WARN",
  "persist_index": true
}
```

### Example 4: Development/Testing

**Use case**: Rapid iteration, frequent restarts

```json
{
  "codebase_path": "./test_data",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "token_limit": 512,
  "max_search_results": 10,
  "concurrency_limit": 1,
  "log_level": "DEBUG",
  "persist_index": false
}
```

### Example 5: CI/CD Pipeline

**Use case**: Automated code analysis, minimal logs

```json
{
  "codebase_path": ".",
  "embedding_model": "microsoft/codebert-base",
  "token_limit": 2048,
  "max_search_results": 30,
  "concurrency_limit": 8,
  "log_level": "ERROR",
  "persist_index": false
}
```

---

## Validation Rules

CodeMinder validates your configuration on startup. Invalid configurations cause the server to fail with clear error messages.

### Required Fields

- `codebase_path`: Must be specified and exist

### Value Constraints

| Field | Constraint | Error if Violated |
|-------|------------|-------------------|
| `codebase_path` | Must exist and be readable | `CONFIG_ERROR: codebase_path not found` |
| `token_limit` | `512 <= value <= 8192` | `CONFIG_ERROR: token_limit out of range` |
| `max_search_results` | `1 <= value <= 100` | `CONFIG_ERROR: max_search_results out of range` |
| `concurrency_limit` | `1 <= value <= 16` | `CONFIG_ERROR: concurrency_limit out of range` |
| `debounce_ms` | `100 <= value <= 5000` | `CONFIG_ERROR: debounce_ms out of range` |
| `log_level` | One of: `DEBUG`, `INFO`, `WARN`, `ERROR` | `CONFIG_ERROR: invalid log_level` |
| `persist_index` | Boolean (`true` or `false`) | `CONFIG_ERROR: persist_index must be boolean` |

### Model Name Format

`embedding_model` must be a valid HuggingFace model identifier:
- Format: `organization/model-name`
- Examples: `jinaai/jina-embeddings-v2-base-code`, `microsoft/codebert-base`

**Validation**:
- Model existence checked during initialization (downloads if not cached)
- Invalid model ID causes `EMBEDDING_ERROR: Model not found on HuggingFace`

---

## Troubleshooting

### Configuration Not Found

**Error**: `CONFIG_ERROR: Configuration file not found`

**Solutions**:
1. Create `.codeminder.json` in the codebase root
2. Check MCP client's `workingDirectory` setting
3. Verify file permissions (readable by CodeMinder)

### Invalid JSON Syntax

**Error**: `CONFIG_ERROR: Failed to parse configuration file`

**Solutions**:
1. Validate JSON syntax with a linter (e.g., `jsonlint .codeminder.json`)
2. Check for:
   - Missing commas between fields
   - Trailing commas (not allowed in JSON)
   - Unquoted strings
   - Single quotes (use double quotes)

### Model Download Failed

**Error**: `EMBEDDING_ERROR: Failed to download model from HuggingFace`

**Solutions**:
1. Check internet connection
2. Verify model name is correct (search HuggingFace)
3. Check disk space in `~/.cache/huggingface/`
4. Try a different model

### Memory Issues

**Error**: Server crashes or becomes unresponsive

**Solutions**:
1. Reduce `concurrency_limit` (try 1 or 2)
2. Use lighter embedding model (`sentence-transformers/all-MiniLM-L6-v2`)
3. Reduce `token_limit` (1024 or lower)
4. Close other applications to free memory

### Slow Indexing

**Problem**: Initial indexing takes too long

**Solutions**:
1. Increase `concurrency_limit` (if CPU/RAM allows)
2. Use faster embedding model (`microsoft/codebert-base`)
3. Reduce `token_limit` (fewer tokens = faster processing)
4. Index smaller directory (`codebase_path: "./src"`)

---

## Configuration File Template

Copy this template to `.codeminder.json` and customize:

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

**Quick customization guide**:
1. Set `codebase_path` to your project directory
2. Choose `embedding_model` based on your hardware (see [Embedding Model Selection](#embedding-model-selection))
3. Adjust `concurrency_limit` based on CPU cores
4. Leave other options at defaults initially
5. Tune performance settings after first run based on observed behavior

---

## Related Documentation

- [Architecture Overview](architecture.md) - System design and algorithms
- [README](../README.md) - Installation and usage guide
- [Full Specification](../specs/001-code-rag-mcp/) - Complete feature specification

---

## Support

If you encounter configuration issues not covered here:
1. Check logs: `tail -f .codeminder/codeminder.log`
2. Enable debug logging: `"log_level": "DEBUG"`
3. Open an issue: https://github.com/vamsi10010/codeminder/issues
