from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests


def _guess_mimetype(path: Path) -> str:
	s = path.suffix.lower()
	if s == ".png":
		return "image/png"
	if s in {".jpg", ".jpeg"}:
		return "image/jpeg"
	if s == ".webp":
		return "image/webp"
	return "application/octet-stream"


def _find_repo_root(start: Path) -> Path:
	cur = start.resolve()
	for _ in range(10):
		if (cur / ".git").exists() or (cur / ".env").exists():
			return cur
		if cur.parent == cur:
			break
		cur = cur.parent
	return start.resolve()


def _load_dotenv_if_needed(repo_root: Path) -> None:
	if os.environ.get("OPENAI_API_KEY"):
		return
	env_path = repo_root / ".env"
	if not env_path.exists():
		return
	for line in env_path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, val = line.split("=", 1)
		key = key.strip()
		val = val.strip().strip("\"'")  # minimal parsing
		if key and not os.environ.get(key):
			os.environ[key] = val


def _openai_post_json(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
	resp = requests.post(
		url,
		headers={"Authorization": f"Bearer {api_key}"},
		json=payload,
		timeout=120,
	)
	if resp.status_code >= 400:
		raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text}")
	return resp.json()


def _openai_post_multipart(
	url: str,
	data: dict[str, Any],
	files: list[tuple[str, tuple[str, bytes, str]]],
	api_key: str,
) -> dict[str, Any]:
	resp = requests.post(
		url,
		headers={"Authorization": f"Bearer {api_key}"},
		data=data,
		files=files,
		timeout=180,
	)
	if resp.status_code >= 400:
		raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text}")
	return resp.json()


def _write_b64_image(out_path: Path, b64_json: str) -> None:
	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_bytes(base64.b64decode(b64_json))


def _is_model_not_found(err: Exception) -> bool:
	msg = str(err).lower()
	return ("model" in msg and "not found" in msg) or ("model_not_found" in msg)


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_\\-]+")


def _slugify(name: str) -> str:
	n = name.strip().replace(" ", "_")
	n = _SAFE_NAME_RE.sub("", n)
	n = re.sub(r"_+", "_", n)
	return n


def _resolve_world_dir(repo_root: Path, world: str) -> Path:
	world_slug = _slugify(world)
	candidates = [
		repo_root / "worlds" / world_slug,
		repo_root / "codex" / "worlds" / world_slug,
	]
	return next((p for p in candidates if p.exists()), candidates[0])


def _load_world_style_prompt(world_dir: Path) -> str | None:
	style_path = world_dir / "ART_STYLE.md"
	if not style_path.exists():
		return None
	lines = style_path.read_text(encoding="utf-8").splitlines()

	def collect(after_heading: str) -> list[str]:
		out: list[str] = []
		in_section = False
		for raw in lines:
			line = raw.strip()
			if line.startswith("#"):
				in_section = (line.lower() == after_heading.lower())
				continue
			if not in_section:
				continue
			if line.startswith("## "):
				break
			if line.startswith("- "):
				out.append(line[2:].strip())
		return out

	# Keep it short and stable: baseline + composition only.
	baseline = collect("## Baseline Look")
	composition = collect("## Composition Notes")
	parts = []
	if baseline:
		parts.append("Baseline look: " + "; ".join(baseline))
	if composition:
		parts.append("Composition: " + "; ".join(composition))
	if not parts:
		return None
	return "WORLD STYLE PACK (use consistently): " + " | ".join(parts)


def _resolve_world_style_refs(world_dir: Path) -> list[Path]:
	"""
	Optional extra anchors for the edits endpoint. Intended to be low-bias
	(ink grain, lighting, material texture), stored in `lore/_style/`.
	"""
	style_dir = world_dir / "lore" / "_style"
	if not style_dir.exists():
		return []
	candidates: list[Path] = []
	for name in [
		"style_ref.png",
		"style_ref.jpg",
		"style_ref.jpeg",
		f"{world_dir.name}_style_ref.png",
		f"{world_dir.name}_style_ref.jpg",
	]:
		p = style_dir / name
		if p.exists() and p.is_file():
			candidates.append(p.resolve())
	# De-dupe
	seen: set[str] = set()
	out: list[Path] = []
	for p in candidates:
		s = str(p)
		if s in seen:
			continue
		seen.add(s)
		out.append(p)
	return out


def _choose_size(size_arg: str, prompt: str, out_path: Path) -> str:
	if size_arg and size_arg.lower() != "auto":
		return size_arg

	hint = f"{out_path.stem} {prompt}".lower()
	if any(k in hint for k in ["wide", "establishing", "rollout", "tunnel", "arena", "thresh", "gate"]):
		return "1536x1024"
	if any(k in hint for k in ["tall", "full-body", "full body", "standing"]):
		return "1024x1536"
	# closeups/macros/portraits default to square
	return "1024x1024"


