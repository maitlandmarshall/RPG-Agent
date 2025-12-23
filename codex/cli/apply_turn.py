from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from codex.engine.validate import validate_campaign  # noqa: E402
from codex.engine.yaml_io import read_yaml_file, write_yaml_file  # noqa: E402

from codex.cli.common import slugify_name  # noqa: E402


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _apply_number_delta(container: dict[str, Any], key: str, delta: float) -> None:
	current = container.get(key, 0)
	if not isinstance(current, (int, float)):
		raise ValueError(f"Cannot apply delta to non-number {key!r}: {current!r}")
	container[key] = current + delta


def _apply_set(container: dict[str, Any], key: str, value: Any) -> None:
	container[key] = value


def _extract_local_image_paths(markdown: str) -> list[str]:
	paths: list[str] = []
	for m in _MD_IMAGE_RE.finditer(markdown or ""):
		p = (m.group(1) or "").strip().strip("\"'")
		if not p:
			continue
		if p.startswith(("http://", "https://", "data:")):
			continue
		paths.append(p)
	return paths


def _ensure_images_exist(log_dir: Path, turn: dict[str, Any]) -> None:
	combined = "\n".join(
		[
			str(turn.get("scene_md") or ""),
			str(turn.get("mechanics_md") or ""),
		]
	)
	campaign_root = log_dir.resolve().parent
	for rel in _extract_local_image_paths(combined):
		asset_path = (log_dir / rel).resolve()
		# Ensure path doesn't escape the campaign directory accidentally.
		if not asset_path.is_relative_to(campaign_root):
			raise ValueError(f"Image path escapes log directory: {rel}")
		if not asset_path.exists():
			raise FileNotFoundError(f"Missing image referenced by turn: {rel} (resolved: {asset_path})")


def _ensure_non_negative_resources(resources: dict[str, Any]) -> None:
	for k in ("hp", "fatigue", "hunger"):
		v = resources.get(k)
		if isinstance(v, (int, float)) and v < 0:
			raise ValueError(f"Resource {k!r} cannot go below 0 (got {v})")


