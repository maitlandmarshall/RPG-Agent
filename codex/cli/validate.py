from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from codex.engine.validate import validate_campaign  # noqa: E402


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--world", required=True)
	parser.add_argument("--campaign", required=True)
	args = parser.parse_args()

	repo_root = Path(__file__).resolve().parents[1]
	world_dir = repo_root / "worlds" / args.world
	validate_campaign(world_dir=world_dir, campaign=args.campaign)
	print(f"OK {args.world}/{args.campaign}")


if __name__ == "__main__":
	main()

