from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class DuplicateKeyError(ValueError):
	pass


class UniqueKeyLoader(yaml.SafeLoader):
	pass


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.Node, deep: bool = False) -> dict[str, Any]:
	mapping: dict[str, Any] = {}
	for key_node, value_node in node.value:
		key = loader.construct_object(key_node, deep=deep)
		if key in mapping:
			raise DuplicateKeyError(f"Duplicate YAML key: {key!r}")
		value = loader.construct_object(value_node, deep=deep)
		mapping[key] = value
	return mapping


UniqueKeyLoader.add_constructor(  # type: ignore[arg-type]
	yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def read_yaml_file(path: str | Path) -> Any:
	p = Path(path)
	raw = p.read_text(encoding="utf-8")
	try:
		return yaml.load(raw, Loader=UniqueKeyLoader)
	except DuplicateKeyError as e:
		raise DuplicateKeyError(f"{p}: {e}") from e
	except yaml.YAMLError as e:
		raise ValueError(f"{p}: YAML parse error: {e}") from e


def write_yaml_file(path: str | Path, data: Any) -> None:
	p = Path(path)
	p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

