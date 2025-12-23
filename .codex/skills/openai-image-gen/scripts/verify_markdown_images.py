from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
OBSIDIAN_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")


def _iter_image_refs(markdown: str) -> list[str]:
	refs: list[str] = []
	for m in MD_IMAGE_RE.finditer(markdown):
		refs.append((m.group(1) or "").strip().strip("\"'"))
	for m in OBSIDIAN_EMBED_RE.finditer(markdown):
		refs.append((m.group(1) or "").strip())
	return [r for r in refs if r and not r.startswith(("http://", "https://", "data:"))]


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("files", nargs="+", help="Markdown files to verify")
	args = parser.parse_args()

	missing: list[str] = []
	for f in args.files:
		p = Path(f)
		if not p.exists():
			missing.append(f"{p}: file does not exist")
			continue
		raw = p.read_text(encoding="utf-8")
		for ref in _iter_image_refs(raw):
			# Obsidian embeds can include an alias like "path|alias"
			ref_path = ref.split("|", 1)[0].strip()
			target = (p.parent / ref_path).resolve()
			if not target.exists():
				missing.append(f"{p}: {ref_path} -> {target}")

	if missing:
		print("Missing image references:", file=sys.stderr)
		for m in missing:
			print(f"- {m}", file=sys.stderr)
		sys.exit(1)

	print("OK (all images exist)")


if __name__ == "__main__":
	main()
