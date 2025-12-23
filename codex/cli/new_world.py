from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from codex.cli.common import slugify_name  # noqa: E402


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--world", required=True, help="World folder name (Obsidian-friendly)")
	args = parser.parse_args()

	world_name = slugify_name(args.world)
	repo_root = Path(__file__).resolve().parents[1]
	template_dir = repo_root / "worlds" / "_TEMPLATE"
	world_dir = repo_root / "worlds" / world_name

	if world_dir.exists():
		raise SystemExit(f"World already exists: {world_dir}")

	shutil.copytree(template_dir, world_dir)
	print(f"Created world: {world_dir}")


if __name__ == "__main__":
	main()
