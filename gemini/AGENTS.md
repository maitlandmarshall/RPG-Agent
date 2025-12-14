
# Agentic Roleplay Engine Design

## Core Concept
Leverage the Agent's file system access, code execution, and persistent memory (artifacts) to create a robust "Game Master" system that maintains state consistency better than raw LLM context.

## 1. The "Database" (State Management)
We will use a designated folder structure to separate structured data from narrative history, nested by World/Campaign.

### Directory Structure
```
root/
  engine/
    game_engine.js
  worlds/
    [WorldName]/
      characters/
        player.yaml
        ...
      campaign_logs/
        001_Chapter.md
      world_state.yaml
```

### `worlds/[WorldName]/characters/`
Directory for character sheet YAML files.
- `player.yaml`: The main character.
- `npc_name.yaml`: Important NPCs.

**Format (`player.yaml`):**
```yaml
name: "Aris"
class: "Rogue"
stats:
  strength: 10
  agility: 15
inventory:
  - name: "rusty dagger"
    equipped: true
status:
  health: 100
  fatigue: 0
```

### `worlds/[WorldName]/world_state.yaml`
The dynamic context of the current immediate scene.
```yaml
location: "The Old Ruins - Entrance"
weather: "Light Rain"
time: "Dusk"
npcs:
  - name: "Guard"
    status: "Suspicious"
```

### `worlds/[WorldName]/campaign_logs/`
Folder for narrative history.
**Log Rotation Logic**:
A new log file is created in two matching scenarios:
1. **New Session**: When the user starts a fresh chat session after a long break.
2. **New Chapter**: When a major narrative arc concludes (e.g., leaving a city, finishing a dungeon).
**Naming**: `001_The_beginning.md`, `002_Into_the_wilds.md`.

**Image Embedding**:
Images generated via `generate_image` must be embedded using standard markdown: `![Caption](/absolute/path/to/image.png)`.

## 2. The "Engine" (Logic & Rules)
We keep `game_engine.js` in a shared `engine/` folder or root, acting as the impartial arbiter.

- **Conflict Resolution**: As defined (Gaussian distributions).
- **Loot Generation**: Procedural generation tables.
- **Travel Mechanics**: Calculating time/fatigue based on terrain.

**Workflow**:
1. User defines World Name (e.g., "NeonTokyo").
2. User takes action.
3. Agent calls `node engine/game_engine.js resolve ...`.
4. Agent updates `worlds/NeonTokyo/characters/player.yaml`.
5. Agent writes narrative to `worlds/NeonTokyo/campaign_logs/...`.
6. Agent Narrates response to user.

## 3. The "Visuals" (Immersion)
Use `generate_image` proactively when entering new significant locations or encountering major NPCs/Monsters.