def _write_meta(meta_path: Path, payload: dict[str, Any]) -> None:
	meta_path.parent.mkdir(parents=True, exist_ok=True)
	meta_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--prompt", required=True)
	parser.add_argument("--out", required=True, help="Output image path (.png/.jpg based on --output-format)")
	parser.add_argument("--world", default=None, help="Optional world name to inject ART_STYLE.md into the prompt")
	parser.add_argument("--model", default="gpt-image-1.5")
	parser.add_argument("--fallback-model", default="gpt-image-1")
	parser.add_argument("--size", default="1024x1024", help='Image size (e.g. "1024x1024") or "auto"')
	parser.add_argument("--quality", default="high", choices=["low", "medium", "high"])
	parser.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"])
	parser.add_argument("--background", default=None, choices=[None, "transparent", "opaque"])
	parser.add_argument("--n", type=int, default=1, help="Number of images to request (writes *_01, *_02... if >1)")
	parser.add_argument("--input-image", action="append", default=[], help="Reference images for edits endpoint")
	parser.add_argument("--mask", default=None, help="Optional mask image path for edits endpoint")
	parser.add_argument(
		"--use-style-refs",
		action="store_true",
		help="When using the edits endpoint, also add world style reference images from `lore/_style/` if present",
	)
	parser.add_argument(
		"--no-world-style",
		action="store_true",
		help="Do not inject world ART_STYLE.md into the prompt (even if --world is provided)",
	)
	parser.add_argument(
		"--write-meta",
		action="store_true",
		help="Write sidecar JSON metadata files under a sibling `_meta/` folder (recommended)",
	)
	parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com"))
	args = parser.parse_args()

	repo_root = _find_repo_root(Path(__file__))
	_load_dotenv_if_needed(repo_root)

	api_key = os.environ.get("OPENAI_API_KEY")
	if not api_key:
		raise SystemExit("Missing OPENAI_API_KEY (set env var or add it to repo .env)")

	out_path = Path(args.out)
	if args.n < 1 or args.n > 10:
		raise SystemExit("--n must be between 1 and 10")

	world_dir: Path | None = None
	style_prompt: str | None = None
	if args.world:
		world_dir = _resolve_world_dir(repo_root, args.world)
		if not args.no_world_style:
			style_prompt = _load_world_style_prompt(world_dir)

	size = _choose_size(str(args.size), str(args.prompt), out_path)

	final_prompt = str(args.prompt).strip()
	if style_prompt:
		final_prompt = f"{style_prompt}\n\n{final_prompt}"

	# Add stable constraints to reduce drift.
	final_prompt = f"{final_prompt}\n\nConstraints: no text, no watermark."

	input_images = [str(p) for p in (args.input_image or [])]

	use_edits = len(input_images) > 0 or args.mask is not None
	if use_edits and args.use_style_refs and world_dir is not None:
		for p in _resolve_world_style_refs(world_dir):
			if str(p) not in input_images:
				input_images.append(str(p))

	endpoint = "/v1/images/edits" if use_edits else "/v1/images/generations"
	url = args.base_url.rstrip("/") + endpoint

	def run_with_model(model_name: str) -> dict[str, Any]:
		if use_edits:
			files: list[tuple[str, tuple[str, bytes, str]]] = []
			for p in input_images:
				pp = Path(p)
				files.append(("image[]", (pp.name, pp.read_bytes(), _guess_mimetype(pp))))
			if args.mask:
				mp = Path(args.mask)
				files.append(("mask", (mp.name, mp.read_bytes(), _guess_mimetype(mp))))
			data: dict[str, Any] = {
				"model": model_name,
				"prompt": final_prompt,
				"size": size,
				"quality": args.quality,
				"output_format": args.output_format,
				"n": str(args.n),
			}
			if args.background:
				data["background"] = args.background
			return _openai_post_multipart(url, data=data, files=files, api_key=api_key)

		payload: dict[str, Any] = {
			"model": model_name,
			"prompt": final_prompt,
			"size": size,
			"quality": args.quality,
			"output_format": args.output_format,
			"n": args.n,
		}
		if args.background:
			payload["background"] = args.background
		return _openai_post_json(url, payload=payload, api_key=api_key)

	try:
		result = run_with_model(args.model)
		model_used = args.model
	except Exception as e:
		if args.fallback_model and _is_model_not_found(e):
			result = run_with_model(args.fallback_model)
			model_used = args.fallback_model
		else:
			raise

	data = result.get("data") or []
	if not isinstance(data, list) or len(data) == 0:
		raise SystemExit(f"Unexpected response shape (no data): {result}")

	stem = out_path.stem
	suffix = out_path.suffix or f".{args.output_format}"
	parent = out_path.parent

	written: list[str] = []
	for idx, item in enumerate(data, start=1):
		b64_json = item.get("b64_json")
		if not b64_json:
			raise SystemExit(f"Unexpected response item (missing b64_json): {item}")
		target = out_path
		if args.n > 1:
			target = parent / f"{stem}_{idx:02d}{suffix}"
		_write_b64_image(target, b64_json)
		written.append(str(target))

	# Machine-readable summary for agents.
	meta_written: list[str] = []
	if args.write_meta:
		now = dt.datetime.now(dt.timezone.utc).isoformat()
		for f in written:
			fp = Path(f)
			meta_path = fp.parent / "_meta" / f"{fp.name}.json"
			_write_meta(
				meta_path,
				{
					"created_at": now,
					"world": args.world,
					"out": str(fp),
					"model_used": model_used,
					"endpoint": endpoint,
					"size": size,
					"quality": args.quality,
					"output_format": args.output_format,
					"background": args.background,
					"prompt_user": str(args.prompt),
					"prompt_final": final_prompt,
					"input_images": input_images,
					"mask": args.mask,
				},
			)
			meta_written.append(str(meta_path))

	print(
		json.dumps(
			{
				"model_used": model_used,
				"endpoint": endpoint,
				"files": written,
				"size": size,
				"world": args.world,
				"meta_files": meta_written,
			}
		)
	)


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		raise
	except Exception as e:
		print(str(e), file=sys.stderr)
		sys.exit(1)
