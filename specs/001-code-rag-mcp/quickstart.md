# Quickstart Guide: CodeMinder

**Phase 1 Output** | **Date**: 2025-12-07

Get CodeMinder up and running in under 5 minutes.

---

## Prerequisites

- **Python**: 3.12 or higher
- **uv**: Fast Python package installer (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Environment**: Linux or macOS (Windows via WSL)
- **Hardware**: ~2GB RAM for default embedding model (less for lightweight models)

---

## Installation

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/codeminder.git
cd codeminder

# Install dependencies using uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### 2. Create Configuration File

Create `.codeminder.json` in your codebase root:

```json
{
  "codebase_path": ".",
  "embedding_model": "jinaai/jina-embeddings-v2-base-code",
  "token_limit": 2048,
  "max_search_results": 20,
  "concurrency_limit": 4,
  "debounce_ms": 500,
  "log_level": "INFO",
  "persist_index": true,
  "excluded_patterns": [
    "*.pyc",
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    "*.min.js"
  ]
}
```

**Configuration Options**:
- `codebase_path`: Directory to index (relative or absolute path)
- `embedding_model`: HuggingFace model ID (default: jinaai/jina-embeddings-v2-base-code)
  - Lightweight: `microsoft/codebert-base` (~500MB)
  - Budget: `sentence-transformers/all-MiniLM-L6-v2` (~80MB)
- `token_limit`: Max tokens per code chunk (default: 2048)
- `max_search_results`: Number of search results to return (default: 20)
- `concurrency_limit`: Parallel file processing (1-16, default: 4)
- `debounce_ms`: File change debounce delay (default: 500ms)
- `log_level`: DEBUG | INFO | WARN | ERROR
- `persist_index`: Save index to disk for restart persistence
- `excluded_patterns`: Glob patterns to skip during indexing

---

## Running the MCP Server

### Start Server

```bash
# Start CodeMinder MCP server
python -m codeminder.server

# Or with custom config location
python -m codeminder.server --config /path/to/.codeminder.json
```

**Output** (first run):
```
[INFO] CodeMinder MCP Server v0.1.0
[INFO] Configuration loaded from .codeminder.json
[INFO] Connected to LanceDB at .codeminder/vector_db
[INFO] No existing file registry found, will index from scratch
[INFO] File watcher started: /home/user/project
[INFO] MCP server listening on stdio
```

**Output** (subsequent runs with existing index):
```
[INFO] CodeMinder MCP Server v0.1.0
[INFO] Configuration loaded from .codeminder.json
[INFO] Connected to LanceDB at .codeminder/vector_db
[INFO] Loaded file registry with 142 files
[INFO] Startup reconciliation: 3 files modified, 1 deleted, 0 new
[INFO] Re-indexing 3 modified files...
[INFO] Reconciliation complete in 4.2 seconds
[INFO] File watcher started: /home/user/project
[INFO] MCP server listening on stdio
```

### Connect AI Assistant

CodeMinder uses the Model Context Protocol (MCP), which is supported by:
- **Claude Desktop**: Add to `claude_desktop_config.json`
- **Cursor IDE**: Add to MCP settings
- **Custom clients**: Any MCP-compatible client

**Example: Claude Desktop Configuration**

Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codeminder": {
      "command": "python",
      "args": ["-m", "codeminder.server"],
      "workingDirectory": "/path/to/your/codebase"
    }
  }
}
```

Restart Claude Desktop to load the configuration.

---

## Basic Usage

### 1. Index Your Codebase

**First Run**: Server automatically performs startup reconciliation and indexes all files.

**Subsequent Runs**: Server loads existing file registry and only re-indexes changed files.

**Manual Re-index** (optional, for debugging):

**In Claude/AI Assistant**:
```
Use the index_codebase tool to force a full re-index of my codebase.
```

**Response**:
```json
{
  "status": "success",
  "summary": {
    "files_indexed": 142,
    "chunks_created": 3891,
    "duration_seconds": 23.4
  }
}
```

**What happens on first run**:
- Downloads embedding model on first run (~1GB, cached to `~/.cache/huggingface/`)
- Scans codebase for Python files (.py)
- Parses each file into AST (Abstract Syntax Tree)
- Chunks code at logical boundaries (functions, classes, methods)
- Generates embeddings locally using sentence-transformers
- **Persists File registry to LanceDB** (tracks which files indexed and when)
- Stores code chunks + embeddings in LanceDB (`.codeminder/vector_db/`)
- Starts file watcher for automatic updates

**What happens on subsequent startups**:
- Loads File registry from LanceDB
- Compares filesystem mtime vs `last_indexed` for each file
- **Only re-indexes files that changed while server was down**
- Deletes records for files that were removed
- Adds new files discovered on filesystem
- Much faster than full re-index (typically 2-5 seconds for small changes)

### 2. Search for Code

Ask natural language questions about your codebase.

**Example Queries**:

```
Find the authentication logic
```

```
Show me where database connections are established
```

```
Find code that handles user registration
```

**Response** (formatted by AI assistant):
```
I found 3 relevant code snippets:

1. **src/auth/jwt_handler.py** (Lines 42-50)
   Context: JWTHandler.verify_token
   Similarity: 89%
   
   def verify_token(self, token: str) -> dict:
       """Verify JWT token and return payload."""
       try:
           payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
           return payload
       except jwt.ExpiredSignatureError:
           raise AuthenticationError('Token has expired')
       except jwt.InvalidTokenError:
           raise AuthenticationError('Invalid token')

