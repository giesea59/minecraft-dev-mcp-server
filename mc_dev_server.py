r"""
Minecraft Dev MCP Server

Local MCP server for Minecraft plugin development:
- Code analysis and bug detection
- Schematic generation from JSON operations
- Plugin update checking (SpigotMC, GitHub, etc.)
- Plugin boilerplate scaffolding

Setup:
    pip install mcp mcschematic requests

Usage in LM Studio:
    Add custom MCP: python <path-to>/mc_dev_server.py
"""
import json
import math
import os
import re
from pathlib import Path
from typing import Any

try:
    import mcschematic
except ImportError:
    mcschematic = None

try:
    import requests
except ImportError:
    requests = None

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("minecraft-dev")

# Configuration
BUILDS_DIR = Path(os.environ.get("MC_BUILDS_DIR", Path.home() / "mc-builds"))
MAX_BLOCKS = int(os.environ.get("MC_MAX_BLOCKS", "400000"))


# ============================================================================
# Schematic Generation Tools
# ============================================================================

def _block(name):
    """Normalize block name to minecraft:blockname format."""
    name = str(name).strip()
    base, bracket, state = name.partition("[")
    if ":" not in base:
        base = "minecraft:" + base
    return base + bracket + state


def _pos(value, label):
    """Validate and convert position to (x, y, z) tuple."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be a list of three numbers [x, y, z]")
    return tuple(int(round(float(c))) for c in value)


def _box(a, b):
    """Calculate bounding box from two corners."""
    return (
        (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2])),
        (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2])),
    )


def _check_volume(volume):
    """Ensure volume doesn't exceed limit."""
    if volume > MAX_BLOCKS:
        raise ValueError(
            f"Shape covers ~{int(volume)} blocks, over limit of {MAX_BLOCKS}"
        )


def _iter_box(a, b, mode):
    """Iterate box coordinates. mode: 'solid', 'shell', or 'walls'."""
    (x1, y1, z1), (x2, y2, z2) = _box(a, b)
    _check_volume((x2 - x1 + 1) * (y2 - y1 + 1) * (z2 - z1 + 1))
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            for z in range(z1, z2 + 1):
                if mode == "solid":
                    yield (x, y, z)
                else:
                    on_x = x in (x1, x2)
                    on_z = z in (z1, z2)
                    on_y = y in (y1, y2)
                    if (on_x or on_z) if mode == "walls" else (on_x or on_y or on_z):
                        yield (x, y, z)


def _iter_cylinder(center, radius, height, hollow):
    """Iterate cylinder coordinates."""
    cx, cy, cz = center
    _check_volume(math.pi * radius * radius * height)
    outer = radius * radius + radius
    inner = (radius - 1) * (radius - 1) + (radius - 1)
    for dx in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            d2 = dx * dx + dz * dz
            if d2 > outer:
                continue
            if hollow and radius > 1 and d2 <= inner:
                continue
            for y in range(cy, cy + height):
                yield (cx + dx, y, cz + dz)


def _iter_sphere(center, radius, hollow):
    """Iterate sphere coordinates."""
    cx, cy, cz = center
    _check_volume(4 / 3 * math.pi * radius ** 3)
    outer = radius * radius + radius
    inner = (radius - 1) * (radius - 1) + (radius - 1)
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                d2 = dx * dx + dy * dy + dz * dz
                if d2 > outer:
                    continue
                if hollow and radius > 1 and d2 <= inner:
                    continue
                yield (cx + dx, cy + dy, cz + dz)


def _apply(op, blocks):
    """Apply a single build operation to the blocks dict."""
    kind = str(op.get("op", "")).lower()
    block = _block(op["block"]) if "block" in op else None

    if kind not in ("set", "fill", "hollow", "walls", "cylinder", "sphere"):
        raise ValueError(f"unknown op '{kind}'")
    if kind in ("set", "fill", "hollow", "walls", "cylinder", "sphere") and block is None:
        raise ValueError("missing 'block'")

    if kind == "set":
        cells = [_pos(op.get("pos"), "pos")]
    elif kind in ("fill", "hollow", "walls"):
        mode = {"fill": "solid", "hollow": "shell", "walls": "walls"}[kind]
        cells = _iter_box(_pos(op.get("from"), "from"), _pos(op.get("to"), "to"), mode)
    elif kind == "cylinder":
        cells = _iter_cylinder(
            _pos(op.get("center"), "center"),
            int(op["radius"]),
            int(op["height"]),
            bool(op.get("hollow", False)),
        )
    elif kind == "sphere":
        cells = _iter_sphere(
            _pos(op.get("center"), "center"),
            int(op["radius"]),
            bool(op.get("hollow", False)),
        )
    else:
        raise ValueError("missing 'op'")

    for cell in cells:
        blocks[cell] = block
        if len(blocks) > MAX_BLOCKS:
            raise ValueError(f"Over limit of {MAX_BLOCKS} blocks")


