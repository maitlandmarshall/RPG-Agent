from __future__ import annotations

import re


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_\\-]+")


def slugify_name(name: str) -> str:
	"""
	Keep Obsidian-friendly file/folder names:
	- letters, numbers, underscore, dash
	- spaces -> underscore
	"""
	n = name.strip().replace(" ", "_")
	n = _SAFE_NAME_RE.sub("", n)
	n = re.sub(r"_+", "_", n)
	if not n or n in {".", ".."}:
		raise ValueError(f"Invalid name: {name!r}")
	return n


