# Tasks: CodeMinder - Code RAG MCP Server

**Input**: Design documents from `/specs/001-code-rag-mcp/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/mcp-tools.md

**Tests**: Per the constitution, Test-First Development is MANDATORY. All features MUST include tests written BEFORE implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure with src/codeminder/ layout per plan.md
- [ ] T002 Initialize Python 3.12+ project with pyproject.toml using uv
- [ ] T003 [P] Configure ruff (linting/formatting) in pyproject.toml
- [ ] T004 [P] Configure mypy (type checking) with strict mode in pyproject.toml
- [ ] T005 [P] Configure pytest with coverage plugin in pyproject.toml
- [ ] T006 Create .codeminder.json.example configuration template with all options
- [ ] T007 [P] Setup .gitignore (.codeminder/, .venv/, __pycache__, *.pyc)
- [ ] T008 Create README.md with project overview and quickstart reference

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Configuration & Utilities

- [ ] T009 Implement Configuration model in src/codeminder/config.py with Pydantic validation
- [ ] T010 [P] Implement structured logging in src/codeminder/utils/logger.py (JSON format, levels, file+stderr)
- [ ] T011 [P] Implement error classes with codes in src/codeminder/utils/errors.py (CONFIG_ERROR, PARSE_ERROR, DB_UNAVAILABLE, EMBEDDING_ERROR, WATCHER_ERROR, INDEX_NOT_READY, SEARCH_ERROR)

### Data Models

- [ ] T012 [P] Create File entity in src/codeminder/storage/models.py with UUID, paths, language, parse_status, timestamps
- [ ] T013 [P] Create CodeChunk entity in src/codeminder/storage/models.py with UUID, file_id, source_code, context_path, lines, token_count, node_type, sequence_number, parent_id
- [ ] T014 [P] Create Embedding entity in src/codeminder/storage/models.py with chunk_id, vector, model_version, created_at

### Core Components (No User Story Yet)

- [ ] T015 [P] Implement token counter in src/codeminder/parser/token_counter.py using tiktoken
- [ ] T016 Implement LanceDB connection in src/codeminder/storage/vector_db.py with connect(), create_table(), persistence handling
- [ ] T017 Implement sentence-transformers loader in src/codeminder/embeddings/embedder.py with model initialization, device selection (GPU/CPU)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Semantic Code Search via MCP (Priority: P1) 🎯 MVP

**Goal**: Enable AI assistants to search codebases semantically via MCP tools, returning syntactically valid code chunks with context

**Independent Test**: Start MCP server, connect AI assistant, index a Python codebase, search for "authentication logic", verify results contain valid code with file paths and line numbers

### Tests for User Story 1 (Write FIRST - Red-Green-Refactor) ⚠️

- [ ] T018 [P] [US1] Contract test for index_codebase tool in tests/contract/test_mcp_index.py (request format, success response, error responses)
- [ ] T019 [P] [US1] Contract test for search_code tool in tests/contract/test_mcp_search.py (request format, result structure, ranking)
- [ ] T020 [P] [US1] Integration test for end-to-end indexing flow in tests/integration/test_indexing_flow.py (scan files, parse AST, chunk, embed, store)
- [ ] T021 [P] [US1] Integration test for end-to-end search flow in tests/integration/test_search_flow.py (query embedding, vector search, result formatting)
- [ ] T022 [P] [US1] Unit test for AST parser in tests/unit/test_ast_parser.py (Tree-sitter parsing, error handling)
- [ ] T023 [P] [US1] Unit test for chunker in tests/unit/test_chunker.py (adaptive sizing, context paths, sequence numbers, syntactic validity)
- [ ] T024 [P] [US1] Unit test for embedder in tests/unit/test_embedder.py (batch encoding, model loading, error handling)
- [ ] T025 [P] [US1] Unit test for vector_db in tests/unit/test_vector_db.py (CRUD operations, similarity search)

### Implementation for User Story 1

#### AST Parsing & Chunking

- [ ] T026 [P] [US1] Implement Tree-sitter parser in src/codeminder/parser/ast_parser.py (parse file, handle syntax errors)
- [ ] T027 [US1] Implement adaptive chunker in src/codeminder/parser/chunker.py (recursive descent, token counting, sequence numbering, context path construction) - depends on T026
- [ ] T028 [US1] Add split node handling for large functions in src/codeminder/parser/chunker.py (statements, expressions, node type tracking)

#### Embedding Generation

- [ ] T029 [US1] Implement batch embedding in src/codeminder/embeddings/embedder.py (encode chunks, handle context+code, progress tracking)
- [ ] T030 [US1] Add embedding error handling and retry logic in src/codeminder/embeddings/embedder.py

#### Vector Storage

- [ ] T031 [US1] Implement chunk storage in src/codeminder/storage/vector_db.py (insert chunks with embeddings, handle duplicates)
- [ ] T032 [US1] Implement similarity search in src/codeminder/storage/vector_db.py (ANN search, cosine similarity, result ranking)
- [ ] T033 [US1] Implement chunk deletion in src/codeminder/storage/vector_db.py (delete by file_id, atomic operations)

#### Search Logic

- [ ] T034 [US1] Implement search service in src/codeminder/search/searcher.py (query embedding, vector search, result formatting with context paths)
- [ ] T035 [US1] Add result ranking and filtering in src/codeminder/search/searcher.py (top-k selection, similarity thresholds)

#### Indexing Service

- [ ] T036 [US1] Implement file scanner in src/codeminder/parser/scanner.py (recursive directory traversal, extension filtering, excluded patterns)
- [ ] T037 [US1] Implement indexing service in src/codeminder/server.py (scan → parse → chunk → embed → store pipeline)
- [ ] T038 [US1] Add parallel processing in src/codeminder/server.py (asyncio.Semaphore with concurrency_limit)
- [ ] T039 [US1] Add indexing error aggregation and reporting in src/codeminder/server.py (partial success handling)

#### MCP Server

- [ ] T040 [US1] Implement FastMCP server initialization in src/codeminder/server.py (load config, initialize components)
- [ ] T041 [US1] Implement index_codebase MCP tool in src/codeminder/server.py (trigger indexing, return summary)
- [ ] T042 [US1] Implement search_code MCP tool in src/codeminder/server.py (accept query, return ranked results)
- [ ] T043 [US1] Add MCP error handling and response formatting in src/codeminder/server.py (structured errors per contracts)
- [ ] T044 [US1] Add get_index_status MCP tool (optional) in src/codeminder/server.py (diagnostics: file count, chunk count, index size)

**Checkpoint**: User Story 1 complete - MCP server can index Python codebases and perform semantic search

---

## Phase 4: User Story 2 - Automatic Index Maintenance (Priority: P1)

**Goal**: Automatically detect file changes and update the index in real-time without manual intervention

**Independent Test**: Start file watcher, modify and save a Python file, query for content from that file, verify updated version is returned within 2 seconds

### Tests for User Story 2 (Write FIRST - Red-Green-Refactor) ⚠️

- [ ] T045 [P] [US2] Integration test for file watcher in tests/integration/test_file_watcher.py (detect changes, trigger re-index, debouncing)
- [ ] T046 [P] [US2] Unit test for debounce logic in tests/unit/test_debounce.py (500ms window, last-change-wins)
- [ ] T047 [P] [US2] Integration test for re-indexing in tests/integration/test_reindex.py (delete old chunks, parse new, atomic updates)
- [ ] T048 [P] [US2] Integration test for batch changes in tests/integration/test_batch_changes.py (git checkout simulation, parallel processing)

### Implementation for User Story 2

#### File Watcher

- [ ] T049 [US2] Implement file watcher in src/codeminder/watcher/file_watcher.py using watchfiles (async watch, 500ms debounce)
- [ ] T050 [US2] Add change type handling in src/codeminder/watcher/file_watcher.py (modified, created, deleted events)
- [ ] T051 [US2] Add file extension filtering in src/codeminder/watcher/file_watcher.py (only Python files in Phase 1)

#### Re-indexing Logic

- [ ] T052 [US2] Implement file deletion handler in src/codeminder/watcher/file_watcher.py (remove File and cascade delete chunks)
- [ ] T053 [US2] Implement file creation handler in src/codeminder/watcher/file_watcher.py (trigger full indexing for new file)
- [ ] T054 [US2] Implement file modification handler in src/codeminder/watcher/file_watcher.py (atomic delete+reparse)
- [ ] T055 [US2] Add re-index coordination in src/codeminder/watcher/file_watcher.py (queue changes, process in parallel with semaphore)

#### Search Consistency

- [ ] T056 [US2] Add re-index lock in src/codeminder/storage/vector_db.py (prevent reads during atomic updates)
- [ ] T057 [US2] Implement atomic transaction for re-indexing in src/codeminder/storage/vector_db.py (delete old + insert new in single operation)

#### Integration

- [ ] T058 [US2] Integrate file watcher with MCP server in src/codeminder/server.py (start watcher on server init)
- [ ] T059 [US2] Add watcher lifecycle management in src/codeminder/server.py (start, stop, error recovery)
- [ ] T060 [US2] Add watcher status to get_index_status tool in src/codeminder/server.py (enabled, watching_path)

**Checkpoint**: User Story 2 complete - Index automatically updates when files change

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

### Documentation

- [ ] T061 [P] Update README.md with installation instructions from quickstart.md
- [ ] T062 [P] Create docs/architecture.md explaining AST chunking algorithm and system design
- [ ] T063 [P] Create docs/configuration.md documenting all .codeminder.json options

### Code Quality

- [ ] T064 Run ruff check and fix all linting issues across codebase
- [ ] T065 Run mypy and fix all type checking errors across codebase
- [ ] T066 Add docstrings to all public APIs (Google-style per plan.md)
- [ ] T067 [P] Add additional edge case tests in tests/unit/ (oversized nodes, syntax errors, empty files)

### Performance

- [ ] T068 Add performance benchmarks in tests/performance/ (indexing speed, search latency, memory usage)
- [ ] T069 Profile and optimize chunking algorithm for large files
- [ ] T070 Profile and optimize embedding batch sizes

### Validation

- [ ] T071 Run full quickstart.md walkthrough and fix any issues
- [ ] T072 Test with real-world Python codebase (>10k LOC) and validate success criteria
- [ ] T073 Validate all MCP protocol compliance requirements from contracts/mcp-tools.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase - Core semantic search capability
- **User Story 2 (Phase 4)**: Depends on Foundational phase and User Story 1 (needs search/index infrastructure)
- **Polish (Phase 5)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Must complete first - provides core indexing and search
  - Foundational phase → Tests → AST Parsing → Embedding → Storage → Search → Indexing → MCP Tools
- **User Story 2 (P1)**: Depends on User Story 1 completion
  - User Story 1 → Tests → File Watcher → Re-indexing → Integration

### Within Each User Story

1. **Tests FIRST**: Write contract, integration, and unit tests (Red phase)
2. **Implementation**: Build components to make tests pass (Green phase)
3. **Refactor**: Clean up code while keeping tests passing (Refactor phase)
4. **Quality**: Run ruff, mypy, ensure coverage >80%

### Parallel Opportunities

#### Phase 1 (Setup)
All tasks marked [P] can run in parallel: T003, T004, T005, T007

#### Phase 2 (Foundational)
- Config & Utilities: T010, T011 parallel
- Data Models: T012, T013, T014 parallel
- Core Components: T015, T017 parallel (T016 sequential)

#### Phase 3 (User Story 1)
- All tests (T018-T025) can run in parallel - 8 tests simultaneously
- AST components: T026, then T027+T028
- Embedding: T029+T030
- Storage: T031, T032, T033 sequential (same file)
- Search: T034+T035
- Indexing: T036, then T037, T038, T039
- MCP: T040, then T041+T042+T043+T044

#### Phase 4 (User Story 2)
- All tests (T045-T048) can run in parallel - 4 tests simultaneously
- Watcher: T049, then T050+T051
- Handlers: T052+T053+T054 parallel, then T055
- Consistency: T056+T057
- Integration: T058, T059, T060 sequential

#### Phase 5 (Polish)
- Documentation: T061, T062, T063 parallel
- Edge tests: T067 parallel with other work

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together (Constitution: Test-First):
pytest tests/contract/test_mcp_index.py &      # T018
pytest tests/contract/test_mcp_search.py &      # T019
pytest tests/integration/test_indexing_flow.py & # T020
pytest tests/integration/test_search_flow.py &   # T021
pytest tests/unit/test_ast_parser.py &          # T022
pytest tests/unit/test_chunker.py &             # T023
pytest tests/unit/test_embedder.py &            # T024
pytest tests/unit/test_vector_db.py &           # T025
wait
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (~2 hours)
2. Complete Phase 2: Foundational (~4 hours)
3. Complete Phase 3: User Story 1 (~16 hours)
   - Tests first: ~4 hours
   - Implementation: ~12 hours
4. **STOP and VALIDATE**: Test with real codebase
5. **MVP READY**: Can index and search Python codebases

**Total MVP Time**: ~22 hours of focused development

### Full MVP (User Stories 1 + 2)

1. Complete MVP First (above)
2. Complete Phase 4: User Story 2 (~8 hours)
   - Tests first: ~2 hours
   - Implementation: ~6 hours
3. **VALIDATE**: Test auto-updates with file changes
4. **FULL MVP READY**: Production-ready MCP server

**Total Full MVP Time**: ~30 hours of focused development

### With Polish

1. Complete Full MVP (above)
2. Complete Phase 5: Polish (~6 hours)
3. **PRODUCTION READY**: Documented, optimized, validated

**Total Production Time**: ~36 hours of focused development

---

## Success Criteria Mapping

### User Story 1 Tasks → Success Criteria

- **SC-001** (>70% accuracy on SWE-bench): T034, T035 (search ranking)
- **SC-002** (100% syntactic validity): T023, T027, T028 (chunking algorithm)
- **SC-003** (<1s search for 100k LOC): T032, T069 (search optimization)
- **SC-004** (>60% HumanEval with hidden helpers): T034 (search quality)
- **SC-005** (99% uptime): T043 (error handling)
- **SC-006** (5s per 1k LOC indexing): T038, T069 (parallel processing)

### User Story 2 Tasks → Success Criteria

- **SC-007** (<5s file re-index): T054, T057 (atomic re-indexing)
- **SC-008** (8+ hours uptime): T059 (lifecycle management), T070 (memory optimization)

---

## Notes

- **[P] tasks**: Different files, no dependencies - can execute in parallel
- **[Story] label**: Maps task to specific user story (US1, US2) for traceability
- **Test-First**: Constitution requires all tests written BEFORE implementation
- **Checkpoints**: Stop after each phase to validate independently
- **Coverage**: Target >80% per constitution
- **Commit**: After each task or logical group
- **Quality Gates**: ruff + mypy must pass before marking tasks complete
- **File Paths**: All paths shown are final locations per plan.md structure