@mcp.tool()
def build_schematic(name: str, operations: list[dict]) -> str:
    """Build a Minecraft .schem file from JSON operations.

    Operations:
      set: place single block
      fill: solid box
      hollow: box shell (walls, floor, roof)
      walls: four walls only
      cylinder: cylinder with optional hollow
      sphere: sphere with optional hollow

    Args:
        name: filename without extension
        operations: list of operation objects
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name).strip("_") or "build"
    if not isinstance(operations, list) or not operations:
        return "No operations given."
    if len(operations) > 5000:
        return "Too many operations (limit 5000)."

    blocks = {}
    for i, op in enumerate(operations, start=1):
        try:
            if not isinstance(op, dict):
                raise ValueError("each operation must be an object")
            _apply(op, blocks)
        except Exception as exc:
            return f"Operation #{i} failed: {exc}"

    solid = {p: b for p, b in blocks.items() if b != "minecraft:air"}
    if not solid:
        return "No solid blocks in build."

    xs = [p[0] for p in solid]
    ys = [p[1] for p in solid]
    zs = [p[2] for p in solid]
    min_x, min_y, min_z = min(xs), min(ys), min(zs)
    size = (max(xs) - min_x + 1, max(ys) - min_y + 1, max(zs) - min_z + 1)

    if mcschematic is None:
        return f"schematic data ready: {len(solid)} blocks, size {size}. Install mcschematic to write .schem file."

    try:
        BUILDS_DIR.mkdir(parents=True, exist_ok=True)
        schem = mcschematic.MCSchematic()
        for (x, y, z), b in blocks.items():
            if x >= min_x and y >= min_y and z >= min_z:
                schem.setBlock((x - min_x, y - min_y, z - min_z), b)
        schem.save(str(BUILDS_DIR), safe, mcschematic.Version.JE_1_21_5)
        path = (BUILDS_DIR / f"{safe}.schem").resolve()
        return f"Saved {path}\nSize: {size[0]}x{size[1]}x{size[2]}, {len(solid)} blocks"
    except Exception as exc:
        return f"Error writing schematic: {exc}"


# ============================================================================
# Code Analysis Tools
# ============================================================================

@mcp.tool()
def analyze_java_code(code: str, filename: str = "plugin.java") -> str:
    """Analyze Java plugin code for common issues.

    Args:
        code: Java source code to analyze
        filename: name of the file (for context)
    """
    issues = []

    # Check for common plugin issues
    if "System.out.println" in code and "getLogger()" not in code:
        issues.append(
            "⚠️ Uses System.out.println instead of plugin logger. Use getLogger().info() instead."
        )

    if "Thread.sleep" in code and "async" not in code.lower():
        issues.append(
            "⚠️ Thread.sleep() found outside async context. This will block the server!"
        )

    if re.search(r"new File\(", code) and "getDataFolder()" not in code:
        issues.append(
            "⚠️ Creates File without plugin data folder. Use getDataFolder() for plugin files."
        )

    if "@EventHandler" in code and "EventPriority" not in code:
        issues.append(
            "⚠️ EventHandler without priority specified. Consider using @EventHandler(priority = EventPriority.NORMAL)"
        )

    if re.search(r"getPlayer\(.*\)\.", code):
        issues.append(
            "⚠️ Direct getPlayer() call without null check. Player might not be online!"
        )

    if "synchronized" not in code and re.search(r"static.*List|static.*Map", code):
        issues.append(
            "⚠️ Static collection without synchronization. Use Collections.synchronizedList() or ConcurrentHashMap."
        )

    if re.search(r"TODO|FIXME|HACK", code):
        matches = re.findall(r"(TODO|FIXME|HACK)[^\n]*", code)
        for match in matches[:3]:  # Show first 3
            issues.append(f"📝 {match}")

    # Check for potential NPE
    if ".get(" in code and "!= null" not in code and "Optional" not in code:
        issues.append(
            "⚠️ Potential null pointer exception. Add null checks or use Optional."
        )

    if not issues:
        return f"✅ No major issues found in {filename}"

    return "🔍 Code Analysis Results:\n" + "\n".join(f"  {issue}" for issue in issues)


@mcp.tool()
def suggest_plugin_boilerplate(plugin_name: str, description: str = "") -> str:
    """Generate boilerplate code for a new Spigot plugin.

    Args:
        plugin_name: name of the plugin
        description: brief description
    """
    safe_name = re.sub(r"[^A-Za-z0-9]", "", plugin_name)
    package_name = f"com.example.{safe_name.lower()}"

    main_class = f'''package {package_name};

import org.bukkit.plugin.java.JavaPlugin;

public class {safe_name} extends JavaPlugin {{
    @Override
    public void onEnable() {{
        getLogger().info("{plugin_name} has been enabled!");
        // Register commands, listeners, etc.
    }}

    @Override
    public void onDisable() {{
        getLogger().info("{plugin_name} has been disabled!");
    }}
}}
'''

    plugin_yml = f'''name: {plugin_name}
version: 1.0
main: {package_name}.{safe_name}
description: {description}
authors:
  - YourName
'''

    return f"""Generated boilerplate for {plugin_name}:

