# `codex/cli/`

CLI helpers for the v2 filesystem-driven game loop.

## Commands

Create a new world (copies `codex/worlds/_TEMPLATE`):
- `python3 codex/cli/new_world.py --world My_World`

Create a new campaign within a world:
- `python3 codex/cli/new_campaign.py --world My_World --campaign Campaign_01 --player-name Aris --location "The Pens"`

Validate a campaign’s YAML against schemas:
- `python3 codex/cli/validate.py --world My_World --campaign Campaign_01`

Apply a turn from a YAML “turn file”:
- `python3 codex/cli/apply_turn.py --world My_World --campaign Campaign_01 --turn-file codex/cli/examples/turn_ok.yaml`

Render a tactical map SVG (background image + code-positioned tokens):
- `python3 codex/cli/render_tactical_map.py --world My_World --campaign Campaign_01`

## Turn File Format

Turn files are YAML mappings with these common keys:
- `scene_md` (string, markdown)
- `options` (list of strings)
- `what_changed` (list of strings; human-readable)
- `mechanics_md` (string; goes inside an Obsidian `<details>` block)

### State Deltas
`delta.player` supports two operation lists:

```yaml
delta:
  player:
    add:
      - target: resources   # resources|stats|xp
        key: hp             # for resources/stats
        value: -5
    set:
      - target: xp
        value: 50
```

Resources cannot go below 0 (`hp`, `fatigue`, `hunger`). If a delta would make them negative, the turn is rejected.

### Updating `world_state.yaml`

```yaml
delta:
  world_state:
    set:
      - key: location
        value: "Maintenance Tunnels"
      - key: scene_tags
        value: ["dark", "humid"]
```

### Log Rotation (New Chapter File)
Create a new log file and set it as `campaign.yaml:log_active`:

```yaml
rotate_log:
  path: "campaign_logs/001_First_Blood.md"
  title: "001 — First Blood"
```

Note: the *current* turn is appended to the current active log; the next turn will go to the rotated `log_active`.