[Additional results...]
```

### 3. Automatic Re-Indexing

CodeMinder automatically detects file changes and updates the index.

**What happens when you save a file**:
1. File watcher detects change (debounced 500ms)
2. Old chunks deleted from index
3. File re-parsed and re-indexed
4. New embeddings generated and stored
5. Search immediately reflects updated code

**No manual intervention needed!**

---

## Common Workflows

### Workflow 1: Understanding a New Codebase

```bash
# 1. Clone the repository
git clone https://github.com/some/project.git
cd project

# 2. Create .codeminder.json
cat > .codeminder.json << 'EOF'
{
  "codebase_path": ".",
  "embedding_model": "jinaai/jina-embeddings-v2-base-code"
}
EOF

# 3. Start MCP server (or via IDE integration)
python -m codeminder.server
```

**In AI Assistant**:
```
Index this codebase, then explain the architecture
```

### Workflow 2: Finding Implementation Examples

**Query**:
```
Show me examples of error handling patterns
```

**CodeMinder returns**:
- All try/except blocks
- Error class definitions
- Custom exception handling

### Workflow 3: Code Review Assistance

**Query**:
```
Find all places where user input is processed without validation
```

**CodeMinder returns**:
- Input handling functions
- Form processing code
- API endpoint handlers

---

## Verification & Troubleshooting

### Check Index Status

```python
# Optional: get_index_status tool (if implemented)
# In AI assistant:
Get the current index status
```

**Response**:
```json
{
  "status": "ready",
  "statistics": {
    "files_indexed": 142,
    "total_chunks": 3891,
    "total_lines_of_code": 45230,
    "index_size_mb": 87.3
  },
  "file_watcher": {
    "enabled": true,
    "watching_path": "/home/user/project"
  }
}
```

### Common Issues

#### Issue: "Configuration error"

**Symptom**: Server fails to start

**Solutions**:
- Check `.codeminder.json` syntax (valid JSON)
- Ensure `codebase_path` exists and is readable
- Verify `JINA_API_KEY` environment variable is set

#### Issue: "No results found"

**Symptom**: Search returns empty results

**Solutions**:
- Run `index_codebase` first
- Check that files exist in `codebase_path`
- Verify file extensions are supported (.py for Phase 1)
- Try broader search terms

#### Issue: "Permission denied"

**Symptom**: Cannot create `.codeminder/` directory

**Solutions**:
- Check write permissions in codebase directory
- Run with appropriate user permissions
- Ensure disk space available

#### Issue: "File watcher not detecting changes"

**Symptom**: Code changes not reflected in search

**Solutions**:
- Check file watcher logs (`.codeminder/codeminder.log`)
- Verify file is in `codebase_path` (not in `excluded_patterns`)
- Restart server to reset watcher

### Logs

View detailed logs:

```bash
# Real-time log viewing
tail -f .codeminder/codeminder.log

# Filter for errors
grep ERROR .codeminder/codeminder.log

# Filter for specific file
grep "src/auth.py" .codeminder/codeminder.log
```

**Log Format** (structured JSON):
```json
{
  "timestamp": "2025-12-07T10:30:45.123Z",
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

## Performance Tuning

### For Large Codebases (>100k LOC)

**Use Lightweight Model**:
```json
{
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
}
```

**Increase Concurrency**:
```json
{
  "concurrency_limit": 8
}
```

### For Faster Indexing

**Reduce Token Limit** (smaller chunks, faster processing):
```json
{
  "token_limit": 1024
}
```

**Disable Persistence** (dev mode only):
```json
{
  "persist_index": false
}
```

### For Better Search Results

**Increase Result Limit**:
```json
{
  "max_search_results": 50
}
```

**Increase Token Limit** (larger context windows):
```json
{
  "token_limit": 4096
}
```

---

## Next Steps

### Phase 1 (Current)

- ✅ Python code indexing
- ✅ Semantic search
- ✅ Automatic re-indexing
- ✅ MCP server

### Phase 2 (Future)

- Multi-language support (JavaScript, TypeScript)
- Code graph overlay (imports, function calls)
- Hybrid retrieval (vector + graph)
- Performance optimizations

### Advanced Usage

- **Custom Embeddings**: Use local models instead of Jina API
- **Multiple Codebases**: Run multiple instances with different configs
- **Integration**: Embed in CI/CD for code analysis

---

## Support & Resources

- **Documentation**: `/specs/001-code-rag-mcp/`
- **Issues**: https://github.com/your-org/codeminder/issues
- **MCP Protocol**: https://modelcontextprotocol.io/
- **HuggingFace Models**: https://huggingface.co/models?pipeline_tag=sentence-similarity

---

## Summary

**3 Steps to Get Started**:
1. Install dependencies: `uv pip install -e .`
2. Configure: Create `.codeminder.json` with embedding model preference
3. Run: `python -m codeminder.server` and connect AI assistant

**Key Commands**:
- Index codebase: `index_codebase` MCP tool
- Search code: Natural language queries via AI assistant
- Check logs: `tail -f .codeminder/codeminder.log`

CodeMinder is now ready to help you navigate and understand your codebase!
