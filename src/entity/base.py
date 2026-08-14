from abc import ABC, abstractmethod
from collections.abc import Callable

import pygame
from pygame.surface import Surface
from tilemap_parser import AnimationPlayer, ICollidableSprite

from src.core.effects import ParticleConsumerPartial


class AnimationEntity(ICollidableSprite, ABC):
    flipped: bool
    animation_states: dict[str, AnimationPlayer]
    current_state: str = ""
    emit: Callable[[ParticleConsumerPartial], None]
    blend_flags: int = 0

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
