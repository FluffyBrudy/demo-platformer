from abc import ABC, abstractmethod
from collections.abc import Callable

import pygame
from pygame.surface import Surface
from tilemap_parser import AnimationPlayer, ICollidableSprite, get_shape_aabb

from src.core.effects import ParticleConsumerPartial


class CollidableAnimationEntity(ICollidableSprite, ABC):
    flipped: bool
    animation_states: dict[str, AnimationPlayer]
    current_state: str = ""
    emit: Callable[[ParticleConsumerPartial], None]
    blend_flags: int = 0
    shape_aabb: tuple[float, float, float, float]
    collision_mask: int = 0
    collision_layer: int = 0

    def update(self, dt: float) -> None:
        self.shape_aabb = get_shape_aabb(self.x, self.y, self.collision_shape)
        self.update_physics(dt)
        self.update_animation(dt)

    @abstractmethod
    def update_physics(self, dt: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_state(self) -> str:
        raise NotImplementedError

    def update_animation(self, dt: float) -> None:
        state = self.get_state()
        if self.current_state != state:
            self.current_state = state
            self.animation_states[state].reset()
        self.animation_states[self.current_state].update(dt * 1000)

    def render(self, surface: Surface, offset: tuple[float, float]) -> None:
        frame = self.animation_states[self.current_state].get_current_image()
        if frame is None:
            return
        if self.flipped:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (self.x - offset[0], self.y - offset[1]), special_flags=self.blend_flags)
