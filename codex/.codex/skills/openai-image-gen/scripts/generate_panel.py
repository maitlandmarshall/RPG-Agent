from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
OBSIDIAN_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")


def _find_repo_root(start: Path) -> Path:
	cur = start.resolve()
	for _ in range(10):
		if (cur / ".git").exists() or (cur / ".env").exists():
			return cur
		if cur.parent == cur:
			break
		cur = cur.parent
	return start.resolve()


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_\-]+")


def _slugify(name: str) -> str:
	n = name.strip().replace(" ", "_")
	n = _SAFE_NAME_RE.sub("", n)
	n = re.sub(r"_+", "_", n)
	return n


def _iter_image_refs(markdown: str) -> list[str]:
	refs: list[str] = []
	for m in MD_IMAGE_RE.finditer(markdown):
		refs.append((m.group(1) or "").strip().strip("\"'"))
	for m in OBSIDIAN_EMBED_RE.finditer(markdown):
		refs.append((m.group(1) or "").strip())
	return [r for r in refs if r and not r.startswith(("http://", "https://", "data:"))]


def _resolve_images_from_markdown(entry_path: Path) -> list[Path]:
	raw = entry_path.read_text(encoding="utf-8")
	found: list[Path] = []
	for ref in _iter_image_refs(raw):
		ref_path = ref.split("|", 1)[0].strip()
		candidate = (entry_path.parent / ref_path).resolve()
		if candidate.exists() and candidate.is_file():
			found.append(candidate)
	return found


def _resolve_character_refs(world_dir: Path, character_name: str) -> list[Path]:
	"""
	Resolution strategy (first match wins by order, but returns all existing):
	1) Parse images embedded in lore entry markdown.
	2) Look for common files under a character folder.
	3) Look for a direct image named after the character.
	"""
	characters_dir = world_dir / "lore" / "characters"
	slug = _slugify(character_name)

	entry_candidates = [
		characters_dir / f"{character_name}.md",
		characters_dir / f"{slug}.md",
	]
	images: list[Path] = []
	for entry in entry_candidates:
		if entry.exists():
			images.extend(_resolve_images_from_markdown(entry))

	folder_candidates = [
		characters_dir / character_name,
		characters_dir / slug,
	]
	common_names = [
		"portrait.png",
		"portrait.jpg",
		"portrait.jpeg",
		"view.png",
		"view.jpg",
		"profile.png",
	]
	for folder in folder_candidates:
		if folder.exists() and folder.is_dir():
			for n in common_names:
				p = folder / n
				if p.exists():
					images.append(p.resolve())

	direct_candidates = [
		characters_dir / f"{character_name}.png",
		characters_dir / f"{character_name}.jpg",
		characters_dir / f"{slug}.png",
		characters_dir / f"{slug}.jpg",
	]
	for p in direct_candidates:
		if p.exists():
			images.append(p.resolve())

	# De-dupe, preserve order
	seen: set[str] = set()
	out: list[Path] = []
	for p in images:
		key = str(p)
		if key in seen:
			continue
		seen.add(key)
		out.append(p)
	return out


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--world", required=True, help="World folder name under codex/worlds/")
	parser.add_argument("--prompt", required=True)
	parser.add_argument("--out", required=True)
	parser.add_argument("--character", action="append", default=[], help="Character name to resolve as reference")
	parser.add_argument("--max-refs-per-character", type=int, default=2)

	# Pass-through args to generate_image.py
	parser.add_argument("--model", default="gpt-image-1.5")
	parser.add_argument("--fallback-model", default="gpt-image-1")
	parser.add_argument("--size", default="1024x1024")
	parser.add_argument("--quality", default="high", choices=["low", "medium", "high"])
	parser.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"])
	parser.add_argument("--background", default=None, choices=[None, "transparent", "opaque"])
	parser.add_argument("--n", type=int, default=1)
	parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com"))
	args = parser.parse_args()

	repo_root = _find_repo_root(Path(__file__))
	# Support both layouts:
	# - repo_root points at monorepo root (contains `codex/`)
	# - repo_root points at the `codex/` folder itself (contains `worlds/`)
	world_slug = _slugify(args.world)
	world_dir_candidates = [
		repo_root / "worlds" / world_slug,
		repo_root / "codex" / "worlds" / world_slug,
	]
	world_dir = next((p for p in world_dir_candidates if p.exists()), world_dir_candidates[0])
	if not world_dir.exists():
		raise SystemExit(f"World not found: {world_dir}")

	ref_images: list[Path] = []
	ref_map: dict[str, list[str]] = {}
	for c in args.character:
		refs = _resolve_character_refs(world_dir, c)[: args.max_refs_per_character]
		ref_map[c] = [str(p) for p in refs]
		ref_images.extend(refs)

	generate_image_py = Path(__file__).parent / "generate_image.py"
	cmd: list[str] = [
		sys.executable,
		str(generate_image_py),
		"--prompt",
		args.prompt,
		"--out",
		args.out,
		"--model",
		args.model,
		"--fallback-model",
		args.fallback_model,
		"--size",
		args.size,
		"--quality",
		args.quality,
		"--output-format",
		args.output_format,
		"--n",
		str(args.n),
		"--base-url",
		args.base_url,
	]
	if args.background:
		cmd += ["--background", args.background]
	for p in ref_images:
		cmd += ["--input-image", str(p)]

	proc = subprocess.run(cmd, capture_output=True, text=True)
	if proc.returncode != 0:
		sys.stderr.write(proc.stderr)
		sys.exit(proc.returncode)

	# generate_image.py prints JSON on stdout
	try:
		out = json.loads(proc.stdout.strip().splitlines()[-1])
	except Exception:
		out = {"raw_stdout": proc.stdout}

	out["references"] = ref_map
	print(json.dumps(out))


if __name__ == "__main__":
	main()
