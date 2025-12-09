# CodeMinder

**Semantic Code Search via Model Context Protocol (MCP)**

CodeMinder is an MCP server that enables AI assistants to understand and navigate your codebase using semantic search. It bridges the "context gap" by providing intelligent, syntax-aware code retrieval through AST-based chunking and local embeddings.

## Features

- 🔍 **Semantic Code Search**: Ask natural language questions, get relevant code snippets
- 🌳 **AST-Based Chunking**: Code is split at logical boundaries (functions, classes) ensuring 100% syntactic validity
- 🔒 **Privacy-First**: All processing happens locally - your code never leaves your machine
- 🚀 **Fast & Efficient**: <1s search for codebases up to 100k LOC, automatic startup reconciliation
- 🔌 **MCP Compatible**: Works with Claude Desktop, Cursor IDE, and any MCP-compatible AI assistant
- 💾 **Persistent Index**: LanceDB storage survives restarts, only re-indexes changed files

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

# Install dependencies using uv (automatically creates venv and installs deps)
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
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
  "persist_index": true
}
```

**Configuration Options**:
- `codebase_path`: Directory to index (relative or absolute path, required)
- `embedding_model`: HuggingFace model ID (default: jinaai/jina-embeddings-v2-base-code)
  - Lightweight: `microsoft/codebert-base` (~500MB)
  - Budget: `sentence-transformers/all-MiniLM-L6-v2` (~80MB)
- `token_limit`: Max tokens per code chunk (512-8192, default: 2048)
- `max_search_results`: Number of search results to return (1-100, default: 20)
- `concurrency_limit`: Parallel file processing (1-16, default: 4)
- `debounce_ms`: File change debounce delay (default: 500ms)
- `log_level`: DEBUG | INFO | WARN | ERROR
- `persist_index`: Save index to disk for restart persistence
---

## Running the MCP Server

### Start Server

```bash
# Start CodeMinder MCP server (uses entry point from pyproject.toml)
codeminder

# Or directly with Python
python -m codeminder.mcp_server
```

**Output** (first run):
```
[INFO] CodeMinder MCP Server v0.1.0
[INFO] Configuration loaded from .codeminder.json
[INFO] Connected to LanceDB at .codeminder/vector_db
[INFO] No existing file registry found, will index from scratch
[INFO] MCP server listening on stdio
```

**Output** (subsequent runs with existing index):
```
[INFO] CodeMinder MCP Server v0.1.0
[INFO] Configuration loaded from .codeminder.json
[INFO] Connected to LanceDB at .codeminder/vector_db
[INFO] Loaded file registry with 142 files
[INFO] Startup reconciliation: 2 files modified, 0 deleted, 0 new
[INFO] Re-indexing 2 modified files...
[INFO] Reconciliation complete in 4.2 seconds
[INFO] MCP server listening on stdio
```

**Note**: The server runs in the foreground and communicates via stdio (standard input/output) using the Model Context Protocol. It's designed to be started by MCP clients (like Claude Desktop), not run directly by users.

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
      "command": "/path/to/codeminder/.venv/bin/codeminder",
      "workingDirectory": "/path/to/your/codebase"
    }
  }
}
```

**Or using Python directly**:
```json
{
  "mcpServers": {
    "codeminder": {
      "command": "/path/to/codeminder/.venv/bin/python",
      "args": ["-m", "codeminder.mcp_server"],
      "workingDirectory": "/path/to/your/codebase"
    }
  }
}
```

Restart Claude Desktop to load the configuration.

---

## Basic Usage

### 1. Automatic Indexing

CodeMinder automatically indexes your codebase on startup:

**First Run**:
- Downloads embedding model (~1GB, cached to `~/.cache/huggingface/`) - one-time download
- Scans codebase for Python files (.py)
- Parses each file into AST (Abstract Syntax Tree)
- Chunks code at logical boundaries (functions, classes, methods)
- Generates embeddings locally using sentence-transformers
- **Persists File registry to LanceDB** - tracks which files are indexed and when
- Stores code chunks + embeddings in LanceDB (`.codeminder/vector_db/`)

