from pathlib import Path

import pygame
import pygkit.lighting.blend as blend
from pygame.surface import Surface
from pygkit import LightMap, PointLight
from tilemap_parser import (
    Camera,
    CollisionRunner,
    ObjectCollisionManager,
    ParticleSystem,
    PhysicsWorld,
    TileLayerRenderer,
    TilemapData,
    load_map,
    load_tileset_collision,
)

from src.core.effects import ParticleConsumerPartial, particle_consumer
from src.entity.enemies.mushroom import Mushroom
from src.entity.player import Player, emit_particle
from src.settings import TILESET_COLLISION_PATH

RUNNER_SPEED = 150.0


class World:
    def __init__(self, map_path: Path, viewport_w: int, viewport_h: int) -> None:
        map_data = load_map(map_path)
        collision_tileset = load_tileset_collision(TILESET_COLLISION_PATH / "tiles.collision.json")
        if collision_tileset is None:
            raise ValueError("Unable to load collision tileset")

        self.render_scale = map_data.render_scale
        self.renderer = TileLayerRenderer(map_data)
        self.runner = CollisionRunner.from_world(
            PhysicsWorld.from_map(map_data, collision_tileset, use_gids=True),
            game_type="platformer",
        )
        self.runner.horizontal_speed = RUNNER_SPEED

        self.player = Player(100, 150)
        self.camera = Camera(viewport_w, viewport_h)
        self.camera.bounds = self._map_bounds(map_data)  # pyright: ignore
        self.camera.follow(self.player)
        self.camera.lerp_speed = 5.0

        self.light_map = LightMap((viewport_w, viewport_h), scale=0.5)
        self.light_map.set_ambient((0, 0, 0), 0.9)
        self.player_point_light = PointLight(radius=200, color=(100, 255, 255), falloff="exp", exponent=2, intensity=5)

        self._load_particles(map_data)
        self.map_objects: list[tuple[Surface, float, float]] = []
        self._load_objects(map_data)

        self._load_enemies()

    def _map_bounds(self, map_data: TilemapData) -> tuple[float, float, float, float]:
        tile_w, tile_h = map_data.tile_size
        ccount, rcount = map_data.map_size
        r = map_data.render_scale
        return (0, 0, tile_w * ccount * r, tile_h * rcount * r)

    def _load_enemies(self):
        self.enemies: list[Mushroom] = []
        self.object_collision = ObjectCollisionManager()
        mushroom = Mushroom(200, 300)
        self.object_collision.add_object(mushroom)  # pyright: ignore
        self.enemies.append(mushroom)

    def _load_objects(self, map_data: TilemapData) -> None:
        r = map_data.render_scale
        for layer in map_data.parsed.layers:
            if layer.layer_type == "tile":
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

    def update(self, dt: float) -> None:
        self.camera.update(dt)
        self.player.update(dt)
        cr = self.runner.move_platformer(self.player, None, None, dt, velocity=(self.player.vx, self.player.vy))
        if cr.collided:
            _, t, r, b = self.player.shape_aabb
            emit_particle(r, (t + b) * 0.5, -1, count=20)
        for name, system in self.particles.items():
            system.update(dt, *self.node_areas[name])
        self.player_point_light.advance(dt)

        for enemy in self.enemies:
            self.runner.move_grounded(enemy, None, None, dt)

        res = self.object_collision.check_object_first(self.player)  # pyright: ignore
        if res is not None:
            pass

    def consume_particles(self, config: ParticleConsumerPartial) -> None:
        particle_consumer(self.particles, config)

    def render(self, screen: Surface) -> None:
        cam_x, cam_y = self.camera.offset
        for surf, x, y in self.map_objects:
            screen.blit(surf, (x - cam_x, y - cam_y))
        self.renderer.render(screen, self.camera.offset)
        for system in self.particles.values():
            system.draw(screen, self.camera.offset[0], self.camera.offset[1], 1.0, pygame.BLEND_RGB_MAX)
        self.player.render(screen, self.camera.offset)

        for enemy in self.enemies:
            enemy.render(screen, self.camera.offset)

        self.light_map.clear()
        self.player_point_light.render(self.light_map, self.player.x, self.player.y)
        self.light_map.apply(screen)
