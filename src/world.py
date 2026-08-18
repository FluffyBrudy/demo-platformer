from pathlib import Path
from random import choice, random, randrange

import pygame
from pygame.surface import Surface
from pygkit import LightMap, PointLight
from pygkit.lighting import blend
from tilemap_parser import (
    AnimationPlayer,
    Camera,
    CollisionRunner,
    ObjectCollisionManager,
    ParticleSystem,
    PhysicsWorld,
    SpriteAnimationSet,
    TileLayerRenderer,
    TilemapData,
    get_shape_aabb,
    load_map,
    load_tileset_collision,
)

from src.core.effects import ParticleConsumerPartial, particle_consumer
from src.entity.enemies.base import HorizontalGroundedEnemy
from src.entity.enemies.mushroom import Mushroom
from src.entity.player import Player
from src.settings import ANIMATION_PATH, TILESET_COLLISION_PATH
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
        self.light_map.set_ambient((0, 255, 0), 0.4)
        self.player_point_light = PointLight(radius=110, color=(255, 255, 255), falloff="exp", exponent=2, intensity=5)
        self.enemy_point_light = PointLight(radius=50, color=(255, 255, 255), falloff="linear")

        self.animated_object_map = {
            "sakura_green": ANIMATION_PATH / "sakura_green.anim.json",
            "big_trunk": ANIMATION_PATH / "big_trunk.anim.json",
        }

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
        self.animated_map_objects: list[tuple[AnimationPlayer, float, float]] = []

        r = map_data.render_scale
        for layer in map_data.parsed.layers:
            if layer.layer_type == "tile" or not layer.visible:
                continue
            for surf, x, y, oid in map_data.get_object_surfaces(layer.name):
                object_props = layer.objects[oid].properties
                if object_props and object_props.get("name", False):
                    path = self.animated_object_map.get(object_props["name"])  # pyright: ignore
                    if path is None:
                        continue
                    anim_system = SpriteAnimationSet.load(path, render_scale=r)
                    label = next(iter(anim_system.library.animations.keys()))
                    anim_player = AnimationPlayer(anim_system, label)
                    clip = anim_player.clip
                    if clip is not None and clip.frames:
                        anim_player._frame_index = randrange(len(clip.frames))
                    self.animated_map_objects.append((anim_player, x * r, y * r))
                else:
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

    def is_ground_ahead(self, sprite: HorizontalGroundedEnemy) -> bool:
        left, _, right, bottom = get_shape_aabb(sprite.x, sprite.y, sprite.collision_shape)
        probe_x = right + 1 if sprite.direction > 0.001 else left - 1
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

        for anim_player, x, y in self.animated_map_objects:
            seed = int(random() * 1000)
            anim_player.update(dt * seed)

        self.player_point_light.advance(dt)
        self.enemy_point_light.advance(dt)

        for enemy in self.enemies:
            enemy.update(dt)

        colliding_obj = self.object_collision.check_object_first(self.player)  # pyright: ignore
        if colliding_obj is not None:
            other = colliding_obj.other(self.player)  # pyright: ignore
            if isinstance(other, Mushroom):
                normal_x = colliding_obj.normal[0]
                if abs(normal_x) < 0.01 and other.can_stun():
                    self.player.knockback(0)
                    other.stun()
                elif other.can_damage():
                    self.player.knockback(-normal_x)
                    self.camera.shake(0.5, 10)
                    _, t, r, b = self.player.shape_aabb
                    self.player.emit(
                        {
                            "x": r,
                            "y": (t + b) * 0.5,
                            "name": "dashorb",
                            "direction": -1,
                            "count": 20,
                            "color": (255, 0, 0),
                        }
                    )

    def render(self, screen: Surface) -> None:
        self.light_map.clear()

        cam_x, cam_y = self.camera.offset

        for anim_player, x, y in self.animated_map_objects:
            frame = anim_player.get_current_image()
            screen.blit(frame, (x - cam_x, y - cam_y), special_flags=blend.RGBA_MAX)  # pyright: ignore

        self.renderer.render(screen, self.camera.offset)

        for system in self.particles.values():
            system.draw(screen, self.camera.offset[0], self.camera.offset[1], 1.0)

        for enemy in self.enemies:
            enemy.render(screen, self.camera.offset)
            dx = self.player.x - enemy.x
            dy = self.player.y - enemy.y
            distance_squared = dx * dx + dy * dy
            max_distance_squared = 700.0**2
            i = max(
                0.0,
                1.0 - distance_squared / max_distance_squared,
            )
            self.enemy_point_light.intensity = i * i
            left, top, right, bottom = enemy.shape_aabb
            self.enemy_point_light.render(
                self.light_map,
                (left + right) * 0.5 - cam_x,
                (top + bottom) * 0.5 - cam_y,
            )
        self.player.render(screen, self.camera.offset)
        for surf, x, y in self.map_objects:
            screen.blit(surf, (x - cam_x, y - cam_y))

        self.player_point_light.render(self.light_map, self.player.x - cam_x, self.player.y - cam_y)
        self.light_map.apply(screen, blend=blend.RGB_MULT)
