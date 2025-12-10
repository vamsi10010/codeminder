"""Lightweight runner to produce SWE-bench predictions using an external agent.

This does NOT bundle SWE-bench or clone repos. It assumes:
1) You have SWE-bench tasks JSONL locally (e.g., swebench_lite_*).
2) You have local checkouts of the repos referenced by the tasks.
3) You provide an agent command that, given a repo and task JSON, emits a patch on stdout.
4) Optionally, your agent can use CodeMinder (e.g., via env vars) for retrieval.

Output: predictions JSONL suitable for SWE-bench's evaluator.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def load_tasks(tasks_path: Path, limit: int | None) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with tasks_path.open() as f:
        for idx, line in enumerate(f):
            if limit is not None and idx >= limit:
                break
            line = line.strip()
            if not line:
                continue
            tasks.append(json.loads(line))
    return tasks


def resolve_repo_path(task: dict[str, Any], repo_root: Path | None) -> Path | None:
    if "repo_path" in task:
        path = Path(task["repo_path"])
        return path if path.exists() else None

    repo_name = task.get("repo")
    if not repo_name or not repo_root:
        return None
    # Map owner/repo -> owner__repo directory under repo_root
    candidate = repo_root / repo_name.replace("/", "__")
    return candidate if candidate.exists() else None


def run_agent(
    agent_cmd: str,
    repo_path: Path,
    task: dict[str, Any],
    timeout: int,
    extra_env: dict[str, str],
) -> tuple[int, str, str, float]:
    task_json = json.dumps(task)
    formatted_cmd = agent_cmd.format(
        repo=str(repo_path),
        repo_name=task.get("repo", ""),
        instance_id=task.get("instance_id", ""),
        task_json=task_json,
    )
    start = time.time()
    proc = subprocess.run(
        shlex.split(formatted_cmd),
        input=task_json.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo_path,
        env={**os.environ, **extra_env},
        timeout=timeout,
    )
    duration = time.time() - start
    stdout = proc.stdout.decode(errors="replace")
    stderr = proc.stderr.decode(errors="replace")
    return proc.returncode, stdout, stderr, duration


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SWE-bench tasks through an agent and emit predictions JSONL")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to SWE-bench tasks JSONL")
    parser.add_argument("--repo-root", type=Path, help="Base dir containing checked-out repos (owner__repo naming)")
    parser.add_argument(
        "--agent-cmd",
        type=str,
        required=True,
        help=(
            "Command template to run the agent. Placeholders: "
            "{repo} {repo_name} {instance_id} {task_json}. "
            "The task JSON is also passed on stdin."
        ),
    )
    parser.add_argument("--predictions", type=Path, default=Path("predictions.jsonl"), help="Where to write predictions JSONL")
    parser.add_argument("--limit", type=int, help="Max tasks to run (for smoke tests)")
    parser.add_argument("--timeout", type=int, default=900, help="Per-task timeout in seconds")
    parser.add_argument("--codeminder-config", type=Path, help="Path to .codeminder.json to expose to the agent (optional)")
    parser.add_argument(
        "--skip-missing-repo",
        action="store_true",
        help="Skip tasks whose repo cannot be resolved locally",
    )
    args = parser.parse_args()

    tasks = load_tasks(args.tasks, args.limit)
    if not tasks:
        print("No tasks loaded; check --tasks path", file=sys.stderr)
        sys.exit(1)

    predictions: list[str] = []
    failures: list[dict[str, Any]] = []

    extra_env: dict[str, str] = {}
    if args.codeminder_config:
        extra_env["CODEMINDER_CONFIG"] = str(args.codeminder_config)

    for task in tasks:
        instance_id = task.get("instance_id", "unknown")
        repo_path = resolve_repo_path(task, args.repo_root)
        if not repo_path:
            msg = f"[{instance_id}] repo not found; set repo_path in task or provide --repo-root"
            if args.skip_missing_repo:
                print(msg, file=sys.stderr)
                continue
            else:
                raise FileNotFoundError(msg)

        try:
            code, stdout, stderr, duration = run_agent(
                args.agent_cmd,
                repo_path,
                task,
                timeout=args.timeout,
                extra_env=extra_env,
            )
        except subprocess.TimeoutExpired:
            failures.append({"instance_id": instance_id, "error": "timeout"})
            print(f"[{instance_id}] timeout after {args.timeout}s", file=sys.stderr)
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append({"instance_id": instance_id, "error": str(exc)})
            print(f"[{instance_id}] failed: {exc}", file=sys.stderr)
            continue

        if code != 0:
            failures.append({"instance_id": instance_id, "error": stderr.strip()})
            print(f"[{instance_id}] agent exited {code}: {stderr}", file=sys.stderr)
            continue

        model_patch = stdout.strip()
        predictions.append(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "model_patch": model_patch,
                    "model_name_or_path": "agent-with-codeminder",
                    "elapsed_seconds": round(duration, 2),
                }
            )
        )
        print(f"[{instance_id}] ok in {duration:.1f}s")

    args.predictions.parent.mkdir(parents=True, exist_ok=True)
    with args.predictions.open("w") as f:
        for line in predictions:
            f.write(line + "\n")

    print(f"\nWrote {len(predictions)} predictions to {args.predictions}")
    if failures:
        print(f"{len(failures)} failures (see stderr for details)")
    print(
        "Next: evaluate with SWE-bench CLI, e.g.\n"
        f"swebench evaluate --predictions {args.predictions} --tasks {args.tasks}"
    )


if __name__ == "__main__":
    main()
