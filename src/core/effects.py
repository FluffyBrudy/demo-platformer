import math
from typing import TypedDict

import pygame
from pygame.surface import Surface
from tilemap_parser import ICollidable, ParticleSystem, get_shape_aabb


class Spotlight:
    def __init__(self, radius: int, intensity: float, vw: int, vh: int, follow_ref: ICollidable) -> None:
        self.intensity = intensity
        self.vw, self.vh = vw, vh
        self.radius = radius
        self.follow_ref = follow_ref

        self.light = pygame.Surface((vw // 2, vh // 2), pygame.SRCALPHA)
        self.glow = self._make_glow()

    def _make_glow(self):
        size = 2 * self.radius
        surface = pygame.Surface((size, size), pygame.SRCALPHA)

        cx = cy = self.radius

        for y in range(size):  # y -> row
            for x in range(size):
                dx = x - cx
                dy = y - cy
                dist = dx**2 + dy**2
                if dist > self.radius**2:
                    continue

                n = math.sqrt(dist) / self.radius
                alpha = 255 * (math.e ** (-4 * n * n))
                v = int(alpha)
                surface.set_at((x, y), (v, v, v, 255))

        return surface

    def render(self, surface: Surface, offset: tuple[float, float]):
        ambient = int(self.intensity * 255)
        self.light.fill((ambient, ambient, ambient))

        z = self.light.width / self.vw
        l, t, r, b = get_shape_aabb(self.follow_ref.x, self.follow_ref.y, self.follow_ref.collision_shape)
        cx = ((l + r) * 0.5 - offset[0]) * z
        cy = ((t + b) * 0.5 - offset[1]) * z

        self.light.blit(self.glow, self.glow.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGBA_ADD)
        scaled = pygame.transform.smoothscale(self.light, (self.vw, self.vh))
        surface.blit(scaled, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)


class ParticleConsumer(TypedDict):
    x: float
    y: float
    name: str


class ParticleConsumerPartial(ParticleConsumer, total=False):
    count: int
    direction: float
    width: int
    height: int
    offset: tuple[int, int]


def particle_consumer(
    particle_lookup: dict[str, ParticleSystem],
    config: ParticleConsumerPartial,
):
    """This is mutable, ensure that direction is always included whoever consumes"""
    x = config["x"]
    y = config["y"]
    name = config["name"]
    count = config.get("count", 5)
    direction = config.get("direction", 0.0)
    width = config.get("width", 1)
    height = config.get("height", 1)

    particle_lookup[name].config.direction = direction
    particle_lookup[name].emit_burst(count, x, y, width, height)
