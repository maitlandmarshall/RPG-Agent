from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_jobs(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
	text = path.read_text(encoding="utf-8")
	if path.suffix.lower() == ".jsonl":
		defaults: dict[str, Any] = {}
		jobs: list[dict[str, Any]] = []
		for raw in text.splitlines():
			line = raw.strip()
			if not line or line.startswith("#"):
				continue
			obj = json.loads(line)
			if isinstance(obj, dict) and obj.get("defaults") and obj.get("jobs") is None:
				# Allow a single defaults-only line, then per-job lines.
				defaults = dict(obj.get("defaults") or {})
				continue
			if not isinstance(obj, dict):
				raise SystemExit("Each .jsonl line must be a JSON object")
			jobs.append(obj)
		return defaults, jobs

	obj = json.loads(text)
	if isinstance(obj, list):
		return {}, obj
	if isinstance(obj, dict):
		defaults = dict(obj.get("defaults") or {})
		jobs = obj.get("jobs")
		if not isinstance(jobs, list):
			raise SystemExit('Jobs JSON must be a list, or an object with key "jobs"')
		return defaults, jobs
	raise SystemExit("Jobs file must be JSON list/object or JSONL")


def _merge(defaults: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
	out = dict(defaults)
	out.update(job)
	return out


def _append_opt(cmd: list[str], key: str, val: Any) -> None:
	if val is None:
		return
	cmd.extend([key, str(val)])


def _append_repeat(cmd: list[str], key: str, vals: Any) -> None:
	if not vals:
		return
	if isinstance(vals, (str, Path)):
		cmd.extend([key, str(vals)])
		return
	if not isinstance(vals, list):
		raise SystemExit(f"{key} must be a list (got {type(vals).__name__})")
	for v in vals:
		cmd.extend([key, str(v)])


def _infer_type(job: dict[str, Any]) -> str:
	t = (job.get("type") or "").strip().lower()
	if t:
		return t
	# "world" can also be used for image jobs (style injection), so only infer
	# panel when explicit characters are present.
	if job.get("characters") or job.get("character"):
		return "panel"
	return "image"


def _build_cmd(job: dict[str, Any]) -> list[str]:
	scripts_dir = Path(__file__).parent
	job_type = _infer_type(job)
	prompt = job.get("prompt")
	out = job.get("out")
	if not prompt or not out:
		raise SystemExit('Each job must include "prompt" and "out"')

	base_url = job.get("base_url") or job.get("base-url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")

	def _flag_is_true(*keys: str) -> bool:
		for k in keys:
			v = job.get(k)
			if v is True:
				return True
			if isinstance(v, str) and v.strip().lower() in {"1", "true", "yes", "y", "on"}:
				return True
		return False

	common: list[str] = []
	_append_opt(common, "--model", job.get("model"))
	_append_opt(common, "--fallback-model", job.get("fallback_model") or job.get("fallback-model"))
	_append_opt(common, "--size", job.get("size"))
	_append_opt(common, "--quality", job.get("quality"))
	_append_opt(common, "--output-format", job.get("output_format") or job.get("output-format"))
	_append_opt(common, "--background", job.get("background"))
	_append_opt(common, "--n", job.get("n"))
	_append_opt(common, "--base-url", base_url)

	if job_type in {"image", "generate_image"}:
		script = scripts_dir / "generate_image.py"
		cmd = [sys.executable, str(script), "--prompt", str(prompt), "--out", str(out)]
		_append_opt(cmd, "--world", job.get("world"))
		cmd += common
		if _flag_is_true("write_meta", "write-meta"):
			cmd += ["--write-meta"]
		if _flag_is_true("use_style_refs", "use-style-refs"):
			cmd += ["--use-style-refs"]
		if _flag_is_true("no_world_style", "no-world-style"):
			cmd += ["--no-world-style"]
		_append_repeat(cmd, "--input-image", job.get("input_images") or job.get("input-image"))
		_append_opt(cmd, "--mask", job.get("mask"))
		return cmd

	if job_type in {"panel", "generate_panel"}:
		world = job.get("world")
		if not world:
			raise SystemExit('Panel jobs must include "world"')
		script = scripts_dir / "generate_panel.py"
		cmd = [sys.executable, str(script), "--world", str(world), "--prompt", str(prompt), "--out", str(out)]
		cmd += common
		if _flag_is_true("write_meta", "write-meta"):
			cmd += ["--write-meta"]
		if _flag_is_true("use_style_refs", "use-style-refs"):
			cmd += ["--use-style-refs"]
		if _flag_is_true("no_world_style", "no-world-style"):
			cmd += ["--no-world-style"]
		_append_opt(cmd, "--max-refs-per-character", job.get("max_refs_per_character") or job.get("max-refs-per-character"))
		chars = job.get("characters") or job.get("character") or []
		if isinstance(chars, str):
			chars = [chars]
		if not isinstance(chars, list):
			raise SystemExit('"characters" must be a list or string')
		for c in chars:
			cmd += ["--character", str(c)]
		_append_repeat(cmd, "--input-image", job.get("input_images") or job.get("input-image"))
		_append_opt(cmd, "--mask", job.get("mask"))
		return cmd

	raise SystemExit(f'Unknown job type "{job_type}" (expected "image" or "panel")')


@dataclass
class JobResult:
	index: int
	ok: bool
	returncode: int
	seconds: float
	command: list[str]
	stdout: str
	stderr: str
	parsed: dict[str, Any] | None


class _JobFailed(RuntimeError):
	def __init__(self, result: JobResult):
		super().__init__(f"Job {result.index} failed with code {result.returncode}")
		self.result = result


async def _run_one(index: int, cmd: list[str], sem: asyncio.Semaphore) -> JobResult:
	start = time.time()
	async with sem:
		proc = await asyncio.create_subprocess_exec(
			*cmd,
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
		)
		stdout_b, stderr_b = await proc.communicate()
		seconds = time.time() - start

	stdout = (stdout_b or b"").decode("utf-8", errors="replace")
	stderr = (stderr_b or b"").decode("utf-8", errors="replace")

	parsed: dict[str, Any] | None = None
	if stdout.strip():
		try:
			parsed = json.loads(stdout.strip().splitlines()[-1])
		except Exception:
			parsed = None

	return JobResult(
		index=index,
		ok=(proc.returncode == 0),
		returncode=int(proc.returncode or 0),
		seconds=seconds,
		command=cmd,
		stdout=stdout,
		stderr=stderr,
		parsed=parsed,
	)


async def _run_all(cmds: list[list[str]], concurrency: int, fail_fast: bool) -> list[JobResult]:
	sem = asyncio.Semaphore(concurrency)
	results: list[JobResult] = [None] * len(cmds)  # type: ignore[list-item]

	async def runner(i: int, c: list[str]) -> None:
		res = await _run_one(i, c, sem)
		results[i] = res
		if fail_fast and not res.ok:
			raise _JobFailed(res)

	try:
		async with asyncio.TaskGroup() as tg:
			for i, c in enumerate(cmds):
				tg.create_task(runner(i, c))
	except* _JobFailed as eg:
		# TaskGroup cancellation means some results may be None.
		# Prefer the first failure.
		fail = eg.exceptions[0].result
		sys.stderr.write(fail.stderr or fail.stdout)
		raise SystemExit(f"Batch failed fast: job {fail.index} returned {fail.returncode}")

	# mypy: results are fully populated when not fail-fast or after completion
	return results  # type: ignore[return-value]


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--jobs", required=True, help="Path to jobs JSON (.json or .jsonl)")
	parser.add_argument("--concurrency", type=int, default=4)
	parser.add_argument("--fail-fast", action="store_true", help="Stop the batch on first failure")
	parser.add_argument("--dry-run", action="store_true", help="Print commands only, do not call the API")
	args = parser.parse_args()

	jobs_path = Path(args.jobs)
	defaults, raw_jobs = _load_jobs(jobs_path)
	if not raw_jobs:
		raise SystemExit("No jobs found")

	jobs = [_merge(defaults, j) for j in raw_jobs]
	cmds = [_build_cmd(j) for j in jobs]

	if args.dry_run:
		for i, cmd in enumerate(cmds):
			print(json.dumps({"job": i, "command": cmd}))
		return

	concurrency = max(1, int(args.concurrency))
	results = asyncio.run(_run_all(cmds, concurrency=concurrency, fail_fast=bool(args.fail_fast)))

	out: dict[str, Any] = {
		"ok": all(r.ok for r in results),
		"concurrency": concurrency,
		"jobs": [],
		"files": [],
	}
	for r in results:
		entry: dict[str, Any] = {
			"index": r.index,
			"ok": r.ok,
			"returncode": r.returncode,
			"seconds": round(r.seconds, 3),
			"command": r.command,
		}
		if r.parsed is not None:
			entry["result"] = r.parsed
			files = r.parsed.get("files") if isinstance(r.parsed, dict) else None
			if isinstance(files, list):
				out["files"].extend(files)
		else:
			# Keep raw output for debugging; trimmed to avoid overly huge payloads.
			entry["stdout"] = r.stdout[-2000:]
			entry["stderr"] = r.stderr[-2000:]
		out["jobs"].append(entry)

	# Machine-readable summary for agents.
	print(json.dumps(out))
	if not out["ok"]:
		sys.exit(1)


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		raise
	except SystemExit:
		raise
	except Exception as e:
		print(str(e), file=sys.stderr)
		sys.exit(1)
