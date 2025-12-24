from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--world", required=True)
	parser.add_argument("--character", required=True, help="Character name to resolve as reference (lore portrait)")
	parser.add_argument("--out", required=True, help="Output token image path (.png recommended)")

	parser.add_argument("--size", default="1024x1024")
	parser.add_argument("--quality", default="high", choices=["low", "medium", "high"])
	parser.add_argument("--model", default="gpt-image-1.5")
	parser.add_argument("--fallback-model", default="gpt-image-1")
	parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com"))
	parser.add_argument("--write-meta", action="store_true", help="Write sidecar JSON metadata under `_meta/`")
	parser.add_argument("--use-style-refs", action="store_true", help="Add world style refs from `lore/_style/`")
	parser.add_argument(
		"--prompt-extra",
		default="",
		help="Optional extra prompt text (kept short; appended at end).",
	)
	args = parser.parse_args()

	prompt = (
		"Top-down D&D-style battle token for a tactical grid map. "
		"Single character centered, viewed from above, clear silhouette, readable pose, "
		"gritty sci-fi gladiator vibe, inked line art with tight cross-hatching, high contrast rim light. "
		"Keep the character visually consistent with the reference image. "
		"Transparent background, no border frame, no text, no watermark. "
	).strip()
	if args.prompt_extra.strip():
		prompt += " " + args.prompt_extra.strip()

	generate_panel_py = Path(__file__).parent / "generate_panel.py"
	cmd: list[str] = [
		sys.executable,
		str(generate_panel_py),
		"--world",
		args.world,
		"--character",
		args.character,
		"--prompt",
		prompt,
		"--out",
		args.out,
		"--size",
		args.size,
		"--quality",
		args.quality,
		"--model",
		args.model,
		"--fallback-model",
		args.fallback_model,
		"--background",
		"transparent",
		"--base-url",
		args.base_url,
	]
	if args.write_meta:
		cmd += ["--write-meta"]
	if args.use_style_refs:
		cmd += ["--use-style-refs"]

	proc = subprocess.run(cmd)
	raise SystemExit(proc.returncode)


if __name__ == "__main__":
	main()

