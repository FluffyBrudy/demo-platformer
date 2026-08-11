from typing import Literal, cast

import pygame
from pygame.surface import Surface
from tilemap_parser import AnimationPlayer, ICollidableSprite, SpriteAnimationSet

from src.settings import ANIMATION_PATH, CHARACTER_COLLISION_PATH
from src.shared.world_context import collision_cache

TMushroomStates = Literal["idle", "run", "attack", "attack_with_stun", "hurt", "dead"]


class Mushroom(ICollidableSprite):
    collision_path = CHARACTER_COLLISION_PATH / "mushroom.collision.json"
    animation_path = ANIMATION_PATH / "mushroom.anim.json"

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0
        self.on_ground = False
        self.collision_shape = collision_cache.get_character_collision(self.collision_path).shape  # pyright: ignore

        sprite_animation_set = SpriteAnimationSet.load(self.animation_path)
        self.animation_states: dict[TMushroomStates, AnimationPlayer] = {
            "idle": AnimationPlayer(sprite_animation_set, "idle"),
            "attack": AnimationPlayer(sprite_animation_set, "jump"),
            "run": AnimationPlayer(sprite_animation_set, "run"),
            "attack_with_stun": AnimationPlayer(sprite_animation_set, "attack_with_stun"),
            "hurt": AnimationPlayer(sprite_animation_set, "hurt"),
            "dead": AnimationPlayer(sprite_animation_set, "dead"),
        }
        self.current_animation: TMushroomStates = "idle"

    def update(self, dt: float):
        self.animation_states[self.current_animation].update(dt)

    def render(self, surface: Surface, offset: tuple[float, float]):
        frame = self.animation_states[self.current_animation].get_current_image()
        if frame is None:
            return
        surface.blit(frame, (self.x - offset[0], self.y - offset[1]))