**Subsequent Runs**:
- Loads File registry from LanceDB
- Compares filesystem mtime vs `last_indexed` timestamp for each file
- **Only re-indexes files that changed while server was down**
- Deletes records for files that were removed
- Adds new files discovered on filesystem
- Much faster than full re-index (typically 2-5 seconds for small changes)

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

### 3. Check Index Status

**In Claude/AI Assistant**:
```
Get the current index status
```

**Response**:
```json
{
  "status": "ready",
  "statistics": {
    "files_indexed": 142,
    "total_chunks": 3891,
    "index_size_mb": 245.3,
    "last_indexed": "2025-12-09T10:30:45Z"
  },
  "registry": {
    "persisted": true,
    "files_in_registry": 142
  },
  "reconciliation": {
    "actions_on_startup": {
      "new_files": 0,
      "modified_files": 2,
      "deleted_files": 0
    }
  }
}
```

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

# 3. Configure MCP client (e.g., Claude Desktop)
# Server will automatically index on first startup
```

**In AI Assistant**:
```
Explain the architecture of this codebase
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

## Troubleshooting

### Common Issues

#### Issue: "Configuration error"

**Symptom**: Server fails to start

**Solutions**:
- Check `.codeminder.json` syntax (valid JSON)
- Ensure `codebase_path` exists and is readable
- Verify Python 3.12+ is installed
- Check that embedding model can be downloaded from HuggingFace

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

#### Issue: "Index not updating after code changes"

**Symptom**: Code changes not reflected in search results

**Solutions**:
- **Restart the MCP server** to trigger startup reconciliation (automatically detects and re-indexes changed files)
- Or manually run `index_codebase` tool again to force full re-index
- Note: Startup reconciliation compares file modification times and only re-indexes what changed

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

**Note**: Pattern-based file exclusion is planned for a future release. Currently, the scanner includes all `.py` files in the codebase path.

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

## Current Features & Roadmap

### ✅ Implemented (User Story 1)

- Python code indexing with AST-based chunking
- Semantic search via MCP tools
- Startup reconciliation (automatic detection of changed files)
- Persistent file registry in LanceDB
- Local embeddings (privacy-preserving)
- MCP server with `index_codebase` and `search_code` tools

### 🚧 Planned Features

**User Story 2: Automatic Index Maintenance**
- Real-time file watching with automatic re-indexing
- Live updates as you save files (no server restart needed)
- Debounced change detection (500ms)

**Future Phases**
- Multi-language support (JavaScript, TypeScript, Java, etc.)
- Code graph overlay (imports, function calls, dependencies)
- Hybrid retrieval (vector + graph traversal)
- Advanced filtering and search refinements

### Advanced Usage

- **Custom Embeddings**: Use local models instead of Jina API
- **Multiple Codebases**: Run multiple instances with different configs
- **Integration**: Embed in CI/CD for code analysis

---

## Architecture

For detailed information about the system design, AST chunking algorithm, and technical decisions, see:
- **Architecture Overview**: [docs/architecture.md](docs/architecture.md)
- **Configuration Reference**: [docs/configuration.md](docs/configuration.md)
- **Full Specification**: [specs/001-code-rag-mcp/](specs/001-code-rag-mcp/)

---

## Support & Resources

- **Documentation**: [specs/001-code-rag-mcp/](specs/001-code-rag-mcp/)
- **Issues**: https://github.com/vamsi10010/codeminder/issues
- **MCP Protocol**: https://modelcontextprotocol.io/
- **HuggingFace Models**: https://huggingface.co/models?pipeline_tag=sentence-similarity

---

## Quick Start Summary

**3 Steps to Get Started**:
1. **Install**: `uv sync` (creates venv and installs dependencies)
2. **Configure**: Create `.codeminder.json` in your codebase root
3. **Connect**: Add to Claude Desktop or MCP-compatible AI assistant

**Key Features**:
- 🔍 Semantic code search via natural language queries
- 🌳 AST-based chunking ensures syntactic validity
- 🔒 100% local processing - your code never leaves your machine
- 💾 Persistent index with automatic startup reconciliation
- 🚀 Fast search: <1s for 100k LOC codebases

**Available MCP Tools**:
- `index_codebase`: Manually trigger full re-index
- `search_code`: Semantic search for code snippets
- `get_index_status`: Check indexing statistics and status

CodeMinder is now ready to help you navigate and understand your codebase!
