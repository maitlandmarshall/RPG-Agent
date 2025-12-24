from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from .yaml_io import read_yaml_file


@dataclass(frozen=True)
class ValidationTarget:
	label: str
	yaml_path: Path
	schema_path: Path


def _load_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def validate_yaml_against_schema(target: ValidationTarget) -> None:
	schema = _load_json(target.schema_path)
	validator = Draft202012Validator(schema)

	data = read_yaml_file(target.yaml_path)
	errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
	if errors:
		lines: list[str] = [f"{target.label} failed schema validation: {target.yaml_path}"]
		for e in errors:
			at = "/" + "/".join(str(p) for p in e.path) if e.path else ""
			lines.append(f"- {e.message}{' at ' + at if at else ''}")
		raise ValueError("\n".join(lines))


def validate_campaign(world_dir: Path, campaign: str) -> None:
	campaign_dir = world_dir / "campaigns" / campaign
	schemas_dir = Path(__file__).parent / "schemas"

	targets = [
		ValidationTarget(
			label="campaign.yaml",
			yaml_path=campaign_dir / "campaign.yaml",
			schema_path=schemas_dir / "campaign.schema.json",
		),
		ValidationTarget(
			label="world_state.yaml",
			yaml_path=campaign_dir / "world_state.yaml",
			schema_path=schemas_dir / "world_state.schema.json",
		),
		ValidationTarget(
			label="player.yaml",
			yaml_path=campaign_dir / "characters" / "player.yaml",
			schema_path=schemas_dir / "player.schema.json",
		),
	]

	# Optional campaign extras (validated if present).
	optional_targets = [
		ValidationTarget(
			label="tactical_map.yaml",
			yaml_path=campaign_dir / "tactical_map.yaml",
			schema_path=schemas_dir / "tactical_map.schema.json",
		),
	]

	for t in targets:
		if not t.yaml_path.exists():
			raise FileNotFoundError(f"Missing required file: {t.yaml_path}")
		validate_yaml_against_schema(t)

	for t in optional_targets:
		if t.yaml_path.exists():
			validate_yaml_against_schema(t)


