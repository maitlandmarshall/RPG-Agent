from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from codex.engine.yaml_io import read_yaml_file, write_yaml_file  # noqa: E402

from codex.cli.common import slugify_name  # noqa: E402


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--world", required=True)
	parser.add_argument("--campaign", required=True)
	parser.add_argument("--player-name", required=True)
	parser.add_argument("--location", default="TBD")
	args = parser.parse_args()

	world_name = slugify_name(args.world)
	campaign_name = slugify_name(args.campaign)

	repo_root = Path(__file__).resolve().parents[1]
	world_dir = repo_root / "worlds" / world_name
	template_campaign_dir = world_dir / "campaigns" / "_TEMPLATE"
	campaign_dir = world_dir / "campaigns" / campaign_name

	if not world_dir.exists():
		raise SystemExit(f"World does not exist: {world_dir}")
	if campaign_dir.exists():
		raise SystemExit(f"Campaign already exists: {campaign_dir}")
	if not template_campaign_dir.exists():
		raise SystemExit(f"Missing world campaign template: {template_campaign_dir}")

	shutil.copytree(template_campaign_dir, campaign_dir)

	now = dt.datetime.now(dt.timezone.utc).isoformat()

	campaign_yaml_path = campaign_dir / "campaign.yaml"
	campaign_yaml = read_yaml_file(campaign_yaml_path)
	campaign_yaml["world"] = world_name
	campaign_yaml["campaign"] = campaign_name
	campaign_yaml["created_at"] = now
	campaign_yaml.setdefault("turn_counter", 0)
	write_yaml_file(campaign_yaml_path, campaign_yaml)

	player_yaml_path = campaign_dir / "characters" / "player.yaml"
	player_yaml = read_yaml_file(player_yaml_path)
	player_yaml["name"] = args.player_name
	write_yaml_file(player_yaml_path, player_yaml)

	world_state_path = campaign_dir / "world_state.yaml"
	world_state = read_yaml_file(world_state_path)
	world_state["location"] = args.location
	write_yaml_file(world_state_path, world_state)

	print(f"Created campaign: {campaign_dir}")


if __name__ == "__main__":
	main()
