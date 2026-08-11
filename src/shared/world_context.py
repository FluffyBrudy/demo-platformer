from pathlib import Path
from warnings import deprecated

from tilemap_parser import CollisionCache, load_map


@deprecated("Prefer some common method like preload insted of global mutable data")
class WorldContext:
    __slots__ = ("collision_cache", "render_scale")

    def __init__(self) -> None:
        self.collision_cache = CollisionCache()
        self.render_scale = 1.0

    def load_map(self, path: Path):
        map_data = load_map(path)
        self.render_scale = map_data.render_scale
        return map_data


world_context = WorldContext()
collision_cache = CollisionCache()
