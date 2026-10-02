# Minecraft Dev MCP Server

A local Model Context Protocol (MCP) server for Minecraft plugin development.

## Features

- **Schematic Generation** — Create `.schem` files from JSON build operations
- **Code Analysis** — Detect bugs and issues in Java plugin code
- **Plugin Scaffolding** — Generate boilerplate for new Spigot plugins
- **Update Checking** — Monitor GitHub/SpigotMC for plugin updates
- **Development Tools** — Utilities for plugin creation and debugging

## Setup

### 1. Install Dependencies

```bash
pip install mcp mcschematic requests
```

### 2. Add to LM Studio

1. Open LM Studio
2. Go to MCP Servers
3. Click "Add custom MCP"
4. Select "Command"
5. Enter: `python <full-path-to>/mc_dev_server.py`
6. Give it a name like "Minecraft Dev"
7. Save and enable

### 3. Restart LM Studio

Your local model now has access to all Minecraft dev tools!

## Usage Examples

### Generate a Schematic

```python
build_schematic("my_tower", [
    {"op": "cylinder", "center": [0, 0, 0], "radius": 5, "height": 10, "block": "stone_bricks"},
    {"op": "set", "pos": [0, 11, 0], "block": "torch"}
])
```

### Analyze Plugin Code

Paste your Java plugin code and ask the model to analyze it. The tool will find:
- Use of `System.out.println` instead of logger
- Blocking operations on main thread
- Missing null checks
- Synchronization issues
- And more...

### Check for Plugin Updates

```python
check_github_releases("Artillex-Studios", "AxPlayerWarps")
```

## Configuration

Set environment variables to customize behavior:

```bash
# Where to save .schem files
export MC_BUILDS_DIR=/path/to/builds

# Maximum blocks per schematic
export MC_MAX_BLOCKS=500000
```

## Operation Types

### set
Place a single block.
```json
{"op": "set", "pos": [x, y, z], "block": "stone"}
```

### fill
Solid rectangular box.
```json
{"op": "fill", "from": [x1, y1, z1], "to": [x2, y2, z2], "block": "stone"}
```

### hollow
Box shell (walls, floor, roof).
```json
{"op": "hollow", "from": [x1, y1, z1], "to": [x2, y2, z2], "block": "stone_bricks"}
```

### walls
Four walls only (no floor or roof).
```json
{"op": "walls", "from": [x1, y1, z1], "to": [x2, y2, z2], "block": "stone_bricks"}
```

### cylinder
Cylinder with optional hollow.
```json
{"op": "cylinder", "center": [x, y, z], "radius": 5, "height": 10, "block": "stone", "hollow": false}
```

### sphere
Sphere with optional hollow.
```json
{"op": "sphere", "center": [x, y, z], "radius": 5, "block": "glass", "hollow": true}
```

## License

MIT
