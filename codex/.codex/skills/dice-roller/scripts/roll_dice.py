from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import re
import secrets
from pathlib import Path
from typing import Any, Literal


TermKind = Literal["dice", "modifier"]


@dataclasses.dataclass(frozen=True)
class DiceTerm:
	kind: Literal["dice"]
	count: int
	sides: int


@dataclasses.dataclass(frozen=True)
class ModifierTerm:
	kind: Literal["modifier"]
	value: int


Term = DiceTerm | ModifierTerm


_TERM_RE = re.compile(r"^\s*(?:(\d*)d(\d+)|([+-]?\d+))\s*$", re.IGNORECASE)


def _parse_expr(expr: str) -> list[Term]:
	if not expr or not expr.strip():
		raise ValueError("expr must be non-empty")

	# Allow either "d20+5-1" or "d20 + 5 - 1" by normalizing separators.
	normalized = (
		expr.replace("-", " - ")
		.replace("+", " + ")
		.replace("\t", " ")
		.replace("\n", " ")
	)
	parts = [p for p in (x.strip() for x in normalized.split()) if p]

	# Re-stitch unary signs into numbers where possible.
	# Example: ["d20", "+", "5", "-", "1"] -> ["d20", "+5", "-1"]
	stitched: list[str] = []
	i = 0
	while i < len(parts):
		p = parts[i]
		if p in {"+", "-"}:
			if i + 1 >= len(parts):
				raise ValueError(f"Dangling operator at end of expression: {expr!r}")
			nxt = parts[i + 1]
			stitched.append(p + nxt)
			i += 2
			continue
		stitched.append(p)
		i += 1

	terms: list[Term] = []
	for raw in stitched:
		m = _TERM_RE.match(raw)
		if not m:
			raise ValueError(f"Unsupported token {raw!r} in expr {expr!r}. Use dice like 'd20' or numbers like '+5'.")

		count_s, sides_s, int_s = m.group(1), m.group(2), m.group(3)
		if sides_s is not None:
			count = int(count_s) if (count_s is not None and count_s != "") else 1
			sides = int(sides_s)
			if count < 1 or count > 100:
				raise ValueError(f"dice count out of range (1..100): {count}")
			if sides < 2 or sides > 1000000:
				raise ValueError(f"dice sides out of range (2..1,000,000): {sides}")
			terms.append(DiceTerm(kind="dice", count=count, sides=sides))
			continue

		if int_s is not None:
			val = int(int_s)
			terms.append(ModifierTerm(kind="modifier", value=val))
			continue

		raise ValueError(f"Unreachable parse state for token {raw!r}")

	if not terms:
		raise ValueError(f"No terms parsed from expr: {expr!r}")
	return terms


def _roll_terms(terms: list[Term]) -> tuple[int, list[dict[str, Any]]]:
	rng = secrets.SystemRandom()
	total = 0
	details: list[dict[str, Any]] = []

	for t in terms:
		if t.kind == "modifier":
			total += t.value
			details.append({"kind": "modifier", "value": t.value})
			continue

		rolls: list[int] = []
		for _ in range(t.count):
			rolls.append(rng.randrange(1, t.sides + 1))
		subtotal = sum(rolls)
		total += subtotal
		details.append(
			{
				"kind": "dice",
				"count": t.count,
				"sides": t.sides,
				"rolls": rolls,
				"subtotal": subtotal,
			}
		)

	return total, details


def _format_md(result: dict[str, Any]) -> str:
	expr = result.get("expr")
	dc = result.get("dc")
	total = result.get("total")
	success = result.get("success")

	line = f"- **Roll**: `{expr}` → **{total}**"
	if dc is not None:
		line += f" vs **DC {dc}** → **{'Success' if success else 'Fail'}**"
	return line


def _append_ndjson(path: Path, obj: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("a", encoding="utf-8") as f:
		f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--expr", required=True, help='Dice expression like "d20 + 6 + 2" or "2d6+1"')
	parser.add_argument("--dc", type=int, default=None, help="Optional DC to evaluate success")
	parser.add_argument("--label", default=None, help="Optional human label (e.g., 'Turn 008: Ki ray')")
	parser.add_argument("--log", default=None, help="Optional NDJSON output path to append the roll record")
	parser.add_argument("--md", action="store_true", help="Print a Markdown-ready summary line before JSON")
	args = parser.parse_args()

	terms = _parse_expr(args.expr)
	total, term_details = _roll_terms(terms)

	record: dict[str, Any] = {
		"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
		"nonce": secrets.token_hex(8),
		"label": args.label,
		"expr": args.expr,
		"terms": term_details,
		"total": total,
	}
	if args.dc is not None:
		record["dc"] = int(args.dc)
		record["success"] = bool(total >= int(args.dc))

	if args.md:
		print(_format_md(record))

	if args.log:
		_append_ndjson(Path(args.log), record)

	print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
	main()