def _format_turn_markdown(turn: dict[str, Any]) -> str:
	scene = (turn.get("scene_md") or "").rstrip()
	options = turn.get("options") or []
	changed = turn.get("what_changed") or []
	mech = (turn.get("mechanics_md") or "").rstrip()

	lines: list[str] = []
	lines.append("\n---\n")
	lines.append(f"## Turn — {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
	lines.append("### Scene\n")
	lines.append(scene + "\n" if scene else "_(scene omitted)_\n")

	lines.append("### Your Options\n")
	if options:
		for idx, opt in enumerate(options, start=1):
			lines.append(f"{idx}. {opt}\n")
	else:
		lines.append("1. _(no options provided)_\n")

	lines.append("\n### What Changed\n")
	if changed:
		for c in changed:
			lines.append(f"- {c}\n")
	else:
		lines.append("- _(no changes recorded)_\n")

	lines.append("\n<details>\n<summary>Mechanics</summary>\n\n")
	lines.append(mech + "\n" if mech else "_(mechanics omitted)_\n")
	lines.append("\n</details>\n")

	return "".join(lines)


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--world", required=True)
	parser.add_argument("--campaign", required=True)
	parser.add_argument("--turn-file", required=True, help="YAML file describing this turn")
	args = parser.parse_args()

	world = slugify_name(args.world)
	campaign = slugify_name(args.campaign)

	repo_root = Path(__file__).resolve().parents[1]
	campaign_dir = repo_root / "worlds" / world / "campaigns" / campaign

	turn = read_yaml_file(args.turn_file)
	if not isinstance(turn, dict):
		raise SystemExit("turn-file must be a YAML mapping/object")

	campaign_yaml_path = campaign_dir / "campaign.yaml"
	campaign_yaml = read_yaml_file(campaign_yaml_path)
	log_rel = turn.get("log_file") or campaign_yaml.get("log_active")
	if not log_rel:
		raise SystemExit("No log_file provided and campaign.yaml has no log_active")

	log_path = campaign_dir / log_rel
	if not log_path.exists():
		raise SystemExit(f"Log file does not exist: {log_path}")

	# Validate referenced assets before mutating state/log.
	_ensure_images_exist(log_dir=log_path.parent, turn=turn)

	# Snapshot originals so we can rollback on failure.
	player_path = campaign_dir / "characters" / "player.yaml"
	world_state_path = campaign_dir / "world_state.yaml"

	orig_player = player_path.read_text(encoding="utf-8")
	orig_world_state = world_state_path.read_text(encoding="utf-8")
	orig_campaign = campaign_yaml_path.read_text(encoding="utf-8")
	orig_log = log_path.read_text(encoding="utf-8")

	player = read_yaml_file(player_path)
	world_state = read_yaml_file(world_state_path)

	delta = turn.get("delta") or {}
	if not isinstance(delta, dict):
		raise SystemExit("delta must be a mapping/object")

	player_delta = delta.get("player") or {}
	if not isinstance(player_delta, dict):
		raise SystemExit("delta.player must be a mapping/object")

	resources = player.get("resources") or {}
	stats = player.get("stats") or {}

	for op in player_delta.get("add", []) or []:
		target = op.get("target")
		key = op.get("key")
		val = op.get("value")
		if target == "resources":
			_apply_number_delta(resources, key, float(val))
		elif target == "stats":
			_apply_number_delta(stats, key, float(val))
		elif target == "xp":
			player["xp"] = float(player.get("xp", 0)) + float(val)
		else:
			raise ValueError(f"Unknown add target: {target!r}")

	for op in player_delta.get("set", []) or []:
		target = op.get("target")
		key = op.get("key")
		val = op.get("value")
		if target == "resources":
			_apply_set(resources, key, val)
		elif target == "stats":
			_apply_set(stats, key, val)
		elif target == "xp":
			player["xp"] = val
		else:
			raise ValueError(f"Unknown set target: {target!r}")

	player["resources"] = resources
	player["stats"] = stats
	_ensure_non_negative_resources(resources)

	# Optional world_state updates: replace top-level keys.
	world_delta = delta.get("world_state") or {}
	if world_delta:
		if not isinstance(world_delta, dict):
			raise SystemExit("delta.world_state must be a mapping/object")
		for op in world_delta.get("set", []) or []:
			key = op.get("key")
			val = op.get("value")
			if not isinstance(key, str) or not key:
				raise ValueError("delta.world_state.set entries must include string key")
			world_state[key] = val
		pass

	# Turn counter bookkeeping (only persisted on success)
	campaign_yaml["turn_counter"] = int(campaign_yaml.get("turn_counter", 0)) + 1

	# Optional log rotation (new chapter/session file)
	rotate = turn.get("rotate_log")
	if rotate:
		if not isinstance(rotate, dict):
			raise SystemExit("rotate_log must be a mapping/object")
		new_rel = rotate.get("path")
		title = rotate.get("title") or "New Chapter"
		if not isinstance(new_rel, str) or not new_rel:
			raise SystemExit("rotate_log.path must be a non-empty string like 'campaign_logs/001_Chapter.md'")

		new_path = campaign_dir / new_rel
		new_path.parent.mkdir(parents=True, exist_ok=True)
		if new_path.exists():
			raise SystemExit(f"rotate_log.path already exists: {new_path}")

		new_path.write_text(f"# {title}\n\n", encoding="utf-8")
		campaign_yaml["log_active"] = new_rel
		if "chapter_counter" in campaign_yaml:
			campaign_yaml["chapter_counter"] = int(campaign_yaml.get("chapter_counter", 0)) + 1

	try:
		# Write state
		write_yaml_file(player_path, player)
		write_yaml_file(world_state_path, world_state)
		write_yaml_file(campaign_yaml_path, campaign_yaml)

		# Append to log
		log_path.write_text(orig_log + _format_turn_markdown(turn), encoding="utf-8")

		# Validate after write (ensures we didn't corrupt state)
		validate_campaign(world_dir=repo_root / "worlds" / world, campaign=campaign)
	except Exception:
		# Roll back all touched files.
		player_path.write_text(orig_player, encoding="utf-8")
		world_state_path.write_text(orig_world_state, encoding="utf-8")
		campaign_yaml_path.write_text(orig_campaign, encoding="utf-8")
		log_path.write_text(orig_log, encoding="utf-8")
		raise

	print(f"Applied turn to {world}/{campaign} -> {log_rel}")


if __name__ == "__main__":
	main()
