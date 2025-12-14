
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

### `worlds/[WorldName]/codex/`
Encyclopedia of characters, locations, items, and lore.
- **Rule 1 (Creation)**: When a NEW entity appears, create a `.md` file in `codex/`.
- **Rule 2 (Description)**: Write a rich, sensory description of the character's face, body, and unique markings.
- **Rule 3 (Visuals)**: Generate an image **based strictly on the written description**.
    - **CRITICAL**: Do NOT use "Dragon Ball", "DBZ", or "Saiyan" in prompts. Use "thick line art", "retro anime style", "tech-armor", etc.
- **Rule 4 (Living Document)**: Update entries immediately if a major event changes their state or appearance.

### Interactive Comic Book Protocol (MANDATORY)
- **Visual Flow**: The campaign log should read like an interactive comic.
- **Interleaving**: Whenever a character or location is mentioned for the first time or is the focus of a scene, **EMBED THEIR IMAGE** directly into the log narrative.
- **Action Panels**: During high-stakes interactions, generate "Action Shot" images. **EMBED THEM** directly into the log at the moment of action.
- **Trigger**: New Entity Mentioned -> Create Codex Entry -> Generate Image -> **Insert Image in Log**.

### Pre-Yield Checklist
Before yielding control back to the User, the Agent **MUST** verify:
1. [ ] Have all new entities (Characters, Locations, Items) been created in the `codex/`?
2. [ ] Have visuals been generated for them?
3. [ ] Have those visuals been inserted into the campaign log at the appropriate narrative moment?

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
6. **Agent updates Codex**: If new entities appear, create their markdown files in `codex/` and generate images.
7. Agent Narrates response to user.

## 3. The "Visuals" (Immersion)
Use `generate_image` proactively when entering new significant locations or encountering major NPCs/Monsters.
