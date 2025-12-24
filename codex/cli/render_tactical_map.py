from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from codex.cli.common import slugify_name  # noqa: E402
from codex.engine.yaml_io import read_yaml_file  # noqa: E402


def _require_mapping(label: str, v: Any) -> dict[str, Any]:
	if not isinstance(v, dict):
		raise ValueError(f"{label} must be a mapping/object")
	return v


def _require_list(label: str, v: Any) -> list[Any]:
	if not isinstance(v, list):
		raise ValueError(f"{label} must be a list/array")
	return v


def _require_str(label: str, v: Any) -> str:
	if not isinstance(v, str) or not v.strip():
		raise ValueError(f"{label} must be a non-empty string")
	return v


def _require_int(label: str, v: Any) -> int:
	if not isinstance(v, (int, float)):
		raise ValueError(f"{label} must be a number")
	i = int(v)
	if i <= 0:
		raise ValueError(f"{label} must be > 0")
	return i


def _require_pos(label: str, v: Any) -> tuple[float, float]:
	if not isinstance(v, list) or len(v) != 2:
		raise ValueError(f"{label} must be [x, y]")
	x, y = v
	if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
		raise ValueError(f"{label} must be [number, number]")
	return float(x), float(y)


def _rel_href(from_path: Path, target: Path) -> str:
	# Compute a relative href between arbitrary siblings (Path.relative_to requires subpaths).
	rel = os.path.relpath(str(target.resolve()), start=str(from_path.resolve().parent))
	return Path(rel).as_posix()


def _svg_escape(text: str) -> str:
	return (
		text.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
		.replace("'", "&#39;")
	)


def _data_uri_for_image(path: Path) -> str:
	mime, _ = mimetypes.guess_type(str(path))
	if not mime:
		mime = "application/octet-stream"
	b64 = base64.b64encode(path.read_bytes()).decode("ascii")
	return f"data:{mime};base64,{b64}"


