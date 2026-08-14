from pathlib import Path

import pygame
from pygame.surface import Surface
from pygkit import LightMap, PointLight
from pygkit.lighting import blend
from tilemap_parser import (
    Camera,
    CollisionRunner,
    ICollidableSprite,
    ObjectCollisionManager,
    ParticleSystem,
    PhysicsWorld,
    TileLayerRenderer,
    TilemapData,
    get_shape_aabb,
    load_map,
    load_tileset_collision,
)

from src.core.effects import ParticleConsumerPartial, particle_consumer
from src.entity.enemies.mushroom import Mushroom
from src.entity.player import Player
from src.settings import TILESET_COLLISION_PATH
from src.utils.coor import align_bottom_right

RUNNER_SPEED = 150.0
KNOCKBACK_FORCE = 350.0
KNOCKBACK_UP = -200.0


class World:
    def __init__(self, map_path: Path, viewport_w: int, viewport_h: int) -> None:
        map_data = load_map(map_path)
        collision_tileset = load_tileset_collision(TILESET_COLLISION_PATH / "tiles.collision.json")
        if collision_tileset is None:
            raise ValueError("Unable to load collision tileset")

        self.render_scale = map_data.render_scale
        self.renderer = TileLayerRenderer(map_data, include_hidden_layers=False)
        self.physics_world = PhysicsWorld.from_map(map_data, collision_tileset, use_gids=True)
        self.runner = CollisionRunner.from_world(self.physics_world, game_type="platformer")
        self.runner.horizontal_speed = RUNNER_SPEED

        self.player = Player(100, 150)
        self.camera = Camera(viewport_w, viewport_h)
        self.camera.bounds = self._map_bounds(map_data)  # pyright: ignore
        self.camera.follow(self.player)
        self.camera.lerp_speed = 5.0

        self.light_map = LightMap((viewport_w, viewport_h), scale=0.5, pixelated=True)
        self.player_point_light = PointLight(radius=110, color=(100, 255, 255), falloff="exp", exponent=2, intensity=5)

        self._load_particles(map_data)
        self._load_objects(map_data)
        self.player.emit = self.consume_particles
        self._load_enemies(map_data)

    def _map_bounds(self, map_data: TilemapData) -> tuple[float, float, float, float]:
        tile_w, tile_h = map_data.tile_size
        ccount, rcount = map_data.map_size
        r = map_data.render_scale
        return (0, 0, tile_w * ccount * r, tile_h * rcount * r)

    def _load_enemies(self, map_data: TilemapData):
        self.object_collision = ObjectCollisionManager()
        self.enemies: list[Mushroom] = []

        enemies = map_data.get_object_surfaces("enemies", scaled=True)
        if len(enemies) == 0:
            raise TypeError("Enemy  layer not found")

        for surf, x, y, _ in enemies:
            mushroom = Mushroom(x, y, self.runner, self.is_ground_ahead, self.consume_particles, target=self.player)
            new_x, new_y = align_bottom_right((x, y, *surf.size), mushroom.size)
            mushroom.x = new_x
            mushroom.y = new_y
            self.object_collision.add_object(mushroom)  # pyright: ignore
            self.enemies.append(mushroom)

    def _load_objects(self, map_data: TilemapData) -> None:
        self.map_objects: list[tuple[Surface, float, float]] = []
        r = map_data.render_scale
        for layer in map_data.parsed.layers:
            if layer.layer_type == "tile" or not layer.visible:
                continue
            for surf, x, y, _ in map_data.get_object_surfaces(layer.name):
                scaled_surf = pygame.transform.scale_by(surf, r)
                self.map_objects.append((scaled_surf, x * r, y * r))

    def _load_particles(self, map_data: TilemapData) -> None:
        self.particles: dict[str, ParticleSystem] = {}
        self.node_areas: dict[str, tuple[float, float, float, float]] = {}
        for particle in map_data.particle_emitters:
            if particle.name == "dashorb":
                config = particle.config
                config.spawn_rate = 0
                config.direction = -1
                config.apply_render_scale(map_data.render_scale)
                self.particles[particle.name] = ParticleSystem(config)
                self.node_areas[particle.name] = (
                    particle.rect.x,
                    particle.rect.y,
                    particle.rect.w,
                    particle.rect.h,
                )

    def is_ground_ahead(self, sprite: ICollidableSprite, direction: int) -> bool:
        left, _, right, bottom = get_shape_aabb(sprite.x, sprite.y, sprite.collision_shape)
        probe_x = right + direction if sprite.vx > 0.001 else left - direction
        probe_y = bottom + 1
        tile_x, tile_y = self.runner.get_tile_at(probe_x, probe_y)
        tile_id = self.physics_world.tile_map.get((tile_x, tile_y))
        return tile_id is not None and self.physics_world.tileset_collision.has_collision(tile_id)  # pyright: ignore

    def consume_particles(self, config: ParticleConsumerPartial) -> None:
        particle_consumer(self.particles, config)

    def update(self, dt: float) -> None:
        self.camera.update(dt)
        self.player.update(dt)
        cr = self.runner.move_platformer(self.player, None, None, dt, velocity=(self.player.vx, self.player.vy))
        if cr.collided:
            _, t, r, b = self.player.shape_aabb
            self.player.emit({"x": r, "y": (t + b) * 0.5, "name": "dashorb", "direction": -1, "count": 20})
        for name, system in self.particles.items():
            system.update(dt, *self.node_areas[name])

        self.player_point_light.advance(dt)

        for enemy in self.enemies:
            enemy.update(dt)

        res = self.object_collision.check_object_first(self.player)  # pyright: ignore
        if res is not None:
            other = res.other(self.player)  # pyright: ignore
            nx, ny = res.normal
            self.player.vx = -nx * KNOCKBACK_FORCE
            self.player.vy = KNOCKBACK_UP * (-1 if ny < 0 else 1)
            if abs(nx) < 0.01 and isinstance(other, Mushroom) and other.can_stun():
                other.stun()

    def render(self, screen: Surface) -> None:
        cam_x, cam_y = self.camera.offset
        for surf, x, y in self.map_objects:
            screen.blit(surf, (x - cam_x, y - cam_y))
        self.renderer.render(screen, self.camera.offset)
        for system in self.particles.values():
            system.draw(screen, self.camera.offset[0], self.camera.offset[1], 1.0)
        self.player.render(screen, self.camera.offset)

        for enemy in self.enemies:
            enemy.render(screen, self.camera.offset)

        self.light_map.clear()
        self.player_point_light.render(self.light_map, self.player.x, self.player.y)
        self.light_map.apply(screen, blend=blend.RGB_MULT)
