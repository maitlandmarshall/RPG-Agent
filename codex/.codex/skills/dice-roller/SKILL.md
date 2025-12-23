---
name: dice-roller
description: Roll real dice using OS randomness (not fabricated), optionally log results to NDJSON for audit, and emit a Markdown-ready summary for Mechanics blocks.
---

# Dice Roller (Real RNG + Audit Log)

Use this skill whenever the game rules require a roll like `d20 + stat + skill` and you want outcomes to be **truly random** and **auditable**.

## Quickstart

Roll a check:
- `python3 .codex/skills/dice-roller/scripts/roll_dice.py --expr "d20 + 5 + 1" --dc 15 --label "Ki ray (Agility+Ki Blast)" --md`

Roll and append to an audit log (NDJSON):
- `python3 .codex/skills/dice-roller/scripts/roll_dice.py --expr "d20 + 5 + 1" --dc 15 --label "Turn 008: Ki ray" --log "worlds/<World>/campaigns/<Campaign>/campaign_logs/_rolls.ndjson" --md`

## Expression format

Supported terms:
- Dice: `d20`, `2d6`, `4d4` (count defaults to 1)
- Modifiers: `+ 3`, `- 2`

Examples:
- `d20 + 6 + 3`
- `2d6 + 1`

Notes:
- Keep it simple (no parentheses). If you need something complex, expand it into explicit `+`/`-` terms.

## Output

The script prints a single JSON object to stdout (last line), including:
- `expr`, `terms`, per-die `rolls`, `total`
- optional `dc` and computed `success`
- `timestamp_utc` and a random `nonce` for auditability

With `--md`, it prints a Markdown-ready summary before the JSON.

