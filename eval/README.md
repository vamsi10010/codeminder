# Evaluation Harness

This folder contains a minimal, runnable evaluation setup for CodeMinder search.

## What’s here
- `fixtures/sample_project/`: Tiny toy codebase to index.
- `golden_queries.json`: Labeled queries with expected files.
- `run_ir_eval.py`: Indexes a codebase with the AST chunker and reports search metrics.
- `run_chunking_compare.py`: Compares AST chunking vs a simple line-based chunker.

## Prerequisites
- Python 3.12+
- Dependencies installed from repo root:
  ```bash
  uv venv && source .venv/bin/activate
  uv pip install -e .
  ```
- Ensure the chosen embedding model is available (default is `sentence-transformers/all-MiniLM-L6-v2`).

## Quick start (use the bundled fixture)
From the repo root:
```bash
python eval/run_ir_eval.py
python eval/run_chunking_compare.py
```
Both commands default to the toy fixture and goldens in this folder.

## Run IR evaluation on a custom codebase
```bash
python eval/run_ir_eval.py \
  --codebase /path/to/your/codebase \
  --golden /path/to/golden_queries.json \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --max-results 5 \
  --token-limit 512
```
Outputs JSON with `success_rate_at_1`, `success_rate_at_k`, `mean_mrr`, and per-query details.

## Compare AST vs line chunking
```bash
python eval/run_chunking_compare.py \
  --codebase /path/to/your/codebase \
  --golden /path/to/golden_queries.json \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --max-results 5 \
  --token-limit 512 \
  --line-span 40
```
Outputs JSON with success@1/k, mean MRR, and chunk stats for both strategies.

## Notes
- Both scripts run in-memory (`persist_index=False`) for speed; point `--codebase` to any repo you want to benchmark.
- Update `golden_queries.json` to reflect your codebase and relevant files (paths can be matched by suffix).