**Main.java:**
```java
{main_class}
```

**plugin.yml:**
```yaml
{plugin_yml}
```
"""


# ============================================================================
# Plugin Update Checking
# ============================================================================

@mcp.tool()
def check_spigot_updates(plugin_name: str) -> str:
    """Check for plugin updates on SpigotMC.

    Args:
        plugin_name: name of the plugin
    """
    if requests is None:
        return "requests library not installed. Install with: pip install requests"

    try:
        # This is a simplified example - SpigotMC doesn't have a public API
        # In production, you'd scrape or use a plugin repository API
        return f"Update checking for '{plugin_name}' requires manual SpigotMC lookup at https://www.spigotmc.org/resources/"
    except Exception as e:
        return f"Error checking updates: {e}"


@mcp.tool()
def check_github_releases(owner: str, repo: str) -> str:
    """Check for releases on GitHub.

    Args:
        owner: GitHub repository owner
        repo: GitHub repository name
    """
    if requests is None:
        return "requests library not installed."

    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return f"Latest: {data.get('tag_name', 'unknown')}\nDownload: {data.get('html_url', 'N/A')}"
        return f"Repo not found or no releases: {response.status_code}"
    except Exception as e:
        return f"Error checking GitHub releases: {e}"


# ============================================================================
# Utility Tools
# ============================================================================

@mcp.tool()
def list_schematics() -> str:
    """List all saved schematics."""
    if not BUILDS_DIR.exists():
        return "No schematics directory found."
    files = sorted(BUILDS_DIR.glob("*.schem"))
    if not files:
        return "No schematics saved yet."
    return "\n".join(f"{f.name} ({f.stat().st_size} bytes)" for f in files)


@mcp.tool()
def get_mc_dev_help() -> str:
    """Show available tools and usage examples."""
    return """# Minecraft Dev MCP Server

## Schematic Tools
- `build_schematic(name, operations)` - Generate .schem from JSON ops
- `list_schematics()` - List saved schematics

## Code Analysis
- `analyze_java_code(code, filename)` - Find bugs in Java plugin code
- `suggest_plugin_boilerplate(name, description)` - Generate starter code

## Plugin Updates
- `check_github_releases(owner, repo)` - Check GitHub for latest release
- `check_spigot_updates(plugin_name)` - Info on checking SpigotMC

## Examples

### Build a stone tower:
```json
{"op": "cylinder", "center": [0, 0, 0], "radius": 5, "height": 10, "block": "stone_bricks"}
```

### Analyze plugin code:
Paste your Java code and I'll find issues.

### Check AxPlayerWarps updates:
I can look up the latest GitHub release for Artillex-Studios/AxPlayerWarps
"""


if __name__ == "__main__":
    mcp.run()
