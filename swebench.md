# SWE-bench Runner Guide

This repo ships a thin runner (`eval/run_swebench_eval.py`) to produce SWE-bench prediction JSONL files using your own agent. It does **not** download SWE-bench or clone repos; you must prepare inputs as below.

## Files you need
1. **SWE-bench tasks JSONL**: e.g., `swebench_lite.jsonl` from the SWE-bench release.
2. **Local repo checkouts** for each task:
   - Either each task JSON includes `repo_path`, or
   - You provide `--repo-root` containing directories named `owner__repo` (e.g., `facebook__prophet`).
3. **Your agent executable/script** that:
   - Reads the SWE-bench task JSON (provided on stdin; also available via `{task_json}` placeholder).
   - Applies a fix in the target repo and prints the resulting patch to stdout.
   - (Optional) Uses CodeMinder if you pass `--codeminder-config /path/to/.codeminder.json`.
4. **(Optional) CodeMinder config**: `.codeminder.json` to expose to your agent via `--codeminder-config`.
5. **Output path**: `predictions.jsonl` will be created by the runner (no need to pre-create).

## How to run the runner
From repo root:
```bash
python eval/run_swebench_eval.py \
  --tasks /path/to/swebench_lite.jsonl \
  --repo-root /path/to/repos \
  --agent-cmd "python /path/to/your_agent.py --repo {repo} --task-id {instance_id}" \
  --predictions /tmp/predictions.jsonl \
  --codeminder-config /path/to/.codeminder.json \
  --timeout 900 \
  --limit 10
```
Flags:
- `--tasks`: path to SWE-bench tasks JSONL (required).
- `--repo-root`: base dir with `owner__repo` checkouts, unless tasks contain `repo_path` (optional).
- `--agent-cmd`: command template; placeholders `{repo}`, `{repo_name}`, `{instance_id}`, `{task_json}` are substituted. Task JSON is also piped on stdin (required).
- `--predictions`: where to write predictions JSONL (default `predictions.jsonl`).
- `--codeminder-config`: pass to agent via `CODEMINDER_CONFIG` env (optional).
- `--timeout`: per-task timeout seconds (default 900).
- `--limit`: cap number of tasks for smoke tests (optional).
- `--skip-missing-repo`: skip tasks whose repo is not found locally (optional).

## Evaluate with SWE-bench CLI
Once predictions are produced:
```bash
swebench evaluate --predictions /tmp/predictions.jsonl --tasks /path/to/swebench_lite.jsonl
```
(Install SWE-bench CLI separately; not included here.)

## Notes
- Runner assumes your agent writes the final patch to stdout. Non-zero exit code is treated as failure.
- If using CodeMinder, your agent should read `CODEMINDER_CONFIG` and call the MCP/search tools accordingly.
- Keep timeouts generous for real tasks; use `--limit` for fast smoke tests.
