# `codex/` (v2)

Fresh-start v2 implementation of the Agentic Roleplay Engine, designed for:
- multi-world + multi-campaign play
- Obsidian-style markdown logs as the player UI
- schema-validated state (YAML)
- deterministic/semi-deterministic mechanics (seeded RNG per turn)

Start here:
- `codex/AGENTS.md` (rules + output contract)
- `codex/cli/` (world/campaign creation + turn application)
- `codex/engine/` (validation + mechanics)
More CLI details: `codex/cli/README.md`

## Requirements
- Python 3.10+ (this repo’s sandbox currently does not provide `node`)

## Quickstart (v2)
Create a new world + campaign:
- `python3 codex/cli/new_world.py --world Planet_Vegeta_V2`
- `python3 codex/cli/new_campaign.py --world Planet_Vegeta_V2 --campaign Campaign_01 --player-name Cress`

Validate a campaign:
- `python3 codex/cli/validate.py --world Planet_Vegeta_V2 --campaign Campaign_01`

Apply a turn:
- `python3 codex/cli/apply_turn.py --world Planet_Vegeta_V2 --campaign Campaign_01 --turn-file codex/cli/examples/turn_ok.yaml`