def render_svg(campaign_dir: Path, config: dict[str, Any], out_path: Path, draw_grid: bool) -> str:
	map_cfg = _require_mapping("map", config.get("map"))
	grid_cfg = _require_mapping("map.grid", map_cfg.get("grid"))
	embed_images = bool(map_cfg.get("embed_images") or False)

	cols = _require_int("map.grid.cols", grid_cfg.get("cols"))
	rows = _require_int("map.grid.rows", grid_cfg.get("rows"))
	cell_px = _require_int("map.grid.cell_px", grid_cfg.get("cell_px"))

	width = cols * cell_px
	height = rows * cell_px

	bg_rel = _require_str("map.background", map_cfg.get("background"))
	bg_path = (campaign_dir / bg_rel).resolve()
	if not bg_path.exists():
		raise FileNotFoundError(f"Missing map background: {bg_rel} (resolved: {bg_path})")

	tokens = _require_list("tokens", config.get("tokens"))

	bg_href = _data_uri_for_image(bg_path) if embed_images else _rel_href(out_path, bg_path)

	lines: list[str] = []
	lines.append('<?xml version="1.0" encoding="UTF-8"?>\n')
	lines.append(
		f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
		f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
	)
	lines.append(f'  <image href="{_svg_escape(bg_href)}" x="0" y="0" width="{width}" height="{height}" />\n')

	if draw_grid:
		lines.append('  <g id="grid" opacity="0.25">\n')
		for x in range(0, width + 1, cell_px):
			lines.append(f'    <line x1="{x}" y1="0" x2="{x}" y2="{height}" stroke="#ffffff" stroke-width="1" />\n')
		for y in range(0, height + 1, cell_px):
			lines.append(f'    <line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="#ffffff" stroke-width="1" />\n')
		lines.append("  </g>\n")

	lines.append('  <defs>\n')
	lines.append('    <filter id="tokenShadow" x="-20%" y="-20%" width="140%" height="140%">\n')
	lines.append('      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.65"/>\n')
	lines.append("    </filter>\n")
	lines.append("  </defs>\n")

	lines.append('  <g id="tokens">\n')
	for idx, tok_any in enumerate(tokens):
		tok = _require_mapping(f"tokens[{idx}]", tok_any)
		tok_id = _require_str(f"tokens[{idx}].id", tok.get("id"))
		img_rel = _require_str(f"tokens[{idx}].image", tok.get("image"))
		at_x, at_y = _require_pos(f"tokens[{idx}].at", tok.get("at"))
		size_cells = int(tok.get("size") or 1)
		if size_cells <= 0:
			size_cells = 1

		img_path = (campaign_dir / img_rel).resolve()
		if not img_path.exists():
			raise FileNotFoundError(f"Missing token image: {img_rel} (resolved: {img_path})")

		# Coordinates are 1-based grid cells: [col, row]
		col = int(at_x)
		row = int(at_y)
		x = (col - 1) * cell_px
		y = (row - 1) * cell_px
		token_px = size_cells * cell_px

		href = _data_uri_for_image(img_path) if embed_images else _rel_href(out_path, img_path)
		clip_id = f"clip_{tok_id}"
		cx = x + token_px / 2
		cy = y + token_px / 2
		r = token_px / 2 - 6

		lines.append(f'    <defs>\n')
		lines.append(f'      <clipPath id="{_svg_escape(clip_id)}">\n')
		lines.append(f'        <circle cx="{cx}" cy="{cy}" r="{r}" />\n')
		lines.append("      </clipPath>\n")
		lines.append("    </defs>\n")

		lines.append(
			f'    <g id="{_svg_escape(tok_id)}" filter="url(#tokenShadow)">\n'
			f'      <circle cx="{cx}" cy="{cy}" r="{r + 5}" fill="rgba(0,0,0,0.45)" stroke="rgba(255,255,255,0.7)" stroke-width="2" />\n'
			f'      <image href="{_svg_escape(href)}" x="{x + 6}" y="{y + 6}" width="{token_px - 12}" height="{token_px - 12}" clip-path="url(#{_svg_escape(clip_id)})" />\n'
		)
		label = tok.get("label")
		if isinstance(label, str) and label.strip():
			lines.append(
				f'      <text x="{cx}" y="{y + token_px - 6}" text-anchor="middle" '
				f'font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI" font-size="14" '
				f'fill="rgba(255,255,255,0.9)" stroke="rgba(0,0,0,0.65)" stroke-width="3" paint-order="stroke">\n'
				f'        {_svg_escape(label.strip())}\n'
				f"      </text>\n"
			)
		lines.append("    </g>\n")

	lines.append("  </g>\n")
	lines.append("</svg>\n")
	return "".join(lines)


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--world", required=True)
	parser.add_argument("--campaign", required=True)
	parser.add_argument(
		"--map-yaml",
		default="tactical_map.yaml",
		help="Campaign-root-relative tactical map YAML (default: tactical_map.yaml)",
	)
	parser.add_argument("--out", default=None, help="Override output SVG path (campaign-root-relative)")
	parser.add_argument("--draw-grid", action="store_true", help="Draw a debug grid overlay in the SVG")
	parser.add_argument(
		"--embed-images",
		action="store_true",
		help="Embed referenced PNG/JPGs as data URIs for viewers that block external SVG image loads",
	)
	parser.add_argument(
		"--no-embed-images",
		action="store_true",
		help="Force file-based hrefs even if tactical_map.yaml sets map.embed_images",
	)
	args = parser.parse_args()

	world = slugify_name(args.world)
	campaign = slugify_name(args.campaign)

	repo_root = Path(__file__).resolve().parents[1]
	campaign_dir = repo_root / "worlds" / world / "campaigns" / campaign

	cfg_path = (campaign_dir / args.map_yaml).resolve()
	if not cfg_path.exists():
		raise SystemExit(f"Missing tactical map YAML: {cfg_path}")
	cfg_any = read_yaml_file(cfg_path)
	cfg = _require_mapping("tactical_map.yaml", cfg_any)

	map_cfg = _require_mapping("map", cfg.get("map"))
	out_rel = args.out or map_cfg.get("output_svg") or "assets/maps/tactical_map.svg"
	out_path = (campaign_dir / str(out_rel)).resolve()
	out_path.parent.mkdir(parents=True, exist_ok=True)

	# CLI flags override YAML.
	if args.embed_images:
		map_cfg["embed_images"] = True
	if args.no_embed_images:
		map_cfg["embed_images"] = False

	svg = render_svg(campaign_dir=campaign_dir, config=cfg, out_path=out_path, draw_grid=bool(args.draw_grid))
	out_path.write_text(svg, encoding="utf-8")
	print(f"Wrote {out_path.relative_to(campaign_dir)}")


if __name__ == "__main__":
	main()
